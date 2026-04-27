"""Google Chat send-only test: verify we can post a message via Chat API.

Full inbound round-trip requires a publicly accessible webhook URL.

Requires env vars:
  GOOGLE_CHAT_SA_PATH   — path to service account JSON file
  GOOGLE_CHAT_TEST_SPACE — space resource name (e.g. "spaces/AAAA...")
"""

from __future__ import annotations

import pytest

from gateway.channels.google_chat import GoogleChatAdapter
from gateway.core.types import OutboundMessage
from tests.live.conftest import require_env


@pytest.mark.live
class TestGoogleChatLive:
    async def test_send_text_message(self):
        env = require_env("GOOGLE_CHAT_SA_PATH", "GOOGLE_CHAT_TEST_SPACE")

        adapter = GoogleChatAdapter(
            service_account_path=env["GOOGLE_CHAT_SA_PATH"],
        )

        await adapter.start()

        try:
            msg = OutboundMessage(
                channel="google_chat",
                recipient_id="",
                text="a2a-gateway live test — if you see this, the send API works.",
                conversation_id=env["GOOGLE_CHAT_TEST_SPACE"],
            )
            await adapter.send(msg)
        finally:
            await adapter.stop()
