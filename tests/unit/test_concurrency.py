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
from dataclasses import dataclass

from gateway.core.concurrency import ConcurrencyLimiter
from gateway.core.types import InboundMessage


@dataclass
class SimpleConfig:
    max_concurrent: int = 2
    per: str = "conversation"


class TestConcurrencyLimiter:
    async def test_within_limit_proceeds(self):
        limiter = ConcurrencyLimiter(SimpleConfig(max_concurrent=2))
        async with limiter.acquire("conv-1"):
            pass

    async def test_concurrent_within_limit(self):
        limiter = ConcurrencyLimiter(SimpleConfig(max_concurrent=2))
        order = []

        async def task(n: int):
            async with limiter.acquire("conv-1"):
                order.append(f"start-{n}")
                await asyncio.sleep(0.01)
                order.append(f"end-{n}")

        await asyncio.gather(task(1), task(2))
        assert len(order) == 4

    async def test_exceeding_limit_queues(self):
        limiter = ConcurrencyLimiter(SimpleConfig(max_concurrent=1))
        order = []

        async def task(n: int):
            async with limiter.acquire("conv-1"):
                order.append(f"start-{n}")
                await asyncio.sleep(0.05)
                order.append(f"end-{n}")

        await asyncio.gather(task(1), task(2))
        assert order[0] == "start-1"
        assert order[1] == "end-1"
        assert order[2] == "start-2"
        assert order[3] == "end-2"

    async def test_different_keys_independent(self):
        limiter = ConcurrencyLimiter(SimpleConfig(max_concurrent=1))
        order = []

        async def task(key: str, n: int):
            async with limiter.acquire(key):
                order.append(f"start-{key}-{n}")
                await asyncio.sleep(0.01)
                order.append(f"end-{key}-{n}")

        await asyncio.gather(task("a", 1), task("b", 1))
        assert "start-a-1" in order
        assert "start-b-1" in order

    async def test_global_mode(self):
        limiter = ConcurrencyLimiter(SimpleConfig(max_concurrent=1, per="global"))
        msg = InboundMessage(
            channel="test",
            sender_id="u1",
            sender_name="Alice",
            text="hi",
            conversation_id="conv-1",
        )
        key = limiter.resolve_key(msg)
        assert key == "__global__"

    def test_resolve_key_conversation(self):
        limiter = ConcurrencyLimiter(SimpleConfig(per="conversation"))
        msg = InboundMessage(
            channel="test",
            sender_id="u1",
            sender_name="Alice",
            text="hi",
            conversation_id="conv-1",
        )
        assert limiter.resolve_key(msg) == "conv-1"

    def test_resolve_key_user(self):
        limiter = ConcurrencyLimiter(SimpleConfig(per="user"))
        msg = InboundMessage(
            channel="test",
            sender_id="u1",
            sender_name="Alice",
            text="hi",
            conversation_id="conv-1",
        )
        assert limiter.resolve_key(msg) == "u1"

    def test_resolve_key_fallback_to_sender(self):
        limiter = ConcurrencyLimiter(SimpleConfig(per="conversation"))
        msg = InboundMessage(
            channel="test",
            sender_id="u1",
            sender_name="Alice",
            text="hi",
        )
        assert limiter.resolve_key(msg) == "u1"
