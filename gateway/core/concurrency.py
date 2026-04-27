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
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.config import ConcurrencyConfig
    from gateway.core.types import InboundMessage

_MAX_SEMAPHORES = 10_000


class ConcurrencyLimiter:
    def __init__(self, config: ConcurrencyConfig) -> None:
        self._max = config.max_concurrent
        self._per = config.per
        self._semaphores: OrderedDict[str, asyncio.Semaphore] = OrderedDict()
        self._global_sem = asyncio.Semaphore(self._max)

    def resolve_key(self, msg: InboundMessage) -> str:
        if self._per == "global":
            return "__global__"
        if self._per == "user":
            return msg.sender_id
        return msg.conversation_id or msg.sender_id

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[None]:
        if key == "__global__":
            sem = self._global_sem
        else:
            if key not in self._semaphores:
                if len(self._semaphores) >= _MAX_SEMAPHORES:
                    self._semaphores.popitem(last=False)
                self._semaphores[key] = asyncio.Semaphore(self._max)
            else:
                self._semaphores.move_to_end(key)
            sem = self._semaphores[key]
        async with sem:
            yield
