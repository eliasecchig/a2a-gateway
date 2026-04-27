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
import contextlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.core.channel import ChannelAdapter

logger = logging.getLogger(__name__)


class TypingIndicator:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._active: dict[str, asyncio.Task[None]] = {}

    async def start(
        self,
        adapter: ChannelAdapter,
        session_key: str,
        conversation_id: str,
        thread_id: str | None = None,
    ) -> None:
        if session_key in self._active:
            return
        task = asyncio.create_task(
            self._typing_loop(adapter, session_key, conversation_id, thread_id),
            name=f"typing-{session_key}",
        )
        self._active[session_key] = task

    async def stop(self, session_key: str) -> None:
        task = self._active.pop(session_key, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def stop_all(self) -> None:
        keys = list(self._active.keys())
        for key in keys:
            await self.stop(key)

    async def _typing_loop(
        self,
        adapter: ChannelAdapter,
        session_key: str,
        conversation_id: str,
        thread_id: str | None,
    ) -> None:
        interval = min(5.0, self._ttl)
        start = time.monotonic()
        try:
            while (time.monotonic() - start) < self._ttl:
                try:
                    await adapter.send_typing(conversation_id, thread_id)
                except (OSError, ConnectionError, TimeoutError):
                    logger.warning("send_typing failed for %s", session_key)
                except Exception:
                    logger.warning("send_typing error for %s", session_key, exc_info=True)
                    break
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        finally:
            self._active.pop(session_key, None)
