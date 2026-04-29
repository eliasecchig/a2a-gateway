from __future__ import annotations

import pytest

from gateway.core.simple_channel import SimpleChannel
from gateway.core.types import InboundMessage, OutboundMessage


class StubChannel(SimpleChannel):
    channel_type = "stub"

    def __init__(self, account_id: str = "default") -> None:
        super().__init__(account_id=account_id)
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> str | None:
        self.sent.append(message)
        return "msg-1"


class TestSimpleChannel:
    def test_is_channel_adapter(self):
        from gateway.core.channel import ChannelAdapter

        ch = StubChannel()
        assert isinstance(ch, ChannelAdapter)

    def test_channel_type(self):
        ch = StubChannel()
        assert ch.channel_type == "stub"

    def test_name_default_account(self):
        ch = StubChannel()
        assert ch.name == "stub"

    def test_name_custom_account(self):
        ch = StubChannel(account_id="prod")
        assert ch.name == "stub:prod"

    async def test_start_is_noop(self):
        ch = StubChannel()
        await ch.start()

    async def test_stop_is_noop(self):
        ch = StubChannel()
        await ch.stop()

    async def test_send_delegates_to_subclass(self):
        ch = StubChannel()
        msg = OutboundMessage(
            channel="stub",
            recipient_id="user-1",
            text="hello",
        )
        result = await ch.send(msg)
        assert result == "msg-1"
        assert ch.sent == [msg]

    async def test_dispatch_calls_on_message(self):
        from unittest.mock import AsyncMock

        ch = StubChannel()
        mock = AsyncMock()
        ch.on_message = mock
        inbound = InboundMessage(
            channel="stub",
            sender_id="u1",
            sender_name="Alice",
            text="hi",
        )
        await ch.dispatch(inbound)
        mock.assert_called_once_with(inbound)

    async def test_send_raises_not_implemented_on_base(self):
        ch = SimpleChannel()
        msg = OutboundMessage(
            channel="test",
            recipient_id="user-1",
            text="hello",
        )
        with pytest.raises(NotImplementedError):
            await ch.send(msg)
