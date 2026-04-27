"""Full local round-trip: send email → gateway → echo agent → reply captured.

No external dependencies. Runs anywhere.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText

import pytest

from gateway.channels.email import EmailAdapter
from gateway.core.a2a_client import A2AClient
from gateway.core.rate_limit import BackoffConfig
from gateway.core.router import Router

LISTEN_PORT = 1026


@pytest.mark.live
class TestEmailLive:
    async def test_full_roundtrip(self, echo_agent: str):
        adapter = EmailAdapter(
            listen_host="127.0.0.1",
            listen_port=LISTEN_PORT,
            smtp_host="127.0.0.1",
            smtp_port=LISTEN_PORT,
            from_address="agent@test.local",
        )

        client = A2AClient(echo_agent)
        router = Router(client, backoff_config=BackoffConfig(max_retries=0))
        router.register(adapter)

        sent_replies: list = []

        def capture_send(msg):
            sent_replies.append(msg)

        adapter._smtp_send = capture_send

        await adapter.start()

        try:
            msg = MIMEText("Hello from test", "plain", "utf-8")
            msg["From"] = "tester@example.com"
            msg["To"] = "agent@test.local"
            msg["Subject"] = "Test message"

            with smtplib.SMTP("127.0.0.1", LISTEN_PORT) as server:
                server.send_message(msg)

            await asyncio.sleep(2.0)

            assert len(sent_replies) >= 1, "No reply was captured"
            reply = sent_replies[0]
            if hasattr(reply, "get_payload"):
                reply_text = reply.get_payload(decode=True)
                reply_text = reply_text.decode() if reply_text else str(reply)
            else:
                reply_text = str(reply)
            assert "ECHO:" in reply_text
            assert "Hello from test" in reply_text

        finally:
            await adapter.stop()
