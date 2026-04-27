# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord

from gateway.channels.discord import DiscordAdapter
from gateway.config import DiscordAccountConfig, load_config
from gateway.core.channel import ChannelAdapter
from gateway.core.types import OutboundMessage


class TestDiscordAdapter:
    def test_is_channel_adapter(self):
        adapter = DiscordAdapter(bot_token="test-token")
        assert isinstance(adapter, ChannelAdapter)

    def test_default_name(self):
        adapter = DiscordAdapter(bot_token="test-token")
        assert adapter.name == "discord"

    def test_custom_account_name(self):
        adapter = DiscordAdapter(bot_token="test-token", account_id="server_a")
        assert adapter.name == "discord:server_a"

    def test_supports_editing(self):
        adapter = DiscordAdapter(bot_token="test-token")
        assert adapter.supports_editing is True

    async def test_send_text(self):
        adapter = DiscordAdapter(bot_token="test-token")
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_sent = MagicMock()
        mock_sent.id = 12345
        mock_channel.send.return_value = mock_sent

        adapter._client.get_channel = MagicMock(return_value=mock_channel)

        msg = OutboundMessage(
            channel="discord",
            recipient_id="999",
            text="hello",
            conversation_id="999",
        )
        result = await adapter.send(msg)

        mock_channel.send.assert_called_once_with("hello")
        assert result == "12345"

    async def test_send_no_channel_returns_none(self):
        adapter = DiscordAdapter(bot_token="test-token")
        adapter._client.get_channel = MagicMock(return_value=None)

        msg = OutboundMessage(
            channel="discord",
            recipient_id="999",
            text="hello",
            conversation_id="999",
        )
        result = await adapter.send(msg)
        assert result is None

    async def test_edit_message(self):
        adapter = DiscordAdapter(bot_token="test-token")
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_msg = AsyncMock()
        mock_channel.fetch_message.return_value = mock_msg
        adapter._client.get_channel = MagicMock(return_value=mock_channel)

        await adapter.edit_message("12345", "999", "updated text")

        mock_channel.fetch_message.assert_called_once_with(12345)
        mock_msg.edit.assert_called_once_with(content="updated text")

    async def test_send_typing(self):
        adapter = DiscordAdapter(bot_token="test-token")
        mock_channel = AsyncMock(spec=discord.TextChannel)
        adapter._client.get_channel = MagicMock(return_value=mock_channel)

        await adapter.send_typing("999")

        mock_channel.typing.assert_called_once()

    async def test_stop_closes_client(self):
        adapter = DiscordAdapter(bot_token="test-token")
        adapter._client.close = AsyncMock()
        await adapter.stop()
        adapter._client.close.assert_called_once()


class TestDiscordConfig:
    def test_discord_account_config_defaults(self):
        cfg = DiscordAccountConfig()
        assert cfg.enabled is False
        assert cfg.bot_token == ""
        assert cfg.features == {}

    def test_discord_parsed_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
channels:
  discord:
    enabled: true
    bot_token: "discord-test-token"
    features:
      typing: true
"""
        )
        cfg = load_config(config_file)
        assert len(cfg.discord_accounts) == 1
        assert cfg.discord_accounts[0].bot_token == "discord-test-token"
        assert cfg.discord_accounts[0].features == {"typing": True}

    def test_discord_env_override(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("port: 8000\n")
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-dc-token")
        cfg = load_config(config_file)
        assert len(cfg.discord_accounts) == 1
        assert cfg.discord_accounts[0].bot_token == "env-dc-token"

    def test_discord_channel_limit(self):
        from gateway.core.chunking import CHANNEL_LIMITS

        assert CHANNEL_LIMITS["discord"] == 2000
