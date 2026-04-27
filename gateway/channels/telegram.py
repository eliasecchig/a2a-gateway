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

from telegram import Bot, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class TelegramAdapter(ChannelAdapter):
    channel_type = "telegram"

    def __init__(
        self,
        bot_token: str,
        account_id: str = "default",
    ) -> None:
        super().__init__(account_id=account_id)
        self._bot_token = bot_token
        self._app: Application | None = None
        self._bot: Bot | None = None
        self._bot_username: str = ""

    @property
    def supports_editing(self) -> bool:
        return True

    async def start(self) -> None:
        self._app = Application.builder().token(self._bot_token).build()
        self._bot = self._app.bot

        try:
            me = await self._bot.get_me()
            self._bot_username = me.username or ""
        except Exception:
            logger.error(
                "could not resolve telegram bot username, mention detection will not work"
            )

        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )

        await self._app.initialize()
        await self._app.start()
        updater = self._app.updater
        if updater is None:
            raise RuntimeError("telegram updater not available")
        self._poll_task = asyncio.create_task(
            updater.start_polling(),
            name=f"telegram-poll-{self._account_id}",
        )
        self._poll_task.add_done_callback(self._on_task_done)
        logger.info(
            "telegram adapter started (polling, account=%s)",
            self._account_id,
        )

    def _on_task_done(self, task: asyncio.Task) -> None:  # type: ignore[type-arg]
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("telegram polling task failed: %s", exc)

    async def _on_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message
        if not message or not message.text:
            return

        chat = message.chat
        is_group = chat.type in ("group", "supergroup")
        text = message.text

        is_mention = False
        if is_group and self._bot_username:
            mention = f"@{self._bot_username}"
            if mention in text:
                is_mention = True
                text = text.replace(mention, "").strip()

        if text.startswith("/start"):
            text = text.removeprefix("/start").strip() or "hello"

        sender = message.from_user
        sender_id = str(sender.id) if sender else ""
        sender_name = ""
        if sender:
            sender_name = sender.full_name or sender.username or sender_id

        attachments: list[Attachment] = []
        if message.document:
            doc = message.document
            attachments.append(
                Attachment(
                    mime_type=doc.mime_type or "application/octet-stream",
                    filename=doc.file_name,
                    size=doc.file_size,
                )
            )

        msg = InboundMessage(
            channel=self.name,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            thread_id=(
                str(message.message_thread_id) if message.message_thread_id else None
            ),
            conversation_id=str(chat.id),
            raw_event=update.to_dict(),
            is_group=is_group,
            is_mention=is_mention,
            attachments=attachments,
        )
        await self.dispatch(msg)

    async def send(self, message: OutboundMessage) -> str | None:
        if not self._bot:
            return None
        chat_id = message.conversation_id or message.recipient_id
        msg_id: str | None = None

        if message.text:
            sent = await self._bot.send_message(
                chat_id=chat_id,
                text=message.text,
                reply_to_message_id=(
                    int(message.thread_id) if message.thread_id else None
                ),
            )
            msg_id = str(sent.message_id)

        for att in message.attachments:
            if att.data:
                await self._bot.send_document(
                    chat_id=chat_id,
                    document=att.data,
                    filename=att.filename or "file",
                )
            elif att.url:
                await self._bot.send_message(chat_id=chat_id, text=att.url)

        return msg_id

    async def edit_message(
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        if not self._bot:
            return
        try:
            await self._bot.edit_message_text(
                chat_id=conversation_id,
                message_id=int(message_id),
                text=text,
            )
        except Exception:
            logger.warning("telegram message edit failed for msg_id=%s", message_id)

    async def send_typing(
        self,
        conversation_id: str,
        thread_id: str | None = None,
    ) -> None:
        if not self._bot:
            return
        try:
            await self._bot.send_chat_action(
                chat_id=conversation_id, action=ChatAction.TYPING
            )
        except Exception:
            logger.warning("telegram typing indicator failed")

    async def stop(self) -> None:
        if self._app:
            if self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        if hasattr(self, "_poll_task") and not self._poll_task.done():
            self._poll_task.cancel()
