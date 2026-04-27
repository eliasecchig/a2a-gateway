"""Real Telegram round-trip: send message → gateway → echo agent → verify reply.

Uses polling transport — no public URL needed.

Requires env vars:
  TELEGRAM_BOT_TOKEN  — bot token from @BotFather
  TELEGRAM_TEST_CHAT  — chat ID to send test messages to (your user ID or group)
"""

from __future__ import annotations

import asyncio

import pytest
from telegram import Bot

from gateway.channels.telegram import TelegramAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


@pytest.mark.live
class TestTelegramLive:
    async def test_full_roundtrip(self, echo_agent: str):
        env = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_TEST_CHAT")
        bot_token = env["TELEGRAM_BOT_TOKEN"]
        chat_id = env["TELEGRAM_TEST_CHAT"]

        adapter = TelegramAdapter(bot_token=bot_token)
        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        await adapter.start()

        try:
            bot = Bot(token=bot_token)
            test_text = "live-test-ping"
            await bot.send_message(chat_id=chat_id, text=test_text)

            for _ in range(20):
                await asyncio.sleep(0.5)
                if len(router._sessions) > 0:
                    break

            await asyncio.sleep(3.0)

            updates = await bot.get_updates(limit=10)
            bot_messages = [
                u.message
                for u in updates
                if u.message
                and u.message.from_user
                and u.message.from_user.is_bot
                and u.message.text
                and "ECHO:" in u.message.text
            ]

            if not bot_messages:
                await bot.send_message(chat_id=chat_id, text="noop")
                recent = await bot.get_updates(
                    offset=updates[-1].update_id + 1 if updates else None,
                    limit=10,
                )
                bot_messages = [
                    u.message
                    for u in recent
                    if u.message
                    and u.message.from_user
                    and u.message.from_user.is_bot
                    and u.message.text
                    and "ECHO:" in u.message.text
                ]

            assert len(bot_messages) >= 1, (
                f"No ECHO reply found. Recent updates: "
                f"{[u.message.text[:60] if u.message and u.message.text else '' for u in updates]}"
            )
            assert test_text in bot_messages[0].text

        finally:
            await adapter.stop()
            await client.close()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        env = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_TEST_CHAT")
        bot_token = env["TELEGRAM_BOT_TOKEN"]
        chat_id = env["TELEGRAM_TEST_CHAT"]

        adapter = TelegramAdapter(bot_token=bot_token)
        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        await adapter.start()

        try:
            bot = Bot(token=bot_token)
            await bot.send_message(chat_id=chat_id, text="/file test-image")

            await asyncio.sleep(5.0)

            updates = await bot.get_updates(limit=10)
            doc_messages = [
                u.message
                for u in updates
                if u.message
                and u.message.from_user
                and u.message.from_user.is_bot
                and u.message.document
            ]
            assert len(doc_messages) >= 1, "No file attachment received from echo agent"

        finally:
            await adapter.stop()
            await client.close()
