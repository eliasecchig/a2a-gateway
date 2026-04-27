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

import hashlib
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Query, Request, Response

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"

_MEDIA_TYPE_MAP = {
    "image": "image",
    "video": "video",
    "audio": "audio",
    "sticker": "sticker",
}


class WhatsAppAdapter(ChannelAdapter):
    channel_type = "whatsapp"

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        verify_token: str,
        app_secret: str = "",
        account_id: str = "default",
    ) -> None:
        super().__init__(account_id=account_id)
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._verify_token = verify_token
        self._app_secret = app_secret
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        prefix = (
            f"/webhooks/whatsapp/{account_id}"
            if account_id != "default"
            else "/webhooks/whatsapp"
        )
        self.router = APIRouter(prefix=prefix, tags=["whatsapp"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("")
        async def verify(
            hub_mode: str = Query(alias="hub.mode", default=""),
            hub_token: str = Query(alias="hub.verify_token", default=""),
            hub_challenge: str = Query(alias="hub.challenge", default=""),
        ) -> Response:
            if hub_mode == "subscribe" and hub_token == self._verify_token:
                return Response(content=hub_challenge, media_type="text/plain")
            return Response(status_code=403)

        @self.router.post("")
        async def webhook(request: Request) -> dict[str, str]:
            raw = await request.body()
            if self._app_secret:
                sig = request.headers.get("x-hub-signature-256", "")
                if not self._verify_signature(raw, sig):
                    return {"status": "invalid signature"}

            import json as _json

            body = _json.loads(raw)
            await self._process_payload(body)
            return {"status": "ok"}

    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        expected = (
            "sha256="
            + hmac.new(self._app_secret.encode(), payload, hashlib.sha256).hexdigest()
        )
        return hmac.compare_digest(expected, signature)

    async def _process_payload(self, body: dict[str, Any]) -> None:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    msg_type = message.get("type", "")
                    contact = next(
                        (
                            c
                            for c in value.get("contacts", [])
                            if c.get("wa_id") == message.get("from")
                        ),
                        {},
                    )
                    sender = message.get("from", "")
                    sender_name = contact.get("profile", {}).get("name", sender)

                    text = ""
                    attachments: list[Attachment] = []

                    if msg_type == "text":
                        text = message.get("text", {}).get("body", "")
                    elif msg_type in _MEDIA_TYPE_MAP:
                        media = message.get(msg_type, {})
                        text = media.get("caption", "")
                        attachments.append(
                            Attachment(
                                mime_type=media.get(
                                    "mime_type", "application/octet-stream"
                                ),
                                filename=media.get("filename"),
                            )
                        )
                    else:
                        continue

                    is_group = message.get("context", {}).get("group_id") is not None

                    msg = InboundMessage(
                        channel=self.name,
                        sender_id=sender,
                        sender_name=sender_name,
                        text=text,
                        conversation_id=sender,
                        raw_event=message,
                        is_group=is_group,
                        is_mention=False,
                        attachments=attachments,
                    )
                    await self.dispatch(msg)

    async def start(self) -> None:
        logger.info("whatsapp adapter started (webhook, account=%s)", self._account_id)

    async def stop(self) -> None:
        await self._http.aclose()

    async def send(self, message: OutboundMessage) -> str | None:
        url = f"{GRAPH_API}/{self._phone_number_id}/messages"

        if message.text:
            payload = {
                "messaging_product": "whatsapp",
                "to": message.recipient_id,
                "type": "text",
                "text": {"body": message.text},
            }
            resp = await self._http.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("whatsapp text send failed: %s", resp.text)

        for att in message.attachments:
            await self._send_media(message.recipient_id, att)
        return None

    async def _send_media(self, to: str, att: Attachment) -> None:
        media_type = self._classify_media(att.mime_type)
        url = f"{GRAPH_API}/{self._phone_number_id}/messages"

        media_obj: dict[str, Any] = {}
        if att.url:
            media_obj["link"] = att.url
        elif att.data:
            media_id = await self._upload_media(att)
            if not media_id:
                return
            media_obj["id"] = media_id

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_obj,
        }
        resp = await self._http.post(url, json=payload)
        if resp.status_code != 200:
            logger.error("whatsapp media send failed: %s", resp.text)

    async def _upload_media(self, att: Attachment) -> str | None:
        if att.data is None:
            raise ValueError("attachment data is required for upload")
        url = f"{GRAPH_API}/{self._phone_number_id}/media"
        files = {
            "file": (att.filename or "file", att.data, att.mime_type),
        }
        data = {"messaging_product": "whatsapp", "type": att.mime_type}
        resp = await self._http.post(url, data=data, files=files)
        if resp.status_code == 200:
            return resp.json().get("id")
        logger.error("whatsapp media upload failed: %s", resp.text)
        return None

    async def send_ack(self, message: InboundMessage, config: dict | None = None) -> None:
        if not (config or {}).get("read_receipts", True):
            return
        msg_id = message.raw_event.get("id", "")
        if msg_id:
            url = f"{GRAPH_API}/{self._phone_number_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": msg_id,
            }
            try:
                await self._http.post(url, json=payload)
            except Exception:
                logger.warning("whatsapp read receipt failed")

    @staticmethod
    def _classify_media(mime_type: str) -> str:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        return "document"
