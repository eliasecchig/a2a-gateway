from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import GatewayConfig, GoogleChatAccountConfig, WhatsAppAccountConfig
from gateway.server import create_app


@pytest.mark.asyncio
class TestServer:
    async def test_live_endpoint(self):
        config = GatewayConfig()
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_ready_endpoint_without_health(self):
        config = GatewayConfig()
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_health_endpoint(self):
        config = GatewayConfig()
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["channels"] == []
        assert data["a2a_server"] == "http://localhost:8001"

    async def test_no_channels_app_works(self):
        config = GatewayConfig()
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["channels"] == []

    async def test_whatsapp_verification_webhook(self):
        config = GatewayConfig(
            whatsapp_accounts=[
                WhatsAppAccountConfig(
                    enabled=True,
                    verify_token="test-token",
                    access_token="fake",
                    phone_number_id="123",
                )
            ]
        )
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/webhooks/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "test-token",
                    "hub.challenge": "challenge_value",
                },
            )
        assert resp.status_code == 200
        assert resp.text == "challenge_value"

    async def test_whatsapp_verification_rejects_bad_token(self):
        config = GatewayConfig(
            whatsapp_accounts=[
                WhatsAppAccountConfig(
                    enabled=True,
                    verify_token="test-token",
                    access_token="fake",
                    phone_number_id="123",
                )
            ]
        )
        app = create_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/webhooks/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong-token",
                    "hub.challenge": "challenge_value",
                },
            )
        assert resp.status_code == 403

    async def test_whatsapp_webhook_post(self):
        config = GatewayConfig(
            whatsapp_accounts=[
                WhatsAppAccountConfig(
                    enabled=True,
                    verify_token="tok",
                    access_token="fake",
                    phone_number_id="123",
                )
            ]
        )
        app = create_app(config)
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123"},
                                "contacts": [
                                    {"wa_id": "5511999", "profile": {"name": "Alice"}}
                                ],
                                "messages": [
                                    {
                                        "from": "5511999",
                                        "type": "text",
                                        "text": {"body": "hello"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/webhooks/whatsapp", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_google_chat_webhook_post(self):
        with patch(
            "gateway.channels.google_chat.service_account.Credentials.from_service_account_file"
        ):
            config = GatewayConfig(
                google_chat_accounts=[
                    GoogleChatAccountConfig(
                        enabled=True,
                        service_account_path="fake.json",
                    )
                ]
            )
            app = create_app(config)
        event = {
            "type": "MESSAGE",
            "message": {
                "sender": {"name": "users/123", "displayName": "Alice"},
                "text": "hi bot",
                "thread": {"name": "spaces/abc/threads/t1"},
            },
            "space": {"name": "spaces/abc", "type": "DM"},
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/webhooks/google-chat", json=event)
        assert resp.status_code == 200

    async def test_lifespan_starts_and_stops_adapters(self):
        config = GatewayConfig(
            whatsapp_accounts=[
                WhatsAppAccountConfig(
                    enabled=True,
                    verify_token="tok",
                    access_token="fake",
                    phone_number_id="123",
                )
            ]
        )
        app = create_app(config)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert "whatsapp" in resp.json()["channels"]
