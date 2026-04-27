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

from unittest.mock import AsyncMock

from gateway.config import AckConfig, load_config
from gateway.core.a2a_client import A2AClient
from gateway.core.router import Router
from gateway.core.types import InboundMessage
from tests.helpers.mock_adapter import MockAdapter


class AckAdapter(MockAdapter):
    def __init__(self, channel_name: str = "slack"):
        super().__init__(channel_name)
        self.ack_calls: list[tuple[InboundMessage, dict | None]] = []

    async def send_ack(self, message: InboundMessage, config: dict | None = None) -> None:
        self.ack_calls.append((message, config))


def _make_msg(channel: str = "slack") -> InboundMessage:
    return InboundMessage(
        channel=channel,
        sender_id="u1",
        sender_name="User",
        text="hello",
        conversation_id="conv1",
        raw_event={},
    )


def _router_with_ack(
    ack_config: dict[str, dict] | None = None,
) -> Router:
    router = Router(
        A2AClient("http://localhost:9999"),
        ack_config=ack_config,
    )
    router._handle_inner = AsyncMock()
    return router


class TestAckInPipeline:
    async def test_ack_fires_before_pipeline(self):
        order: list[str] = []

        async def tracking_handle(msg):
            order.append("pipeline")

        router = Router(
            A2AClient("http://localhost:9999"),
            ack_config={"slack": {"emoji": "eyes"}},
        )
        router._handle_inner = tracking_handle

        adapter = AckAdapter("slack")

        original_send_ack = adapter.send_ack

        async def tracking_ack(msg, config=None):
            order.append("ack")
            await original_send_ack(msg, config)

        adapter.send_ack = tracking_ack
        router.register(adapter)

        await adapter.on_message(_make_msg())
        assert order == ["ack", "pipeline"]

    async def test_ack_passes_channel_config(self):
        router = _router_with_ack({"slack": {"emoji": "rocket"}})
        adapter = AckAdapter("slack")
        router.register(adapter)

        await adapter.on_message(_make_msg())

        assert len(adapter.ack_calls) == 1
        _, config = adapter.ack_calls[0]
        assert config == {"emoji": "rocket"}

    async def test_ack_disabled_by_feature_flag(self):
        router = _router_with_ack({"slack": {"emoji": "eyes"}})
        adapter = AckAdapter("slack")
        router.register(adapter, features={"ack": False})

        await adapter.on_message(_make_msg())

        assert len(adapter.ack_calls) == 0

    async def test_no_ack_config_skips_ack(self):
        router = _router_with_ack(None)
        adapter = AckAdapter("slack")
        router.register(adapter)

        await adapter.on_message(_make_msg())

        assert len(adapter.ack_calls) == 0

    async def test_ack_error_does_not_block_pipeline(self):
        router = Router(
            A2AClient("http://localhost:9999"),
            ack_config={"slack": {"emoji": "eyes"}},
        )
        pipeline_called = False

        async def mock_handle(msg):
            nonlocal pipeline_called
            pipeline_called = True

        router._handle_inner = mock_handle

        adapter = AckAdapter("slack")

        async def failing_ack(msg, config=None):
            raise RuntimeError("ack boom")

        adapter.send_ack = failing_ack
        router.register(adapter)

        await adapter.on_message(_make_msg())
        assert pipeline_called

    async def test_ack_with_multi_account_channel(self):
        router = _router_with_ack({"slack": {"emoji": "wave"}})
        adapter = AckAdapter("slack")
        adapter._name = "slack:workspace_a"
        router.register(adapter)

        await adapter.on_message(_make_msg("slack:workspace_a"))

        assert len(adapter.ack_calls) == 1
        _, config = adapter.ack_calls[0]
        assert config == {"emoji": "wave"}

    async def test_ack_only_for_configured_channels(self):
        router = _router_with_ack({"slack": {"emoji": "eyes"}})
        adapter = AckAdapter("whatsapp")
        router.register(adapter)

        await adapter.on_message(_make_msg("whatsapp"))

        assert len(adapter.ack_calls) == 1
        _, config = adapter.ack_calls[0]
        assert config is None


class TestAckConfigParsing:
    def test_ack_config_defaults(self):
        cfg = AckConfig()
        assert cfg.slack == {"emoji": "eyes"}
        assert cfg.whatsapp == {"read_receipts": "true"}
        assert cfg.google_chat == {"emoji": "eyes"}

    def test_ack_parsed_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
ack:
  slack:
    emoji: "rocket"
  whatsapp:
    read_receipts: "true"
"""
        )
        cfg = load_config(config_file)
        assert cfg.ack is not None
        assert cfg.ack.slack == {"emoji": "rocket"}

    def test_ack_none_when_not_configured(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("port: 8000\n")
        cfg = load_config(config_file)
        assert cfg.ack is None


class TestChannelAdapterSendAck:
    async def test_base_adapter_send_ack_is_noop(self):
        adapter = MockAdapter("test")
        msg = _make_msg()
        await adapter.send_ack(msg, {"emoji": "eyes"})
