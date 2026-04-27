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
import logging
from typing import Any

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class SlackAdapter(ChannelAdapter):
    channel_type = "slack"

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        account_id: str = "default",
    ) -> None:
        super().__init__(account_id=account_id)
        self._bot_token = bot_token
        self._app_token = app_token
        self._app = AsyncApp(token=bot_token)
        self._handler: AsyncSocketModeHandler | None = None
        self._bot_user_id: str = ""
        self._setup_listeners()

    def _setup_listeners(self) -> None:
        @self._app.event("message")
        async def on_message(event: dict[str, Any], say: Any) -> None:
            if event.get("subtype"):
                return
            if event.get("bot_id"):
                return

            text = event.get("text", "")
            channel_type = event.get("channel_type", "")
            is_group = channel_type in ("channel", "group", "mpim")
            is_mention = f"<@{self._bot_user_id}>" in text if self._bot_user_id else False

            attachments: list[Attachment] = []
            for f in event.get("files", []):
                attachments.append(
                    Attachment(
                        url=f.get("url_private_download"),
                        mime_type=f.get("mimetype", "application/octet-stream"),
                        filename=f.get("name"),
                        size=f.get("size"),
                    )
                )

            msg = InboundMessage(
                channel=self.name,
                sender_id=event.get("user", ""),
                sender_name=event.get("user", "unknown"),
                text=text,
                thread_id=event.get("thread_ts") or event.get("ts"),
                conversation_id=event.get("channel", ""),
                raw_event=event,
                is_group=is_group,
                is_mention=is_mention,
                attachments=attachments,
            )
            await self.dispatch(msg)

    async def start(self) -> None:
        try:
            auth = await self._app.client.auth_test()
            self._bot_user_id = auth.get("user_id", "")
        except Exception:
            logger.error(
                "could not resolve slack bot user id, mention detection will not work"
            )

        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        self._start_task = asyncio.create_task(
            self._handler.start_async(), name=f"slack-socket-{self._account_id}"
        )
        self._start_task.add_done_callback(self._on_task_done)
        logger.info("slack adapter started (socket mode, account=%s)", self._account_id)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("slack socket mode task failed: %s", exc)

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()
        if hasattr(self, "_start_task") and not self._start_task.done():
            self._start_task.cancel()

    @property
    def supports_editing(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> str | None:
        channel = message.conversation_id or message.recipient_id
        msg_ts: str | None = None
        if message.text:
            result = await self._app.client.chat_postMessage(
                channel=channel,
                text=message.text,
                thread_ts=message.thread_id,
            )
            msg_ts = result.get("ts")

        for att in message.attachments:
            if att.data:
                await self._app.client.files_upload_v2(
                    channel=channel,
                    content=att.data,
                    filename=att.filename or "file",
                    thread_ts=message.thread_id,
                )
            elif att.url:
                await self._app.client.chat_postMessage(
                    channel=channel,
                    text=att.url,
                    thread_ts=message.thread_id,
                )
        return msg_ts

    async def edit_message(
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        try:
            await self._app.client.chat_update(
                channel=conversation_id,
                ts=message_id,
                text=text,
            )
        except Exception:
            logger.warning("slack message edit failed for ts=%s", message_id)

    async def send_ack(self, message: InboundMessage, config: dict | None = None) -> None:
        emoji = (config or {}).get("emoji", "eyes")
        ts = message.raw_event.get("ts", "")
        channel = message.raw_event.get("channel", "")
        if ts and channel:
            try:
                await self._app.client.reactions_add(
                    channel=channel, name=emoji, timestamp=ts
                )
            except Exception:
                logger.warning("slack ack reaction failed")
