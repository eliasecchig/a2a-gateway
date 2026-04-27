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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InteractionCallback:
    action_id: str
    value: str
    user_id: str
    channel: str
    conversation_id: str
    thread_id: str | None = None


class InteractionRouter:
    def __init__(
        self,
        on_interaction: Callable[[InteractionCallback], Awaitable[None]] | None = None,
    ) -> None:
        self._handler = on_interaction

    async def handle(self, callback: InteractionCallback) -> None:
        if self._handler:
            await self._handler(callback)
        else:
            logger.debug(
                "interaction callback received but no handler: %s",
                callback.action_id,
            )
