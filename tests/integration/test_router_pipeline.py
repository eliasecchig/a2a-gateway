from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from gateway.core.a2a_client import A2AClient
from gateway.core.chunking import ChunkConfig, ChunkMode
from gateway.core.debounce import DebounceConfig
from gateway.core.policies import GroupMode, GroupPolicyChecker, GroupPolicyConfig
from gateway.core.rate_limit import BackoffConfig, RateLimitConfig
from gateway.core.router import Router
from gateway.core.types import InboundMessage
from tests.helpers.mock_adapter import MockAdapter

A2A_URL = "http://localhost:8001"


def _a2a_result(
    text: str = "agent reply",
    task_id: str = "t1",
    context_id: str = "c1",
    file_parts: list | None = None,
):
    parts = [{"kind": "text", "text": text}]
    if file_parts:
        parts.extend(file_parts)
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "artifacts": [{"parts": parts}],
        },
    }


def _msg(channel: str = "test", text: str = "hi", **kw) -> InboundMessage:
    defaults = {
        "channel": channel,
        "sender_id": "u1",
        "sender_name": "Alice",
        "text": text,
        "thread_id": "t1",
        "conversation_id": "conv1",
    }
    defaults.update(kw)
    return InboundMessage(**defaults)


@pytest.mark.asyncio
class TestRouterPipeline:
    @respx.mock
    async def test_happy_path(self):
        respx.post(A2A_URL).mock(
            return_value=Response(200, json=_a2a_result("hello back"))
        )
        client = A2AClient(A2A_URL)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        adapter = MockAdapter()
        router.register(adapter)

        await router._handle_inner(_msg())

        assert len(adapter.sent) == 1
        assert adapter.sent[0].text == "hello back"
        assert adapter.sent[0].recipient_id == "u1"
        assert adapter.sent[0].thread_id == "t1"
        await client.close()

    @respx.mock
    async def test_group_policy_blocks(self):
        route = respx.post(A2A_URL).mock(return_value=Response(200, json=_a2a_result()))
        policy = GroupPolicyChecker({"test": GroupPolicyConfig(mode=GroupMode.DISABLED)})
        client = A2AClient(A2A_URL)
        router = Router(
            client, policy_checker=policy, backoff_config=BackoffConfig(max_retries=0)
        )
        adapter = MockAdapter()
        router.register(adapter)

        await router._handle_inner(_msg(is_group=True))

        assert len(adapter.sent) == 0
        assert route.call_count == 0
        await client.close()

    @respx.mock
    async def test_debouncing_coalesces(self):
        respx.post(A2A_URL).mock(
            return_value=Response(200, json=_a2a_result("combined reply"))
        )
        client = A2AClient(A2A_URL)
        router = Router(
            client,
            debounce_config=DebounceConfig(
                window_ms=100, max_messages=10, max_chars=4000
            ),
            backoff_config=BackoffConfig(max_retries=0),
        )
        adapter = MockAdapter()
        router.register(adapter)

        await adapter.dispatch(_msg(text="one"))
        await adapter.dispatch(_msg(text="two"))
        await adapter.dispatch(_msg(text="three"))
        await asyncio.sleep(0.2)

        assert len(adapter.sent) == 1
        await client.close()

    @respx.mock
    async def test_chunking_splits_long_response(self):
        long_text = "word " * 1000
        respx.post(A2A_URL).mock(return_value=Response(200, json=_a2a_result(long_text)))
        client = A2AClient(A2A_URL)
        router = Router(
            client,
            chunk_config=ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=200),
            backoff_config=BackoffConfig(max_retries=0),
        )
        adapter = MockAdapter(channel_name="slack")
        router.register(adapter)

        await router._handle_inner(_msg(channel="slack"))

        assert len(adapter.sent) > 1
        await client.close()

    @respx.mock
    async def test_attachments_on_last_chunk(self):
        file_parts = [
            {
                "kind": "file",
                "file": {"uri": "https://x.com/f.png", "mimeType": "image/png"},
            }
        ]
        long_text = "word " * 1000
        respx.post(A2A_URL).mock(
            return_value=Response(200, json=_a2a_result(long_text, file_parts=file_parts))
        )
        client = A2AClient(A2A_URL)
        router = Router(
            client,
            chunk_config=ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=200),
            backoff_config=BackoffConfig(max_retries=0),
        )
        adapter = MockAdapter(channel_name="slack")
        router.register(adapter)

        await router._handle_inner(_msg(channel="slack"))

        assert len(adapter.sent) > 1
        for msg in adapter.sent[:-1]:
            assert msg.attachments == []
        assert len(adapter.sent[-1].attachments) == 1
        await client.close()

    @respx.mock
    async def test_session_continuity(self):
        route = respx.post(A2A_URL).mock(
            return_value=Response(200, json=_a2a_result(context_id="c1", task_id="t1"))
        )
        client = A2AClient(A2A_URL)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        adapter = MockAdapter()
        router.register(adapter)

        await router._handle_inner(_msg())
        await router._handle_inner(_msg())

        import json

        second_req = json.loads(route.calls[1].request.content)
        assert second_req["params"]["message"]["contextId"] == "c1"
        assert second_req["params"]["message"]["taskId"] == "t1"
        await client.close()

    @respx.mock
    async def test_a2a_error_sends_error_reply(self):
        respx.post(A2A_URL).mock(return_value=Response(500, text="server error"))
        client = A2AClient(A2A_URL)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        adapter = MockAdapter()
        router.register(adapter)

        await router._handle_inner(_msg())

        assert len(adapter.sent) == 1
        assert "couldn't process" in adapter.sent[0].text.lower()
        await client.close()

    @respx.mock
    async def test_markdown_adaptation_applied(self):
        respx.post(A2A_URL).mock(return_value=Response(200, json=_a2a_result("**bold**")))
        client = A2AClient(A2A_URL)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        adapter = MockAdapter(channel_name="whatsapp")
        router.register(adapter)

        await router._handle_inner(_msg(channel="whatsapp"))

        assert adapter.sent[0].text == "*bold*"
        await client.close()

    @respx.mock
    async def test_multi_account_routing(self):
        respx.post(A2A_URL).mock(return_value=Response(200, json=_a2a_result("reply")))
        client = A2AClient(A2A_URL)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        adapter = MockAdapter(channel_name="slack", account_id="ws_a")
        router.register(adapter)

        assert "slack:ws_a" in router.channels
        await router._handle_inner(_msg(channel="slack:ws_a"))

        assert len(adapter.sent) == 1
        await client.close()

    @respx.mock
    async def test_rate_limiting_acquire_called(self):
        respx.post(A2A_URL).mock(return_value=Response(200, json=_a2a_result("reply")))
        client = A2AClient(A2A_URL)
        a2a_rate = RateLimitConfig(max_requests=60, window_seconds=60)
        ch_rates = {"test": RateLimitConfig(max_requests=30, window_seconds=60)}
        router = Router(
            client,
            a2a_rate_limit=a2a_rate,
            channel_rate_limits=ch_rates,
            backoff_config=BackoffConfig(max_retries=0),
        )
        adapter = MockAdapter()
        router.register(adapter)

        with (
            patch.object(
                router._a2a_limiter, "acquire", new_callable=AsyncMock
            ) as a2a_acq,
            patch.object(
                router._channel_limiters["test"], "acquire", new_callable=AsyncMock
            ) as ch_acq,
        ):
            await router._handle_inner(_msg())

        a2a_acq.assert_called_once()
        ch_acq.assert_called_once()
        assert len(adapter.sent) == 1
        await client.close()
