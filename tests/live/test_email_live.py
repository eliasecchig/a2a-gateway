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


def _make_stack(echo_agent: str):
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
    adapter._smtp_send = lambda msg: sent_replies.append(msg)
    return adapter, client, sent_replies


def _send_email(text: str, subject: str = "Test message"):
    msg = MIMEText(text, "plain", "utf-8")
    msg["From"] = "tester@example.com"
    msg["To"] = "agent@test.local"
    msg["Subject"] = subject
    with smtplib.SMTP("127.0.0.1", LISTEN_PORT) as server:
        server.send_message(msg)


def _extract_reply_text(reply) -> str:
    if hasattr(reply, "get_payload"):
        if reply.is_multipart():
            for part in reply.get_payload():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    return payload.decode() if payload else ""
        payload = reply.get_payload(decode=True)
        return payload.decode() if payload else str(reply)
    return str(reply)


@pytest.mark.live
class TestEmailLive:
    async def test_full_roundtrip(self, echo_agent: str):
        adapter, _client, sent_replies = _make_stack(echo_agent)

        await adapter.start()
        try:
            _send_email("Hello from test")
            await asyncio.sleep(2.0)

            assert len(sent_replies) >= 1, "No reply was captured"
            text = _extract_reply_text(sent_replies[0])
            assert "ECHO:" in text
            assert "Hello from test" in text
        finally:
            await adapter.stop()

    async def test_file_attachment_roundtrip(self, echo_agent: str):
        adapter, _client, sent_replies = _make_stack(echo_agent)

        await adapter.start()
        try:
            _send_email("/file gimme-a-png")
            await asyncio.sleep(3.0)

            assert len(sent_replies) >= 1, "No reply was captured"
            reply = sent_replies[0]
            assert hasattr(reply, "get_payload"), "Expected MIME message reply"
            if reply.is_multipart():
                parts = reply.get_payload()
                filenames = [p.get_filename() for p in parts if p.get_filename()]
                assert "test.png" in filenames, (
                    f"Expected test.png attachment, got: {filenames}"
                )
            else:
                text = _extract_reply_text(reply)
                assert "ECHO:" in text
        finally:
            await adapter.stop()

    async def test_unicode_roundtrip(self, echo_agent: str):
        adapter, _client, sent_replies = _make_stack(echo_agent)

        await adapter.start()
        try:
            _send_email("café naïve 你好 \U0001f680")
            await asyncio.sleep(2.0)

            assert len(sent_replies) >= 1, "No reply was captured"
            text = _extract_reply_text(sent_replies[0])
            assert "ECHO:" in text
            assert "café" in text, f"Accented chars lost: {text[:200]}"
        finally:
            await adapter.stop()
