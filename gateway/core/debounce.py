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

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from gateway.core.types import InboundMessage

logger = logging.getLogger(__name__)


@dataclass
class DebounceConfig:
    window_ms: int = 500
    max_messages: int = 10
    max_chars: int = 4000


@dataclass
class _BufferEntry:
    messages: list[InboundMessage] = field(default_factory=list)
    total_chars: int = 0
    timer: asyncio.TimerHandle | None = None


class Debouncer:
    def __init__(
        self,
        config: DebounceConfig,
        flush_callback: Callable[[InboundMessage], Awaitable[None]],
    ) -> None:
        self._config = config
        self._flush_callback = flush_callback
        self._buffers: dict[str, _BufferEntry] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def _key(self, msg: InboundMessage) -> str:
        return f"{msg.channel}:{msg.conversation_id or msg.sender_id}"

    async def submit(self, msg: InboundMessage) -> None:
        key = self._key(msg)
        buf = self._buffers.get(key)

        if buf is None:
            buf = _BufferEntry()
            self._buffers[key] = buf

        buf.messages.append(msg)
        buf.total_chars += len(msg.text)

        if buf.timer is not None:
            buf.timer.cancel()

        if (
            len(buf.messages) >= self._config.max_messages
            or buf.total_chars >= self._config.max_chars
        ):
            await self._flush(key)
            return

        loop = self._get_loop()
        delay = self._config.window_ms / 1000.0
        buf.timer = loop.call_later(
            delay, lambda k=key: asyncio.ensure_future(self._safe_flush(k))
        )

    async def _safe_flush(self, key: str) -> None:
        try:
            await self._flush(key)
        except Exception:
            logger.exception("debounce flush failed for key=%s", key)

    async def _flush(self, key: str) -> None:
        buf = self._buffers.pop(key, None)
        if buf is None or not buf.messages:
            return

        if buf.timer is not None:
            buf.timer.cancel()

        first = buf.messages[0]
        coalesced_text = "\n".join(m.text for m in buf.messages)

        all_attachments = []
        for m in buf.messages:
            all_attachments.extend(m.attachments)

        coalesced = InboundMessage(
            channel=first.channel,
            sender_id=first.sender_id,
            sender_name=first.sender_name,
            text=coalesced_text,
            thread_id=first.thread_id,
            conversation_id=first.conversation_id,
            raw_event=first.raw_event,
            is_group=first.is_group,
            is_mention=any(m.is_mention for m in buf.messages),
            attachments=all_attachments,
        )

        logger.debug("debounce: flushing %d messages for key=%s", len(buf.messages), key)
        await self._flush_callback(coalesced)

    async def close(self) -> None:
        keys = list(self._buffers.keys())
        for key in keys:
            await self._flush(key)
