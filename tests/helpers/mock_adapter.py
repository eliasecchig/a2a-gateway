from __future__ import annotations

from gateway.core.channel import ChannelAdapter
from gateway.core.types import OutboundMessage


class MockAdapter(ChannelAdapter):
    channel_type = "test"

    def __init__(self, channel_name: str = "test", account_id: str = "default") -> None:
        self.channel_type = channel_name
        super().__init__(account_id=account_id)
        self.sent: list[OutboundMessage] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, message: OutboundMessage) -> str | None:
        self.sent.append(message)
        return None
