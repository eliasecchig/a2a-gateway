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
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    OSError,
    ConnectionError,
    TimeoutError,
)


@dataclass
class RateLimitConfig:
    max_requests: int = 60
    window_seconds: float = 60.0


@dataclass
class BackoffConfig:
    initial: float = 1.0
    factor: float = 2.0
    max_delay: float = 300.0
    jitter_pct: float = 0.10
    max_retries: int = 5


class RateLimiter:
    def __init__(self, config: RateLimitConfig) -> None:
        self._max = config.max_requests
        self._window = config.window_seconds
        self._counts: dict[str, int] = {}
        self._window_start: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str = "__global__") -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                start = self._window_start.get(key, 0.0)

                if now - start >= self._window:
                    self._counts[key] = 0
                    self._window_start[key] = now

                if self._counts.get(key, 0) < self._max:
                    self._counts[key] = self._counts.get(key, 0) + 1
                    return

                wait = self._window - (now - start)

            logger.warning(
                "rate limit hit for key=%s, waiting %.1fs", key, wait
            )
            await asyncio.sleep(max(wait, 0))


class RetryWithBackoff:
    def __init__(
        self,
        config: BackoffConfig | None = None,
        retryable: tuple[type[BaseException], ...] = RETRYABLE_EXCEPTIONS,
    ) -> None:
        self._cfg = config or BackoffConfig()
        self._retryable = retryable

    async def execute(
        self,
        coro_factory: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        delay = self._cfg.initial
        last_exc: BaseException | None = None
        for attempt in range(self._cfg.max_retries + 1):
            try:
                return await coro_factory(*args, **kwargs)
            except self._retryable as e:
                last_exc = e
                if attempt == self._cfg.max_retries:
                    raise
                jitter = delay * self._cfg.jitter_pct * (2 * random.random() - 1)
                sleep = min(delay + jitter, self._cfg.max_delay)
                logger.warning(
                    "attempt %d failed (%s), retrying in %.1fs",
                    attempt + 1,
                    e,
                    sleep,
                )
                await asyncio.sleep(sleep)
                delay = min(delay * self._cfg.factor, self._cfg.max_delay)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("unreachable")
