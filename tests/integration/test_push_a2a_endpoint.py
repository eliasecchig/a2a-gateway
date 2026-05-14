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
