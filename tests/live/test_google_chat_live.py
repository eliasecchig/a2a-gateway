"""Google Chat send-only tests: verify we can post messages via Chat API.

Full inbound round-trip requires a publicly accessible webhook URL.

Requires env vars:
  GOOGLE_CHAT_SA_PATH    — path to service account JSON file
  GOOGLE_CHAT_TEST_SPACE — space resource name (e.g. "spaces/AAAA...")
"""

from __future__ import annotations

import pytest

from gateway.channels.google_chat import GoogleChatAdapter
from gateway.core.types import OutboundMessage
from tests.live.conftest import require_env


def _make_adapter() -> GoogleChatAdapter:
    env = require_env("GOOGLE_CHAT_SA_PATH")
    return GoogleChatAdapter(
        service_account_path=env["GOOGLE_CHAT_SA_PATH"],
    )


def _space() -> str:
    return require_env("GOOGLE_CHAT_TEST_SPACE")["GOOGLE_CHAT_TEST_SPACE"]


@pytest.mark.live
class TestGoogleChatLive:
    async def test_send_text_message(self):
        adapter = _make_adapter()

        await adapter.start()
        try:
            msg = OutboundMessage(
                channel="google_chat",
                recipient_id="",
                text=("a2a-gateway live test — if you see this, the send API works."),
                conversation_id=_space(),
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()

    async def test_send_long_message(self):
        """Send a message exceeding Google Chat's 4096 char limit."""
        adapter = _make_adapter()
        long_text = "Paragraph. " * 500

        await adapter.start()
        try:
            msg = OutboundMessage(
                channel="google_chat",
                recipient_id="",
                text=long_text,
                conversation_id=_space(),
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()
