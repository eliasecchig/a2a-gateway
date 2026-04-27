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
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionState:
    context_id: str | None = None
    task_id: str | None = None
    last_activity: float = field(default_factory=time.monotonic)


class SessionStore:
    def __init__(self, idle_timeout_minutes: float | None = None) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._idle_timeout: float | None = None
        if idle_timeout_minutes is not None:
            self._idle_timeout = idle_timeout_minutes * 60.0
        self._sweep_task: asyncio.Task | None = None

    def get(self, key: str) -> SessionState:
        if key not in self._sessions:
            self._sessions[key] = SessionState()
        return self._sessions[key]

    def update(
        self,
        key: str,
        context_id: str | None,
        task_id: str | None,
    ) -> None:
        session = self.get(key)
        session.context_id = context_id
        session.task_id = task_id
        session.last_activity = time.monotonic()

    def touch(self, key: str) -> None:
        session = self._sessions.get(key)
        if session:
            session.last_activity = time.monotonic()

    def remove(self, key: str) -> None:
        self._sessions.pop(key, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def start_sweep(self) -> None:
        if self._idle_timeout is not None and self._sweep_task is None:
            self._sweep_task = asyncio.create_task(
                self._sweep_loop(), name="session-sweep"
            )

    async def stop_sweep(self) -> None:
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweep_task
            self._sweep_task = None

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(60.0)
            self._sweep()

    def _sweep(self) -> None:
        if self._idle_timeout is None:
            return
        now = time.monotonic()
        expired = [
            key
            for key, session in self._sessions.items()
            if now - session.last_activity > self._idle_timeout
        ]
        for key in expired:
            logger.info("session expired: %s", key)
            del self._sessions[key]
