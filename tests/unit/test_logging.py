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

import json
import logging

from gateway.config import LoggingConfig
from gateway.core.logging import JsonFormatter, configure_logging


class TestJsonFormatter:
    def test_produces_valid_json(self):
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self):
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.channel = "slack"
        record.a2a_duration_ms = 123.4
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["channel"] == "slack"
        assert parsed["a2a_duration_ms"] == 123.4

    def test_excludes_missing_extra_fields(self):
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert "channel" not in parsed
        assert "a2a_duration_ms" not in parsed


class TestConfigureLogging:
    def setup_method(self):
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def teardown_method(self):
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_none_config_uses_default(self):
        configure_logging(None)
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_sets_root_level(self):
        configure_logging(LoggingConfig(level="DEBUG"))
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_json_format_uses_json_formatter(self):
        configure_logging(LoggingConfig(format="json"))
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_text_format_uses_standard_formatter(self):
        configure_logging(LoggingConfig(format="text"))
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_subsystem_level_overrides(self):
        configure_logging(
            LoggingConfig(subsystem_levels={"gateway.core.router": "DEBUG"})
        )
        router_logger = logging.getLogger("gateway.core.router")
        assert router_logger.level == logging.DEBUG
