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
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import service_account

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)

CHAT_API = "https://chat.googleapis.com/v1"
SCOPES = ["https://www.googleapis.com/auth/chat.bot"]


def _event_token_from_header(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


class GoogleChatAdapter(ChannelAdapter):
    channel_type = "google_chat"

    def __init__(
        self,
        service_account_path: str,
        account_id: str = "default",
        verification_token: str = "",
    ) -> None:
        super().__init__(account_id=account_id)
        self._verification_token = verification_token
        self._creds = service_account.Credentials.from_service_account_file(
            service_account_path, scopes=SCOPES
        )
        self._auth_request = AuthRequest()
        self._http = httpx.AsyncClient(timeout=30.0)
        prefix = (
            f"/webhooks/google-chat/{account_id}"
            if account_id != "default"
            else "/webhooks/google-chat"
        )
        self.router = APIRouter(prefix=prefix, tags=["google-chat"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.post("", response_model=None)
        async def webhook(request: Request) -> dict[str, Any] | Response:
            if self._verification_token:
                token = _event_token_from_header(request)
                if not token or not hmac.compare_digest(token, self._verification_token):
                    return Response(status_code=403)

            event = await request.json()
            event_type = event.get("type", "")

            if event_type == "MESSAGE":
                message = event.get("message", {})
                sender = message.get("sender", {})
                space = event.get("space", {})

                space_type = space.get("type", "")
                is_group = space_type in ("ROOM", "SPACE")

                annotations = message.get("annotations", [])
                is_mention = any(
                    a.get("type") == "USER_MENTION"
                    and a.get("userMention", {}).get("type") == "MENTION"
                    for a in annotations
                )

                attachments: list[Attachment] = []
                for att_data in message.get("attachment", []):
                    attachments.append(
                        Attachment(
                            url=att_data.get("downloadUri"),
                            mime_type=att_data.get(
                                "contentType", "application/octet-stream"
                            ),
                            filename=att_data.get("contentName"),
                        )
                    )

                msg = InboundMessage(
                    channel=self.name,
                    sender_id=sender.get("name", ""),
                    sender_name=sender.get("displayName", "unknown"),
                    text=message.get("argumentText", message.get("text", "")),
                    thread_id=message.get("thread", {}).get("name"),
                    conversation_id=space.get("name", ""),
                    raw_event=event,
                    is_group=is_group,
                    is_mention=is_mention,
                    attachments=attachments,
                )
                await self.dispatch(msg)

            return {"text": ""}

    async def _get_auth_headers(self) -> dict[str, str]:
        await asyncio.to_thread(self._creds.refresh, self._auth_request)
        return {"Authorization": f"Bearer {self._creds.token}"}

    async def start(self) -> None:
        logger.info("google chat adapter started (webhook, account=%s)", self._account_id)

    async def stop(self) -> None:
        await self._http.aclose()

    @property
    def supports_editing(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> str | None:
        space = message.conversation_id or ""
        url = f"{CHAT_API}/{space}/messages"

        body: dict[str, Any] = {"text": message.text}
        if message.thread_id:
            body["thread"] = {"name": message.thread_id}
            url += "?messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

        headers = await self._get_auth_headers()
        resp = await self._http.post(url, json=body, headers=headers)
        msg_name: str | None = None
        if resp.status_code != 200:
            logger.error("google chat send failed: %s %s", resp.status_code, resp.text)
        else:
            msg_name = resp.json().get("name")

        for att in message.attachments:
            if att.url:
                att_body: dict[str, Any] = {"text": att.url}
                if message.thread_id:
                    att_body["thread"] = {"name": message.thread_id}
                await self._http.post(
                    f"{CHAT_API}/{space}/messages", json=att_body, headers=headers
                )
        return msg_name

    async def edit_message(
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        url = f"{CHAT_API}/{message_id}"
        headers = await self._get_auth_headers()
        try:
            await self._http.patch(
                url,
                json={"text": text},
                headers=headers,
                params={"updateMask": "text"},
            )
        except Exception:
            logger.warning("google chat message edit failed for %s", message_id)

    async def send_ack(self, message: InboundMessage, config: dict | None = None) -> None:
        emoji = (config or {}).get("emoji", "eyes")
        emoji_map = {"eyes": "\U0001f440", "thumbsup": "\U0001f44d"}
        unicode_emoji = emoji_map.get(emoji, emoji)

        msg_event = message.raw_event.get("message", {})
        msg_name = msg_event.get("name", "")
        if not msg_name:
            return
        url = f"{CHAT_API}/{msg_name}/reactions"
        headers = await self._get_auth_headers()
        try:
            await self._http.post(
                url,
                json={"emoji": {"unicode": unicode_emoji}},
                headers=headers,
            )
        except Exception:
            logger.warning("google chat ack reaction failed")
