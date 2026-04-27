"""WhatsApp send-only test: verify we can deliver a real message via Graph API.

Full inbound round-trip requires a publicly accessible webhook URL (ngrok/etc).

Requires env vars:
  WHATSAPP_ACCESS_TOKEN  — Bearer token for Graph API
  WHATSAPP_PHONE_ID      — WhatsApp Business phone number ID
  WHATSAPP_TEST_NUMBER   — recipient phone number (e.g. "5511999999999")
"""

from __future__ import annotations

import pytest

from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.core.types import OutboundMessage
from tests.live.conftest import require_env


@pytest.mark.live
class TestWhatsAppLive:
    async def test_send_text_message(self):
        env = require_env(
            "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_TEST_NUMBER"
        )

        adapter = WhatsAppAdapter(
            access_token=env["WHATSAPP_ACCESS_TOKEN"],
            phone_number_id=env["WHATSAPP_PHONE_ID"],
            verify_token="test",
        )

        await adapter.start()

        try:
            msg = OutboundMessage(
                channel="whatsapp",
                recipient_id=env["WHATSAPP_TEST_NUMBER"],
                text="a2a-gateway live test — if you see this, the send API works.",
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()
