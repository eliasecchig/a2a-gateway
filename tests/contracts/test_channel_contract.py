from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from gateway.channels.email import EmailAdapter
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.core.channel import ChannelAdapter
from gateway.core.types import InboundMessage


def _make_adapters() -> list[tuple[str, ChannelAdapter]]:
    adapters: list[tuple[str, ChannelAdapter]] = []

    adapters.append(("email", EmailAdapter()))

    adapters.append(
        (
            "whatsapp",
            WhatsAppAdapter(
                access_token="fake",
                phone_number_id="123",
                verify_token="tok",
            ),
        )
    )

    with patch("gateway.channels.slack.AsyncApp"):
        from gateway.channels.slack import SlackAdapter

        adapters.append(
            (
                "slack",
                SlackAdapter(bot_token="xoxb-fake", app_token="xapp-fake"),
            )
        )

    with patch(
        "gateway.channels.google_chat.service_account.Credentials.from_service_account_file"
    ):
        from gateway.channels.google_chat import GoogleChatAdapter

        adapters.append(
            (
                "google_chat",
                GoogleChatAdapter(service_account_path="fake.json"),
            )
        )

    return adapters


@pytest.fixture(params=["email", "whatsapp", "slack", "google_chat"])
def adapter(request: pytest.FixtureRequest) -> ChannelAdapter:
    adapters = _make_adapters()
    lookup = dict(adapters)
    return lookup[request.param]


class TestChannelContract:
    def test_is_channel_adapter(self, adapter: ChannelAdapter):
        assert isinstance(adapter, ChannelAdapter)

    def test_name_returns_string(self, adapter: ChannelAdapter):
        assert isinstance(adapter.name, str)
        assert len(adapter.name) > 0

    def test_has_start_method(self, adapter: ChannelAdapter):
        assert asyncio.iscoroutinefunction(adapter.start)

    def test_has_stop_method(self, adapter: ChannelAdapter):
        assert asyncio.iscoroutinefunction(adapter.stop)

    def test_has_send_method(self, adapter: ChannelAdapter):
        assert asyncio.iscoroutinefunction(adapter.send)

    def test_on_message_settable(self, adapter: ChannelAdapter):
        assert adapter.on_message is None
        adapter.on_message = AsyncMock()
        assert adapter.on_message is not None
        adapter.on_message = None

    @pytest.mark.asyncio
    async def test_dispatch_calls_on_message(self, adapter: ChannelAdapter):
        mock = AsyncMock()
        adapter.on_message = mock
        msg = InboundMessage(
            channel=adapter.name,
            sender_id="u1",
            sender_name="Test",
            text="hello",
        )
        await adapter.dispatch(msg)
        mock.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_dispatch_noop_when_no_callback(self, adapter: ChannelAdapter):
        adapter.on_message = None
        msg = InboundMessage(
            channel=adapter.name,
            sender_id="u1",
            sender_name="Test",
            text="hello",
        )
        await adapter.dispatch(msg)

    def test_email_default_name(self):
        adapter = EmailAdapter()
        assert adapter.name == "email"

    def test_email_custom_account_name(self):
        adapter = EmailAdapter(account_id="support")
        assert adapter.name == "email:support"

    def test_whatsapp_default_name(self):
        adapter = WhatsAppAdapter(access_token="x", phone_number_id="1", verify_token="t")
        assert adapter.name == "whatsapp"

    def test_whatsapp_custom_account_name(self):
        adapter = WhatsAppAdapter(
            access_token="x", phone_number_id="1", verify_token="t", account_id="biz"
        )
        assert adapter.name == "whatsapp:biz"

    def test_slack_default_name(self):
        with patch("gateway.channels.slack.AsyncApp"):
            from gateway.channels.slack import SlackAdapter

            adapter = SlackAdapter(bot_token="xoxb-x", app_token="xapp-x")
            assert adapter.name == "slack"

    def test_slack_custom_account_name(self):
        with patch("gateway.channels.slack.AsyncApp"):
            from gateway.channels.slack import SlackAdapter

            adapter = SlackAdapter(
                bot_token="xoxb-x", app_token="xapp-x", account_id="ws_a"
            )
            assert adapter.name == "slack:ws_a"

    def test_google_chat_default_name(self):
        with patch(
            "gateway.channels.google_chat.service_account.Credentials.from_service_account_file"
        ):
            from gateway.channels.google_chat import GoogleChatAdapter

            adapter = GoogleChatAdapter(service_account_path="fake.json")
            assert adapter.name == "google_chat"

    def test_google_chat_custom_account_name(self):
        with patch(
            "gateway.channels.google_chat.service_account.Credentials.from_service_account_file"
        ):
            from gateway.channels.google_chat import GoogleChatAdapter

            adapter = GoogleChatAdapter(
                service_account_path="fake.json", account_id="org1"
            )
            assert adapter.name == "google_chat:org1"
