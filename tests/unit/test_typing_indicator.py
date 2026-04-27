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

from gateway.core.typing_indicator import TypingIndicator
from tests.helpers.mock_adapter import MockAdapter


class TypingAdapter(MockAdapter):
    def __init__(self):
        super().__init__("test")
        self.typing_calls: list[tuple[str, str | None]] = []

    async def send_typing(
        self, conversation_id: str, thread_id: str | None = None
    ) -> None:
        self.typing_calls.append((conversation_id, thread_id))


class TestTypingIndicator:
    async def test_start_creates_task(self):
        ti = TypingIndicator(ttl_seconds=30)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1")
        assert "key1" in ti._active
        await ti.stop("key1")

    async def test_stop_cancels_task(self):
        ti = TypingIndicator(ttl_seconds=30)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1")
        await ti.stop("key1")
        assert "key1" not in ti._active

    async def test_stop_nonexistent_is_noop(self):
        ti = TypingIndicator(ttl_seconds=30)
        await ti.stop("nonexistent")

    async def test_stop_all_cleans_up(self):
        ti = TypingIndicator(ttl_seconds=30)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1")
        await ti.start(adapter, "key2", "conv-2")
        await ti.stop_all()
        assert len(ti._active) == 0

    async def test_ttl_auto_stops(self):
        ti = TypingIndicator(ttl_seconds=0.05)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1")
        await asyncio.sleep(0.15)
        assert "key1" not in ti._active

    async def test_duplicate_start_ignored(self):
        ti = TypingIndicator(ttl_seconds=30)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1")
        task1 = ti._active["key1"]
        await ti.start(adapter, "key1", "conv-1")
        assert ti._active["key1"] is task1
        await ti.stop("key1")

    async def test_sends_typing_signal(self):
        ti = TypingIndicator(ttl_seconds=0.05)
        adapter = TypingAdapter()
        await ti.start(adapter, "key1", "conv-1", "thread-1")
        await asyncio.sleep(0.02)
        assert len(adapter.typing_calls) >= 1
        assert adapter.typing_calls[0] == ("conv-1", "thread-1")
        await ti.stop("key1")
