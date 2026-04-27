"""Real Telegram round-trip: send message → gateway → echo agent → verify.

Uses polling transport — no public URL needed.

Requires env vars:
  TELEGRAM_BOT_TOKEN — bot token from @BotFather
  TELEGRAM_TEST_CHAT — chat ID (your user ID or a group)
"""

from __future__ import annotations

import asyncio

import pytest
from telegram import Bot

from gateway.channels.telegram import TelegramAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.chunking import ChunkConfig
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


def _make_stack(echo_agent: str, **router_kwargs):
    env = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_TEST_CHAT")
    adapter = TelegramAdapter(bot_token=env["TELEGRAM_BOT_TOKEN"])
    client = A2AClient(echo_agent)
    router = Router(
        client,
        backoff_config=BackoffConfig(max_retries=0),
        **router_kwargs,
    )
    router.register(adapter)
    return adapter, client, env


async def _get_bot_text_replies(
    bot: Bot, keyword: str = "ECHO:", limit: int = 10
) -> list:
    updates = await bot.get_updates(limit=limit)
    return [
        u.message
        for u in updates
        if u.message
        and u.message.from_user
        and u.message.from_user.is_bot
        and u.message.text
        and keyword in u.message.text
    ]


@pytest.mark.live
class TestTelegramLive:
    async def test_full_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        chat_id = env["TELEGRAM_TEST_CHAT"]

        await adapter.start()
        try:
            bot = Bot(token=env["TELEGRAM_BOT_TOKEN"])
            await bot.send_message(chat_id=chat_id, text="live-test-ping")
            await asyncio.sleep(5.0)

            replies = await _get_bot_text_replies(bot)
            assert len(replies) >= 1, "No ECHO reply found"
            assert replies[0].text and "live-test-ping" in replies[0].text
        finally:
            await adapter.stop()
            await client.close()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        chat_id = env["TELEGRAM_TEST_CHAT"]

        await adapter.start()
        try:
            bot = Bot(token=env["TELEGRAM_BOT_TOKEN"])
            await bot.send_message(chat_id=chat_id, text="/file test-image")
            await asyncio.sleep(5.0)

            updates = await bot.get_updates(limit=10)
            doc_msgs = [
                u.message
                for u in updates
                if u.message
                and u.message.from_user
                and u.message.from_user.is_bot
                and u.message.document
            ]
            assert len(doc_msgs) >= 1, "No file attachment received from echo agent"
        finally:
            await adapter.stop()
            await client.close()

    async def test_long_message_chunking(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent, chunk_config=ChunkConfig())
        chat_id = env["TELEGRAM_TEST_CHAT"]

        await adapter.start()
        try:
            bot = Bot(token=env["TELEGRAM_BOT_TOKEN"])
            await bot.send_message(chat_id=chat_id, text="/long")
            await asyncio.sleep(8.0)

            replies = await _get_bot_text_replies(bot, keyword="Section")
            assert len(replies) >= 2, (
                f"Expected chunked response (>=2), got {len(replies)}"
            )
        finally:
            await adapter.stop()
            await client.close()

    async def test_unicode_message(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        chat_id = env["TELEGRAM_TEST_CHAT"]

        await adapter.start()
        try:
            bot = Bot(token=env["TELEGRAM_BOT_TOKEN"])
            await bot.send_message(chat_id=chat_id, text="/unicode")
            await asyncio.sleep(5.0)

            replies = await _get_bot_text_replies(bot)
            assert len(replies) >= 1, "No unicode response found"
            text = replies[0].text or ""
            assert "\U0001f680" in text, f"Rocket emoji missing: {text[:100]}"
            assert "你好" in text, f"CJK missing: {text[:100]}"
        finally:
            await adapter.stop()
            await client.close()

    async def test_session_continuity(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        chat_id = env["TELEGRAM_TEST_CHAT"]

        await adapter.start()
        try:
            bot = Bot(token=env["TELEGRAM_BOT_TOKEN"])
            await bot.send_message(chat_id=chat_id, text="first-message")
            await asyncio.sleep(4.0)
            await bot.send_message(chat_id=chat_id, text="second-message")
            await asyncio.sleep(4.0)

            replies = await _get_bot_text_replies(bot)
            second = [m for m in replies if m.text and "second-message" in m.text]
            assert len(second) >= 1, (
                "Second message reply not found — session may have broken"
            )
        finally:
            await adapter.stop()
            await client.close()
