"""Unit tests for GatewayPushExecutor and the agent card builder."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from a2a.types import Message, Part, Role

from gateway.core.a2a_client import A2AClient
from gateway.core.push_a2a import (
    CHANNEL_KEY,
    CONVERSATION_KEY,
    PUSH_PATH,
    RECIPIENT_KEY,
    THREAD_KEY,
    GatewayPushExecutor,
    PushRoutingError,
    build_push_agent_card,
)
from gateway.core.router import Router
from tests.helpers.mock_adapter import MockAdapter


def _make_inbound_message(text: str, **metadata: str) -> Message:
    return Message(
        message_id=uuid.uuid4().hex,
        role=Role.ROLE_USER,
        parts=[Part(text=text)],
        metadata=metadata or None,
    )


def _make_router(*adapters: MockAdapter) -> Router:
    router = Router(A2AClient("http://localhost:9999"))
    for adapter in adapters:
        router.register(adapter)
    return router


def _make_context(
    message: Message,
    *,
    context_id: str | None = None,
    task_id: str | None = None,
) -> AsyncMock:
    ctx = AsyncMock()
    ctx.message = message
    ctx.context_id = context_id
    ctx.task_id = task_id
    return ctx


@pytest.mark.asyncio
class TestGatewayPushExecutor:
    async def test_executor_routes_to_adapter(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hello",
            **{
                CHANNEL_KEY: "test",
                RECIPIENT_KEY: "U1",
                THREAD_KEY: "T1",
                CONVERSATION_KEY: "C1",
            },
        )
        queue = AsyncMock()
        await executor.execute(_make_context(message, context_id="ctx-1"), queue)

        assert len(adapter.sent) == 1
        sent = adapter.sent[0]
        assert sent.channel == "test"
        assert sent.recipient_id == "U1"
        assert sent.text == "hello"
        assert sent.thread_id == "T1"
        assert sent.conversation_id == "C1"
        queue.enqueue_event.assert_awaited_once()

    async def test_executor_handles_optional_metadata_absent(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hi",
            **{CHANNEL_KEY: "test", RECIPIENT_KEY: "U1"},
        )
        queue = AsyncMock()
        await executor.execute(_make_context(message), queue)

        sent = adapter.sent[0]
        assert sent.thread_id is None
        assert sent.conversation_id is None

    async def test_executor_rejects_missing_channel(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message("hi", **{RECIPIENT_KEY: "U1"})
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="gateway/channel"):
            await executor.execute(_make_context(message), queue)
        assert adapter.sent == []
        queue.enqueue_event.assert_not_awaited()

    async def test_executor_rejects_missing_recipient(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message("hi", **{CHANNEL_KEY: "test"})
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="gateway/recipient_id"):
            await executor.execute(_make_context(message), queue)

    async def test_executor_rejects_unknown_channel(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hi",
            **{CHANNEL_KEY: "nope", RECIPIENT_KEY: "U1"},
        )
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="not registered"):
            await executor.execute(_make_context(message), queue)

    async def test_executor_rejects_empty_text(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "",
            **{CHANNEL_KEY: "test", RECIPIENT_KEY: "U1"},
        )
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="no text"):
            await executor.execute(_make_context(message), queue)

    async def test_executor_wraps_adapter_failure(self):
        adapter = MockAdapter(channel_name="test")
        adapter.send = AsyncMock(side_effect=OSError("conn refused"))
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hi",
            **{CHANNEL_KEY: "test", RECIPIENT_KEY: "U1"},
        )
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="adapter send failed"):
            await executor.execute(_make_context(message), queue)

    async def test_executor_does_not_swallow_cancellation(self):
        adapter = MockAdapter(channel_name="test")
        adapter.send = AsyncMock(side_effect=asyncio.CancelledError("shutdown"))
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hi",
            **{CHANNEL_KEY: "test", RECIPIENT_KEY: "U1"},
        )
        queue = AsyncMock()

        with pytest.raises(asyncio.CancelledError):
            await executor.execute(_make_context(message), queue)

    async def test_executor_rejects_empty_optional_metadata(self):
        adapter = MockAdapter(channel_name="test")
        executor = GatewayPushExecutor(_make_router(adapter))
        message = _make_inbound_message(
            "hi",
            **{CHANNEL_KEY: "test", RECIPIENT_KEY: "U1", THREAD_KEY: ""},
        )
        queue = AsyncMock()

        with pytest.raises(PushRoutingError, match="thread_id"):
            await executor.execute(_make_context(message), queue)


class TestBuildPushAgentCard:
    def test_card_lists_registered_channels_alphabetically(self):
        router = _make_router(
            MockAdapter(channel_name="beta"),
            MockAdapter(channel_name="alpha"),
        )
        card = build_push_agent_card(router)

        skill_ids = [s.id for s in card.skills]
        assert skill_ids == ["send_alpha", "send_beta"]
        assert card.name == "a2a-gateway-push"
        assert list(card.default_input_modes) == ["text"]
        assert list(card.default_output_modes) == ["text"]

    def test_card_with_no_channels_has_empty_skills(self):
        router = _make_router()
        card = build_push_agent_card(router)
        assert list(card.skills) == []

    def test_push_path_constant_starts_with_slash(self):
        assert PUSH_PATH.startswith("/")
        assert not PUSH_PATH.endswith("/")

    def test_card_advertises_jsonrpc_interface_relative_by_default(self):
        router = _make_router(MockAdapter(channel_name="alpha"))
        card = build_push_agent_card(router)

        assert len(card.supported_interfaces) >= 1
        iface = card.supported_interfaces[0]
        assert PUSH_PATH in iface.url
        assert iface.protocol_version == "1.0"

    def test_card_advertises_absolute_url_when_base_url_set(self):
        router = _make_router(MockAdapter(channel_name="alpha"))
        card = build_push_agent_card(
            router, public_base_url="https://gateway.example.com"
        )

        iface = card.supported_interfaces[0]
        assert iface.url == f"https://gateway.example.com{PUSH_PATH}"

    def test_card_strips_trailing_slash_from_base_url(self):
        router = _make_router(MockAdapter(channel_name="alpha"))
        card = build_push_agent_card(
            router, public_base_url="https://gateway.example.com/"
        )

        iface = card.supported_interfaces[0]
        assert iface.url == f"https://gateway.example.com{PUSH_PATH}"
