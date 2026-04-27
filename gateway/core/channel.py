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

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from gateway.core.types import InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)

OnMessageCallback = Callable[[InboundMessage], Awaitable[None]]


class ChannelAdapter(ABC):
    """Base class for all channel adapters.

    Subclasses implement channel-specific logic for receiving and sending
    messages.  The router sets ``on_message`` before calling ``start()``.
    """

    channel_type: str = ""

    def __init__(self, *, account_id: str = "default") -> None:
        self.on_message: OnMessageCallback | None = None
        self._account_id = account_id

    @property
    def name(self) -> str:
        if self._account_id == "default":
            return self.channel_type
        return f"{self.channel_type}:{self._account_id}"

    @property
    def supports_editing(self) -> bool:
        return False

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> str | None: ...

    async def edit_message(  # noqa: B027
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        pass

    async def send_typing(  # noqa: B027
        self,
        conversation_id: str,
        thread_id: str | None = None,
    ) -> None:
        pass

    async def send_ack(  # noqa: B027
        self,
        message: InboundMessage,
        config: dict | None = None,
    ) -> None:
        pass

    async def dispatch(self, message: InboundMessage) -> None:
        if self.on_message is not None:
            await self.on_message(message)
        else:
            logger.warning(
                "message from %s dropped: on_message not set", self.name
            )
