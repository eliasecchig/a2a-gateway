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

from unittest.mock import patch

from gateway.core.session import SessionStore


class TestSessionStore:
    def test_get_creates_new_session(self):
        store = SessionStore()
        session = store.get("key1")
        assert session.context_id is None
        assert store.active_count == 1

    def test_get_returns_existing_session(self):
        store = SessionStore()
        s1 = store.get("key1")
        s1.context_id = "ctx-1"
        s2 = store.get("key1")
        assert s2.context_id == "ctx-1"
        assert store.active_count == 1

    def test_update_sets_fields(self):
        store = SessionStore()
        store.get("key1")
        store.update("key1", "ctx-1")
        session = store.get("key1")
        assert session.context_id == "ctx-1"

    def test_update_refreshes_timestamp(self):
        store = SessionStore()
        session = store.get("key1")
        old_activity = session.last_activity
        with patch(
            "gateway.core.session.time.monotonic",
            return_value=old_activity + 100,
        ):
            store.update("key1", "ctx-1")
        assert store.get("key1").last_activity == old_activity + 100

    def test_touch_refreshes_timestamp(self):
        store = SessionStore()
        session = store.get("key1")
        old_activity = session.last_activity
        with patch(
            "gateway.core.session.time.monotonic",
            return_value=old_activity + 50,
        ):
            store.touch("key1")
        assert store.get("key1").last_activity == old_activity + 50

    def test_touch_nonexistent_is_noop(self):
        store = SessionStore()
        store.touch("nonexistent")
        assert store.active_count == 0

    def test_remove(self):
        store = SessionStore()
        store.get("key1")
        store.remove("key1")
        assert store.active_count == 0

    def test_remove_nonexistent_is_noop(self):
        store = SessionStore()
        store.remove("nonexistent")

    def test_sweep_removes_expired(self):
        store = SessionStore(idle_timeout_minutes=5)
        s1 = store.get("key1")
        s2 = store.get("key2")
        s1.last_activity = 1000
        s2.last_activity = 1000
        with patch("gateway.core.session.time.monotonic", return_value=1301):
            store._sweep()
        assert store.active_count == 0

    def test_sweep_preserves_active(self):
        store = SessionStore(idle_timeout_minutes=5)
        s = store.get("key1")
        s.last_activity = 1000
        with patch("gateway.core.session.time.monotonic", return_value=1100):
            store._sweep()
        assert store.active_count == 1

    def test_sweep_mixed(self):
        store = SessionStore(idle_timeout_minutes=5)
        old = store.get("old")
        old.last_activity = 1000
        new = store.get("new")
        new.last_activity = 1200
        with patch("gateway.core.session.time.monotonic", return_value=1400):
            store._sweep()
        assert store.active_count == 1

    def test_no_timeout_no_sweep(self):
        store = SessionStore()
        store.get("key1")
        store._sweep()
        assert store.active_count == 1

    async def test_stop_sweep_without_start(self):
        store = SessionStore()
        await store.stop_sweep()
