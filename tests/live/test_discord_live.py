"""Real Discord round-trip: send message → gateway → echo agent → verify reply.

Uses WebSocket transport — no public URL needed.

Requires env vars:
  DISCORD_BOT_TOKEN    — bot token from Discord Developer Portal
  DISCORD_TEST_CHANNEL — channel ID to post test messages in
"""

from __future__ import annotations

import asyncio

import discord
import pytest

from gateway.channels.discord import DiscordAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


@pytest.mark.live
class TestDiscordLive:
    async def test_full_roundtrip(self, echo_agent: str):
        env = require_env("DISCORD_BOT_TOKEN", "DISCORD_TEST_CHANNEL")
        bot_token = env["DISCORD_BOT_TOKEN"]
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        adapter = DiscordAdapter(bot_token=bot_token)
        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        await adapter.start()

        try:
            for _ in range(30):
                await asyncio.sleep(0.5)
                if adapter._client.is_ready():
                    break
            else:
                pytest.fail("Discord client did not become ready within 15s")

            channel = adapter._client.get_channel(channel_id)
            assert channel and isinstance(channel, discord.abc.Messageable), (
                f"Channel {channel_id} not found or not messageable"
            )

            test_text = "live-test-ping"
            await channel.send(test_text)

            for _ in range(20):
                await asyncio.sleep(0.5)
                if len(router._sessions) > 0:
                    break

            await asyncio.sleep(3.0)

            history = [m async for m in channel.history(limit=10)]
            bot_replies = [
                m
                for m in history
                if m.author == adapter._client.user and m.content and "ECHO:" in m.content
            ]
            assert len(bot_replies) >= 1, (
                f"No ECHO reply found in channel. Recent messages: "
                f"{[m.content[:60] for m in history if m.content]}"
            )
            assert test_text in bot_replies[0].content

        finally:
            await adapter.stop()
            await client.close()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        env = require_env("DISCORD_BOT_TOKEN", "DISCORD_TEST_CHANNEL")
        bot_token = env["DISCORD_BOT_TOKEN"]
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        adapter = DiscordAdapter(bot_token=bot_token)
        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        await adapter.start()

        try:
            for _ in range(30):
                await asyncio.sleep(0.5)
                if adapter._client.is_ready():
                    break

            channel = adapter._client.get_channel(channel_id)
            assert channel and isinstance(channel, discord.abc.Messageable)

            await channel.send("/file test-image")

            await asyncio.sleep(5.0)

            history = [m async for m in channel.history(limit=10)]
            file_messages = [
                m
                for m in history
                if m.author == adapter._client.user and len(m.attachments) > 0
            ]
            assert len(file_messages) >= 1, "No file attachment received from echo agent"

        finally:
            await adapter.stop()
            await client.close()
