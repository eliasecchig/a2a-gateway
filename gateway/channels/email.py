# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import email as email_lib
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import AsyncMessage

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class _InboundHandler(AsyncMessage):
    def __init__(self, adapter: EmailAdapter) -> None:
        super().__init__()
        self._adapter = adapter

    async def handle_message(self, message: email_lib.message.Message) -> None:
        sender = message.get("From", "")
        subject = message.get("Subject", "")
        body = ""
        attachments: list[Attachment] = []

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in disposition or content_type not in (
                    "text/plain",
                    "text/html",
                    "multipart/mixed",
                    "multipart/alternative",
                ):
                    raw = part.get_payload(decode=True)
                    if isinstance(raw, bytes):
                        attachments.append(
                            Attachment(
                                data=raw,
                                mime_type=content_type,
                                filename=part.get_filename(),
                                size=len(raw),
                            )
                        )
                elif content_type == "text/plain" and not body:
                    raw = part.get_payload(decode=True)
                    if isinstance(raw, bytes):
                        body = raw.decode("utf-8", errors="replace")
        else:
            raw = message.get_payload(decode=True)
            if isinstance(raw, bytes):
                body = raw.decode("utf-8", errors="replace")

        msg = InboundMessage(
            channel=self._adapter.name,
            sender_id=sender,
            sender_name=sender,
            text=body,
            thread_id=message.get("Message-ID", ""),
            conversation_id=f"email:{sender}:{subject}",
            attachments=attachments,
        )
        await self._adapter.dispatch(msg)


class EmailAdapter(ChannelAdapter):
    channel_type = "email"

    def __init__(  # noqa: PLR0917
        self,
        listen_host: str = "localhost",
        listen_port: int = 1025,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        from_address: str = "agent@example.com",
        smtp_user: str = "",
        smtp_password: str = "",
        account_id: str = "default",
    ) -> None:
        super().__init__(account_id=account_id)
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from_address = from_address
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._controller: Controller | None = None

    async def start(self) -> None:
        handler = _InboundHandler(self)
        self._controller = Controller(
            handler,
            hostname=self._listen_host,
            port=self._listen_port,
        )
        await asyncio.to_thread(self._controller.start)
        logger.info(
            "email adapter started (SMTP on %s:%d, account=%s)",
            self._listen_host,
            self._listen_port,
            self._account_id,
        )

    async def stop(self) -> None:
        if self._controller:
            self._controller.stop()

    async def send(self, message: OutboundMessage) -> str | None:
        if message.attachments:
            msg = MIMEMultipart()
            msg.attach(MIMEText(message.text, "html", "utf-8"))
            for att in message.attachments:
                part = MIMEBase(*att.mime_type.split("/", 1))
                if att.data:
                    part.set_payload(att.data)
                    encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=att.filename or "file",
                )
                msg.attach(part)
        else:
            msg = MIMEText(message.text, "html", "utf-8")

        msg["From"] = self._from_address
        msg["To"] = message.recipient_id
        msg["Subject"] = "Re: Agent Reply"
        if message.thread_id:
            msg["In-Reply-To"] = message.thread_id

        await asyncio.to_thread(self._smtp_send, msg)
        return None

    def _smtp_send(self, msg: MIMEText | MIMEMultipart) -> None:
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            if self._smtp_user:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
            server.send_message(msg)
