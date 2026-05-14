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

from unittest.mock import AsyncMock, patch

from gateway.config import StreamingConfig, load_config
from gateway.core.a2a_client import A2AClient, A2AStreamEvent
from gateway.core.capabilities import AgentCapabilities
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router
from gateway.core.types import InboundMessage, OutboundMessage
from tests.helpers.mock_adapter import MockAdapter


class EditableAdapter(MockAdapter):
    def __init__(self, channel_name: str = "slack"):
        super().__init__(channel_name)
        self.edits: list[tuple[str, str, str]] = []
        self._send_counter = 0

    @property
    def supports_editing(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> str | None:
        self.sent.append(message)
        self._send_counter += 1
        return f"msg-{self._send_counter}"

    async def edit_message(
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        self.edits.append((message_id, conversation_id, text))


def _make_msg(channel: str = "slack") -> InboundMessage:
    return InboundMessage(
        channel=channel,
        sender_id="u1",
        sender_name="User",
        text="hello",
        conversation_id="conv1",
        raw_event={},
    )


class TestA2AStreamEvent:
    def test_from_result_working_state(self):
        result = {
            "task": {
                "id": "task-1",
                "contextId": "ctx-1",
                "status": {"state": "TASK_STATE_WORKING"},
                "artifacts": [{"parts": [{"text": "partial"}]}],
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.text == "partial"
        assert event.is_final is False
        assert event.task_id == "task-1"

    def test_from_result_completed_state(self):
        result = {
            "task": {
                "id": "task-1",
                "contextId": "ctx-1",
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{"parts": [{"text": "done"}]}],
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.text == "done"
        assert event.is_final is True

    def test_from_result_failed_state(self):
        result = {
            "task": {
                "status": {"state": "TASK_STATE_FAILED"},
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.is_final is True

    def test_non_final_ignores_status_message_text(self):
        result = {
            "task": {
                "status": {
                    "state": "TASK_STATE_WORKING",
                    "message": {"parts": [{"text": "thinking"}]},
                },
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.text == ""

    def test_final_uses_status_message_fallback(self):
        result = {
            "task": {
                "status": {
                    "state": "TASK_STATE_COMPLETED",
                    "message": {"parts": [{"text": "done"}]},
                },
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.text == "done"

    def test_message_event_treated_as_final(self):
        # StreamResponse can carry a Message event when the executor emits a
        # final agent message without a Task. The wrapped Message is terminal.
        result = {
            "message": {
                "messageId": "m1",
                "contextId": "ctx-1",
                "role": "ROLE_AGENT",
                "parts": [{"text": "answer"}],
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.is_final is True
        assert event.text == "answer"
        assert event.context_id == "ctx-1"

    def test_unwrap_status_update_event(self):
        result = {
            "statusUpdate": {
                "taskId": "abc",
                "contextId": "ctx-1",
                "status": {
                    "state": "TASK_STATE_WORKING",
                    "message": {
                        "role": "ROLE_AGENT",
                        "parts": [{"text": "thinking..."}],
                    },
                },
                "final": False,
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.task_id == "abc"
        assert event.context_id == "ctx-1"
        assert event.is_final is False
        assert event.text == "thinking..."

    def test_unwrap_status_update_event_final_state(self):
        result = {
            "statusUpdate": {
                "taskId": "abc",
                "contextId": "ctx-1",
                "status": {
                    "state": "TASK_STATE_COMPLETED",
                    "message": {
                        "role": "ROLE_AGENT",
                        "parts": [{"text": "done"}],
                    },
                },
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.is_final is True
        assert event.text == "done"

    def test_unwrap_status_update_event_explicit_final_flag(self):
        result = {
            "statusUpdate": {
                "taskId": "abc",
                "contextId": "ctx-1",
                "status": {
                    "state": "TASK_STATE_WORKING",
                    "message": {
                        "role": "ROLE_AGENT",
                        "parts": [{"text": "done early"}],
                    },
                },
                "final": True,
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.is_final is True
        assert event.text == "done early"

    def test_unwrap_artifact_update_event(self):
        result = {
            "artifactUpdate": {
                "taskId": "abc",
                "contextId": "ctx-1",
                "artifact": {"parts": [{"text": "partial answer"}]},
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.task_id == "abc"
        assert event.context_id == "ctx-1"
        assert event.is_final is False
        assert event.text == "partial answer"

    def test_rejected_state_is_terminal(self):
        result = {
            "task": {
                "id": "t",
                "contextId": "c",
                "status": {"state": "TASK_STATE_REJECTED"},
            }
        }
        event = A2AStreamEvent.from_result(result)
        assert event.is_final is True


class TestStreamingRouter:
    async def test_uses_streaming_when_supported(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            streaming_update_interval_ms=100,
        )
        router._agent_capabilities = AgentCapabilities(streaming=True)

        adapter = EditableAdapter("slack")
        router.register(adapter)

        async def fake_stream(*args, **kwargs):
            yield A2AStreamEvent(
                text="partial",
                is_final=False,
                context_id="ctx1",
                task_id="t1",
            )
            yield A2AStreamEvent(
                text="final answer",
                is_final=True,
                context_id="ctx1",
                task_id="t1",
            )

        router.a2a.send_message_stream = fake_stream

        msg = _make_msg()
        await router._handle_inner(msg)

        assert len(adapter.sent) >= 1
        assert len(adapter.edits) >= 1
        assert adapter.edits[-1][2] == "final answer"

    async def test_falls_back_when_channel_not_editable(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            streaming_update_interval_ms=100,
        )
        router._agent_capabilities = AgentCapabilities(streaming=True)

        adapter = MockAdapter("whatsapp")
        router.register(adapter)

        mock_resp = AsyncMock()
        mock_resp.return_value.text = "response"
        mock_resp.return_value.context_id = "ctx1"
        mock_resp.return_value.task_id = "t1"
        mock_resp.return_value.attachments = []

        with patch.object(router, "_call_a2a") as mock_call:
            mock_call.return_value = (mock_resp.return_value, 100.0)
            await router._handle_inner(_make_msg("whatsapp"))

        assert len(adapter.sent) >= 1

    async def test_falls_back_when_agent_no_streaming(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            streaming_update_interval_ms=100,
        )
        router._agent_capabilities = AgentCapabilities(streaming=False)

        adapter = EditableAdapter("slack")
        router.register(adapter)

        with patch.object(router, "_call_a2a") as mock_call:
            mock_call.return_value = (
                AsyncMock(
                    text="resp",
                    context_id="c1",
                    task_id="t1",
                    attachments=[],
                ),
                50.0,
            )
            await router._handle_inner(_make_msg())

        assert len(adapter.sent) >= 1

    async def test_streaming_retries_on_connection_error(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            streaming_update_interval_ms=100,
            backoff_config=BackoffConfig(max_retries=3, initial=0.01, factor=1.0),
        )
        router._agent_capabilities = AgentCapabilities(streaming=True)

        adapter = EditableAdapter("slack")
        router.register(adapter)

        attempt = 0

        async def flaky_stream(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError("refused")
            yield A2AStreamEvent(
                text="recovered",
                is_final=True,
                context_id="ctx1",
                task_id="t1",
            )

        router.a2a.send_message_stream = flaky_stream

        await router._handle_inner(_make_msg())

        assert attempt == 3
        assert len(adapter.sent) >= 1
        assert adapter.sent[-1].text == "recovered"

    async def test_streaming_gives_up_after_max_retries(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            streaming_update_interval_ms=100,
            backoff_config=BackoffConfig(max_retries=2, initial=0.01, factor=1.0),
        )
        router._agent_capabilities = AgentCapabilities(streaming=True)

        adapter = EditableAdapter("slack")
        router.register(adapter)

        async def always_fail(*args, **kwargs):
            raise ConnectionError("down")
            yield

        router.a2a.send_message_stream = always_fail

        await router._handle_inner(_make_msg())

        assert len(adapter.sent) == 1
        assert "Sorry" in adapter.sent[0].text

    async def test_falls_back_when_streaming_not_configured(self):
        router = Router(A2AClient("http://localhost:9999"))
        router._agent_capabilities = AgentCapabilities(streaming=True)

        adapter = EditableAdapter("slack")
        router.register(adapter)

        with patch.object(router, "_call_a2a") as mock_call:
            mock_call.return_value = (
                AsyncMock(
                    text="resp",
                    context_id="c1",
                    task_id="t1",
                    attachments=[],
                ),
                50.0,
            )
            await router._handle_inner(_make_msg())

        assert len(adapter.sent) >= 1


class TestStreamingConfig:
    def test_defaults(self):
        cfg = StreamingConfig()
        assert cfg.enabled is True
        assert cfg.update_interval_ms == 500

    def test_parsed_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
streaming:
  enabled: true
  update_interval_ms: 300
"""
        )
        cfg = load_config(config_file)
        assert cfg.streaming is not None
        assert cfg.streaming.update_interval_ms == 300

    def test_defaults_when_not_configured(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("port: 8000\n")
        cfg = load_config(config_file)
        assert cfg.streaming.enabled is True
        assert cfg.streaming.update_interval_ms == 500


class TestChannelEditing:
    def test_base_adapter_not_editable(self):
        adapter = MockAdapter("test")
        assert adapter.supports_editing is False

    def test_editable_adapter_supports_editing(self):
        adapter = EditableAdapter("slack")
        assert adapter.supports_editing is True

    async def test_base_edit_message_is_noop(self):
        adapter = MockAdapter("test")
        await adapter.edit_message("id", "conv", "text")
