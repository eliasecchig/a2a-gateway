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

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterHealth:
    connected: bool = False
    last_heartbeat: float = 0.0
    error: str | None = None


class HealthMonitor:
    def __init__(self, stale_timeout_seconds: float = 300.0) -> None:
        self._stale_timeout = stale_timeout_seconds
        self._adapters: dict[str, AdapterHealth] = {}

    def record_connect(self, adapter_name: str) -> None:
        health = self._adapters.setdefault(adapter_name, AdapterHealth())
        health.connected = True
        health.last_heartbeat = time.monotonic()
        health.error = None

    def record_disconnect(self, adapter_name: str) -> None:
        health = self._adapters.get(adapter_name)
        if health:
            health.connected = False

    def record_heartbeat(self, adapter_name: str) -> None:
        health = self._adapters.get(adapter_name)
        if health:
            health.last_heartbeat = time.monotonic()

    def record_error(self, adapter_name: str, error: str) -> None:
        health = self._adapters.get(adapter_name)
        if health:
            health.error = error

    def is_adapter_healthy(self, adapter_name: str) -> bool:
        health = self._adapters.get(adapter_name)
        if not health or not health.connected:
            return False
        if health.last_heartbeat == 0.0:
            return True
        elapsed = time.monotonic() - health.last_heartbeat
        return elapsed <= self._stale_timeout

    def is_ready(self) -> bool:
        return any(self.is_adapter_healthy(name) for name in self._adapters)

    def get_status(self) -> dict[str, Any]:
        now = time.monotonic()
        adapters: dict[str, Any] = {}
        for name, health in self._adapters.items():
            elapsed = now - health.last_heartbeat if health.last_heartbeat else None
            adapters[name] = {
                "connected": health.connected,
                "healthy": self.is_adapter_healthy(name),
                "last_heartbeat_seconds_ago": (
                    round(elapsed, 1) if elapsed is not None else None
                ),
                "error": health.error,
            }
        return {
            "ready": self.is_ready(),
            "adapters": adapters,
        }
