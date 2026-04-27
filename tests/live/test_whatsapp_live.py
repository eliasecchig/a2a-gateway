"""WhatsApp send-only tests: verify we can deliver messages via Graph API.

Full inbound round-trip requires a publicly accessible webhook URL.

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


def _make_adapter() -> WhatsAppAdapter:
    env = require_env(
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_ID",
        "WHATSAPP_TEST_NUMBER",
    )
    return WhatsAppAdapter(
        access_token=env["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=env["WHATSAPP_PHONE_ID"],
        verify_token="test",
    )


def _recipient() -> str:
    return require_env("WHATSAPP_TEST_NUMBER")["WHATSAPP_TEST_NUMBER"]


@pytest.mark.live
class TestWhatsAppLive:
    async def test_send_text_message(self):
        adapter = _make_adapter()

        await adapter.start()
        try:
            msg = OutboundMessage(
                channel="whatsapp",
                recipient_id=_recipient(),
                text=("a2a-gateway live test — if you see this, the send API works."),
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()

    async def test_send_long_message(self):
        """Send a message exceeding WhatsApp's 4096 char limit."""
        adapter = _make_adapter()
        long_text = "Paragraph. " * 500

        await adapter.start()
        try:
            msg = OutboundMessage(
                channel="whatsapp",
                recipient_id=_recipient(),
                text=long_text,
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()

    async def test_send_markdown_message(self):
        """Verify WhatsApp can handle markdown-formatted text."""
        adapter = _make_adapter()
        markdown_text = (
            "**Bold text** and __underline__\n\n"
            "```python\nprint('hello')\n```\n\n"
            "Check [this link](https://example.com)\n\n"
            "- item one\n- item two\n- item three"
        )

        await adapter.start()
        try:
            msg = OutboundMessage(
                channel="whatsapp",
                recipient_id=_recipient(),
                text=markdown_text,
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()
