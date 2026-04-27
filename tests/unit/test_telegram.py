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

from gateway.channels.telegram import TelegramAdapter
from gateway.config import TelegramAccountConfig, load_config
from gateway.core.channel import ChannelAdapter
from gateway.core.types import InboundMessage, OutboundMessage


class TestTelegramAdapter:
    def test_is_channel_adapter(self):
        adapter = TelegramAdapter(bot_token="test-token")
        assert isinstance(adapter, ChannelAdapter)

    def test_default_name(self):
        adapter = TelegramAdapter(bot_token="test-token")
        assert adapter.name == "telegram"

    def test_custom_account_name(self):
        adapter = TelegramAdapter(bot_token="test-token", account_id="bot_a")
        assert adapter.name == "telegram:bot_a"

    def test_supports_editing(self):
        adapter = TelegramAdapter(bot_token="test-token")
        assert adapter.supports_editing is True

    async def test_send_text(self):
        adapter = TelegramAdapter(bot_token="test-token")
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 42
        mock_bot.send_message.return_value = mock_sent
        adapter._bot = mock_bot

        msg = OutboundMessage(
            channel="telegram",
            recipient_id="123",
            text="hello",
            conversation_id="456",
        )
        result = await adapter.send(msg)

        mock_bot.send_message.assert_called_once_with(
            chat_id="456", text="hello", reply_to_message_id=None
        )
        assert result == "42"

    async def test_send_with_thread(self):
        adapter = TelegramAdapter(bot_token="test-token")
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 43
        mock_bot.send_message.return_value = mock_sent
        adapter._bot = mock_bot

        msg = OutboundMessage(
            channel="telegram",
            recipient_id="123",
            text="reply",
            conversation_id="456",
            thread_id="99",
        )
        await adapter.send(msg)

        mock_bot.send_message.assert_called_once_with(
            chat_id="456", text="reply", reply_to_message_id=99
        )

    async def test_edit_message(self):
        adapter = TelegramAdapter(bot_token="test-token")
        mock_bot = AsyncMock()
        adapter._bot = mock_bot

        await adapter.edit_message("42", "456", "updated text")

        mock_bot.edit_message_text.assert_called_once_with(
            chat_id="456", message_id=42, text="updated text"
        )

    async def test_send_typing(self):
        adapter = TelegramAdapter(bot_token="test-token")
        mock_bot = AsyncMock()
        adapter._bot = mock_bot

        await adapter.send_typing("456")

        mock_bot.send_chat_action.assert_called_once()

    async def test_send_no_bot_returns_none(self):
        adapter = TelegramAdapter(bot_token="test-token")
        msg = OutboundMessage(
            channel="telegram",
            recipient_id="123",
            text="hello",
        )
        result = await adapter.send(msg)
        assert result is None

    async def test_send_ack_is_noop(self):
        adapter = TelegramAdapter(bot_token="test-token")
        msg = InboundMessage(
            channel="telegram",
            sender_id="123",
            sender_name="User",
            text="hi",
            raw_event={},
        )
        await adapter.send_ack(msg)


class TestTelegramConfig:
    def test_telegram_account_config_defaults(self):
        cfg = TelegramAccountConfig()
        assert cfg.enabled is False
        assert cfg.bot_token == ""
        assert cfg.features == {}

    def test_telegram_parsed_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
channels:
  telegram:
    enabled: true
    bot_token: "123456:ABC"
    features:
      typing: true
"""
        )
        cfg = load_config(config_file)
        assert len(cfg.telegram_accounts) == 1
        assert cfg.telegram_accounts[0].bot_token == "123456:ABC"
        assert cfg.telegram_accounts[0].features == {"typing": True}

    def test_telegram_env_override(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("port: 8000\n")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
        cfg = load_config(config_file)
        assert len(cfg.telegram_accounts) == 1
        assert cfg.telegram_accounts[0].bot_token == "env-token"

    def test_telegram_channel_limit(self):
        from gateway.core.chunking import CHANNEL_LIMITS

        assert CHANNEL_LIMITS["telegram"] == 4096
