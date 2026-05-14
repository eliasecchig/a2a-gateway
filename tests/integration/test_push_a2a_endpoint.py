"""End-to-end tests for the A2A push endpoint."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.config import GatewayConfig
from gateway.server import create_app
from tests.helpers.mock_adapter import MockAdapter


def _jsonrpc_send(text: str, **metadata: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "messageId": uuid.uuid4().hex,
                "parts": [{"text": text}],
                "metadata": metadata,
            }
        },
    }


@pytest.mark.asyncio
async def test_push_a2a_delivers_to_adapter():
    adapter = MockAdapter(channel_name="test")
    app = create_app(GatewayConfig(), custom_channels=[adapter])

    payload = _jsonrpc_send(
        "weekly nudge!",
        **{"gateway/channel": "test", "gateway/recipient_id": "U123"},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"A2A-Version": "1.0"},
    ) as client:
        resp = await client.post("/push", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "result" in body, body
    # The push executor returns a Message-only response confirming delivery.
    assert "message" in body["result"], body["result"]

    # Adapter should have received the OutboundMessage.
    assert len(adapter.sent) == 1
    msg = adapter.sent[0]
    assert msg.channel == "test"
    assert msg.recipient_id == "U123"
    assert msg.text == "weekly nudge!"


@pytest.mark.asyncio
async def test_push_a2a_unknown_channel_returns_jsonrpc_error():
    app = create_app(GatewayConfig())
    payload = _jsonrpc_send(
        "hi",
        **{"gateway/channel": "nope", "gateway/recipient_id": "U1"},
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"A2A-Version": "1.0"},
    ) as client:
        resp = await client.post("/push", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert "error" in body, body
    assert "result" not in body
    msg = body["error"]["message"].lower()
    assert "channel" in msg or "not registered" in msg


@pytest.mark.asyncio
async def test_push_a2a_missing_recipient_returns_jsonrpc_error():
    adapter = MockAdapter(channel_name="test")
    app = create_app(GatewayConfig(), custom_channels=[adapter])
    payload = _jsonrpc_send(
        "hi",
        **{"gateway/channel": "test"},  # no recipient_id
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"A2A-Version": "1.0"},
    ) as client:
        resp = await client.post("/push", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert "error" in body, body
    assert "recipient_id" in body["error"]["message"]
    assert adapter.sent == []


@pytest.mark.asyncio
async def test_push_a2a_serves_agent_card():
    adapter_one = MockAdapter(channel_name="alpha")
    adapter_two = MockAdapter(channel_name="beta")
    app = create_app(GatewayConfig(), custom_channels=[adapter_one, adapter_two])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/push/.well-known/agent-card.json")

    assert resp.status_code == 200, resp.text
    card = resp.json()
    assert card["name"] == "a2a-gateway-push"
    skill_ids = [s["id"] for s in card.get("skills", [])]
    assert "send_alpha" in skill_ids
    assert "send_beta" in skill_ids
