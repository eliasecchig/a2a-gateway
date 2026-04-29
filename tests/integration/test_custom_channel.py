from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import CustomChannelConfig, GatewayConfig
from gateway.core.simple_channel import SimpleChannel
from gateway.core.types import OutboundMessage
from gateway.server import create_app


class EchoChannel(SimpleChannel):
    channel_type = "echo"

    def __init__(self, prefix: str = "", account_id: str = "default") -> None:
        super().__init__(account_id=account_id)
        self.prefix = prefix
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> str | None:
        self.sent.append(message)
        return None


class TestProgrammaticRegistration:
    async def test_custom_channel_appears_in_health(self):
        adapter = EchoChannel()
        config = GatewayConfig()
        app = create_app(config, custom_channels=[adapter])
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert "echo" in resp.json()["channels"]

    async def test_multiple_custom_channels(self):
        a = EchoChannel(account_id="a")
        b = EchoChannel(account_id="b")
        config = GatewayConfig()
        app = create_app(config, custom_channels=[a, b])
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        channels = resp.json()["channels"]
        assert "echo:a" in channels
        assert "echo:b" in channels

    async def test_custom_channel_with_kwargs(self):
        adapter = EchoChannel(prefix=">>")
        config = GatewayConfig()
        app = create_app(config, custom_channels=[adapter])
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert "echo" in resp.json()["channels"]


class TestYamlAutoImport:
    async def test_auto_import_registers_channel(self):
        config = GatewayConfig(
            custom_channels=[
                CustomChannelConfig(
                    class_path=("tests.integration.test_custom_channel.EchoChannel"),
                    account_id="yaml",
                    kwargs={"prefix": "!"},
                )
            ]
        )
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert "echo:yaml" in resp.json()["channels"]

    async def test_auto_import_malformed_class_path_raises(self):
        config = GatewayConfig(
            custom_channels=[
                CustomChannelConfig(class_path="NoDotsHere"),
            ]
        )
        with pytest.raises(ValueError, match="dotted path"):
            create_app(config)

    async def test_auto_import_bad_path_raises(self):
        config = GatewayConfig(
            custom_channels=[
                CustomChannelConfig(
                    class_path="nonexistent.module.Channel",
                )
            ]
        )
        with pytest.raises(ImportError):
            create_app(config)

    async def test_auto_import_bad_class_name_raises(self):
        config = GatewayConfig(
            custom_channels=[
                CustomChannelConfig(
                    class_path="gateway.config.NonExistentClass",
                )
            ]
        )
        with pytest.raises(ImportError, match="not found"):
            create_app(config)

    async def test_auto_import_not_adapter_raises(self):
        config = GatewayConfig(
            custom_channels=[
                CustomChannelConfig(
                    class_path="gateway.config.GatewayConfig",
                )
            ]
        )
        with pytest.raises(TypeError, match="not a ChannelAdapter subclass"):
            create_app(config)
