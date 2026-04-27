"""Real Discord round-trip: send message → gateway → echo agent → verify.

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
from gateway.core.chunking import ChunkConfig
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from tests.live.conftest import require_env


def _make_stack(echo_agent: str, **router_kwargs):
    env = require_env("DISCORD_BOT_TOKEN", "DISCORD_TEST_CHANNEL")
    adapter = DiscordAdapter(bot_token=env["DISCORD_BOT_TOKEN"])
    client = A2AClient(echo_agent)
    router = Router(
        client,
        backoff_config=BackoffConfig(max_retries=0),
        **router_kwargs,
    )
    router.register(adapter)
    return adapter, client, env


async def _wait_ready(adapter: DiscordAdapter, timeout: float = 15.0):
    for _ in range(int(timeout / 0.5)):
        await asyncio.sleep(0.5)
        if adapter._client.is_ready():
            return
    pytest.fail("Discord client did not become ready")


async def _get_channel(adapter: DiscordAdapter, channel_id: int):
    channel = adapter._client.get_channel(channel_id)
    assert channel and isinstance(channel, discord.abc.Messageable), (
        f"Channel {channel_id} not found or not messageable"
    )
    return channel


async def _send_and_collect(
    adapter: DiscordAdapter,
    channel,
    text: str,
    wait_s: float = 5.0,
    limit: int = 10,
) -> list[discord.Message]:
    await channel.send(text)
    await asyncio.sleep(wait_s)
    return [m async for m in channel.history(limit=limit)]


@pytest.mark.live
class TestDiscordLive:
    async def test_full_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        await adapter.start()
        try:
            await _wait_ready(adapter)
            channel = await _get_channel(adapter, channel_id)

            history = await _send_and_collect(adapter, channel, "live-test-ping")
            bot_replies = [
                m
                for m in history
                if m.author == adapter._client.user and m.content and "ECHO:" in m.content
            ]
            assert len(bot_replies) >= 1, (
                f"No ECHO reply found. Messages: "
                f"{[m.content[:60] for m in history if m.content]}"
            )
            assert "live-test-ping" in bot_replies[0].content
        finally:
            await adapter.stop()
            await client.close()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        await adapter.start()
        try:
            await _wait_ready(adapter)
            channel = await _get_channel(adapter, channel_id)

            history = await _send_and_collect(adapter, channel, "/file test-image")
            file_msgs = [
                m
                for m in history
                if m.author == adapter._client.user and len(m.attachments) > 0
            ]
            assert len(file_msgs) >= 1, "No file attachment received from echo agent"
        finally:
            await adapter.stop()
            await client.close()

    async def test_long_message_chunking(self, echo_agent: str):
        """Discord has a 2000 char limit — /long (~5000 chars) should
        produce >=3 chunks."""
        adapter, client, env = _make_stack(echo_agent, chunk_config=ChunkConfig())
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        await adapter.start()
        try:
            await _wait_ready(adapter)
            channel = await _get_channel(adapter, channel_id)

            history = await _send_and_collect(
                adapter, channel, "/long", wait_s=8.0, limit=20
            )
            bot_msgs = [
                m
                for m in history
                if m.author == adapter._client.user
                and m.content
                and "Section" in m.content
            ]
            assert len(bot_msgs) >= 3, (
                f"Expected >=3 chunks (2000 char limit), got {len(bot_msgs)}"
            )
        finally:
            await adapter.stop()
            await client.close()

    async def test_unicode_message(self, echo_agent: str):
        adapter, client, env = _make_stack(echo_agent)
        channel_id = int(env["DISCORD_TEST_CHANNEL"])

        await adapter.start()
        try:
            await _wait_ready(adapter)
            channel = await _get_channel(adapter, channel_id)

            history = await _send_and_collect(adapter, channel, "/unicode")
            bot_msgs = [
                m
                for m in history
                if m.author == adapter._client.user and m.content and "ECHO:" in m.content
            ]
            assert len(bot_msgs) >= 1, "No unicode response found"
            text = bot_msgs[0].content
            assert "\U0001f680" in text, f"Rocket emoji missing: {text[:100]}"
            assert "你好" in text, f"CJK missing: {text[:100]}"
            assert "مرحبا" in text, f"Arabic missing: {text[:100]}"
        finally:
            await adapter.stop()
            await client.close()
