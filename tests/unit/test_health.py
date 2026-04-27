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

from gateway.core.health import HealthMonitor


class TestHealthMonitor:
    def test_no_adapters_not_ready(self):
        hm = HealthMonitor()
        assert hm.is_ready() is False

    def test_connected_adapter_is_healthy(self):
        hm = HealthMonitor()
        hm.record_connect("slack")
        assert hm.is_adapter_healthy("slack") is True
        assert hm.is_ready() is True

    def test_disconnected_adapter_is_unhealthy(self):
        hm = HealthMonitor()
        hm.record_connect("slack")
        hm.record_disconnect("slack")
        assert hm.is_adapter_healthy("slack") is False
        assert hm.is_ready() is False

    def test_heartbeat_keeps_adapter_healthy(self):
        hm = HealthMonitor(stale_timeout_seconds=100)
        hm.record_connect("slack")
        hm.record_heartbeat("slack")
        assert hm.is_adapter_healthy("slack") is True

    def test_stale_adapter_is_unhealthy(self):
        hm = HealthMonitor(stale_timeout_seconds=10)
        hm.record_connect("slack")
        with patch("gateway.core.health.time.monotonic", return_value=1000):
            hm.record_heartbeat("slack")
        with patch("gateway.core.health.time.monotonic", return_value=1020):
            assert hm.is_adapter_healthy("slack") is False

    def test_recent_heartbeat_is_healthy(self):
        hm = HealthMonitor(stale_timeout_seconds=10)
        hm.record_connect("slack")
        with patch("gateway.core.health.time.monotonic", return_value=1000):
            hm.record_heartbeat("slack")
        with patch("gateway.core.health.time.monotonic", return_value=1005):
            assert hm.is_adapter_healthy("slack") is True

    def test_error_recording(self):
        hm = HealthMonitor()
        hm.record_connect("slack")
        hm.record_error("slack", "a2a_call_failed")
        status = hm.get_status()
        assert status["adapters"]["slack"]["error"] == "a2a_call_failed"

    def test_unknown_adapter_unhealthy(self):
        hm = HealthMonitor()
        assert hm.is_adapter_healthy("nonexistent") is False

    def test_ready_with_mixed_adapters(self):
        hm = HealthMonitor()
        hm.record_connect("slack")
        hm.record_connect("whatsapp")
        hm.record_disconnect("slack")
        assert hm.is_ready() is True

    def test_get_status_structure(self):
        hm = HealthMonitor()
        hm.record_connect("slack")
        status = hm.get_status()
        assert "ready" in status
        assert "adapters" in status
        assert "slack" in status["adapters"]
        adapter_status = status["adapters"]["slack"]
        assert "connected" in adapter_status
        assert "healthy" in adapter_status
        assert "last_heartbeat_seconds_ago" in adapter_status
        assert "error" in adapter_status
