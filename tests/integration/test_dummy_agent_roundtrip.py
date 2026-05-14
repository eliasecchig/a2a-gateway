"""Round-trip the gateway's A2AClient against samples/dummy_agent.py.

This is the only test that proves the wire shape between our client and
a real a2a-sdk 1.0 server is what we think it is. Mock fixtures elsewhere
in the suite assume a particular shape — this test is the source of truth.
"""

from __future__ import annotations

import httpx
import pytest

from gateway.core.a2a_client import A2AClient
from samples.dummy_agent import build_app


@pytest.mark.asyncio
async def test_send_message_roundtrip_against_dummy():
    app = build_app()
    transport = httpx.ASGITransport(app=app)

    client = A2AClient("http://test/")
    await client._http.aclose()
    client._http = httpx.AsyncClient(transport=transport, base_url="http://test")

    try:
        resp = await client.send_message("hello there")
    finally:
        await client.close()

    assert resp.text == "Hello! You said: hello there"
    assert resp.context_id
