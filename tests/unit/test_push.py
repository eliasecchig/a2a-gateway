from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import GatewayConfig
from gateway.server import create_app
from tests.helpers.mock_adapter import MockAdapter


@pytest.mark.asyncio
class TestPushEdgeCases:
    async def test_push_adapter_send_failure_returns_502(self):
        adapter = MockAdapter(channel_name="test")
        app = create_app(GatewayConfig(), custom_channels=[adapter])
        with patch.object(
            adapter, "send", new_callable=AsyncMock, side_effect=OSError("conn refused")
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/push",
                    json={
                        "channel": "test",
                        "recipient_id": "U1",
                        "text": "hi",
                    },
                )
        assert resp.status_code == 502
        assert "adapter send failed" in resp.json()["error"]

    async def test_push_empty_body_returns_422(self):
        app = create_app(GatewayConfig())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/push",
                content=b"not json",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 422
        assert "invalid JSON" in resp.json()["error"]

    async def test_push_non_dict_body_returns_422(self):
        app = create_app(GatewayConfig())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/push", json="hello")
        assert resp.status_code == 422
        assert "JSON object" in resp.json()["error"]

    async def test_push_non_string_fields_returns_422(self):
        app = create_app(GatewayConfig())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/push",
                json={
                    "channel": "test",
                    "recipient_id": 123,
                    "text": "hi",
                },
            )
        assert resp.status_code == 422
        assert "non-empty strings" in resp.json()["error"]
