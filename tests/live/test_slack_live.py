"""Real Slack round-trip: post message → gateway → echo agent → verify reply.

Requires env vars:
  SLACK_BOT_TOKEN   — xoxb-* bot token
  SLACK_APP_TOKEN   — xapp-* for Socket Mode
  SLACK_TEST_CHANNEL — channel ID to post test messages in
"""

from __future__ import annotations

import asyncio

import pytest
from slack_sdk.web.async_client import AsyncWebClient

from gateway.channels.slack import SlackAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


@pytest.mark.live
class TestSlackLive:
    async def test_full_roundtrip(self, echo_agent: str):
        env = require_env("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_TEST_CHANNEL")
        bot_token = env["SLACK_BOT_TOKEN"]
        app_token = env["SLACK_APP_TOKEN"]
        channel = env["SLACK_TEST_CHANNEL"]

        adapter = SlackAdapter(bot_token=bot_token, app_token=app_token)
        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        await adapter.start()

        try:
            api = AsyncWebClient(token=bot_token)
            test_text = "live-test-ping"
            await api.chat_postMessage(channel=channel, text=test_text)

            for _ in range(20):
                await asyncio.sleep(0.5)
                if adapter._bot_user_id and len(router._sessions) > 0:
                    break

            await asyncio.sleep(3.0)

            history = await api.conversations_history(channel=channel, limit=5)
            messages = history.get("messages", [])
            bot_replies = [
                m for m in messages if m.get("bot_id") and "ECHO:" in m.get("text", "")
            ]
            assert len(bot_replies) >= 1, (
                f"No ECHO reply found in channel. Recent messages: "
                f"{[m.get('text', '')[:60] for m in messages]}"
            )
            assert test_text in bot_replies[0]["text"]

        finally:
            await adapter.stop()
            await client.close()
