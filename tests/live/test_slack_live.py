"""Real Slack round-trip: post message → gateway → echo agent → verify reply.

Requires env vars:
  SLACK_BOT_TOKEN    — xoxb-* bot token
  SLACK_APP_TOKEN    — xapp-* for Socket Mode
  SLACK_TEST_CHANNEL — channel ID to post test messages in
"""

from __future__ import annotations

import asyncio

import pytest
from slack_sdk.web.async_client import AsyncWebClient

from gateway.channels.slack import SlackAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.chunking import ChunkConfig
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


def _make_stack(echo_agent: str, **router_kwargs):
    env = require_env("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_TEST_CHANNEL")
    adapter = SlackAdapter(
        bot_token=env["SLACK_BOT_TOKEN"],
        app_token=env["SLACK_APP_TOKEN"],
    )
    client = A2AClient(echo_agent)
    router = Router(
        client,
        backoff_config=BackoffConfig(max_retries=0),
        **router_kwargs,
    )
    router.register(adapter)
    return adapter, client, env


async def _send_and_collect(
    api: AsyncWebClient,
    channel: str,
    text: str,
    wait_s: float = 5.0,
) -> list[dict]:
    await api.chat_postMessage(channel=channel, text=text)
    await asyncio.sleep(wait_s)
    history = await api.conversations_history(channel=channel, limit=15)
    return history.get("messages", [])


@pytest.mark.live
class TestSlackLive:
    async def test_full_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel = env["SLACK_TEST_CHANNEL"]

        await adapter.start()
        try:
            api = AsyncWebClient(token=env["SLACK_BOT_TOKEN"])
            messages = await _send_and_collect(api, channel, "live-test-ping")
            bot_replies = [
                m for m in messages if m.get("bot_id") and "ECHO:" in m.get("text", "")
            ]
            assert len(bot_replies) >= 1, (
                f"No ECHO reply found. Messages: "
                f"{[m.get('text', '')[:60] for m in messages]}"
            )
            assert "live-test-ping" in bot_replies[0]["text"]
        finally:
            await adapter.stop()
            await client.close()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel = env["SLACK_TEST_CHANNEL"]

        await adapter.start()
        try:
            api = AsyncWebClient(token=env["SLACK_BOT_TOKEN"])
            messages = await _send_and_collect(
                api, channel, "/file test-image", wait_s=8.0
            )
            file_msgs = [m for m in messages if m.get("bot_id") and m.get("files")]
            assert len(file_msgs) >= 1, "No file attachment received from echo agent"
            assert file_msgs[0]["files"][0]["name"] == "test.png"
        finally:
            await adapter.stop()
            await client.close()

    async def test_long_message_chunking(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent, chunk_config=ChunkConfig())
        channel = env["SLACK_TEST_CHANNEL"]

        await adapter.start()
        try:
            api = AsyncWebClient(token=env["SLACK_BOT_TOKEN"])
            messages = await _send_and_collect(api, channel, "/long", wait_s=8.0)
            bot_msgs = [
                m for m in messages if m.get("bot_id") and "Section" in m.get("text", "")
            ]
            assert len(bot_msgs) >= 2, (
                f"Expected chunked response (>=2 messages), got {len(bot_msgs)}"
            )
        finally:
            await adapter.stop()
            await client.close()

    async def test_markdown_formatting(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel = env["SLACK_TEST_CHANNEL"]

        await adapter.start()
        try:
            api = AsyncWebClient(token=env["SLACK_BOT_TOKEN"])
            messages = await _send_and_collect(api, channel, "/markdown", wait_s=6.0)
            bot_msgs = [
                m
                for m in messages
                if m.get("bot_id")
                and ("bold" in m.get("text", "") or "hello" in m.get("text", ""))
            ]
            assert len(bot_msgs) >= 1, "No markdown response found"
            text = bot_msgs[0]["text"]
            assert "*bold text*" in text, (
                f"Expected Slack bold (*text*), got: {text[:200]}"
            )
            assert "```" in text, "Code block should be preserved"
        finally:
            await adapter.stop()
            await client.close()
