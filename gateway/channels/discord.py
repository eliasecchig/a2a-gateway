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
import io
import logging

import discord

from gateway.core.channel import ChannelAdapter
from gateway.core.types import Attachment, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class DiscordAdapter(ChannelAdapter):
    channel_type = "discord"

    def __init__(
        self,
        bot_token: str,
        account_id: str = "default",
    ) -> None:
        super().__init__(account_id=account_id)
        self._bot_token = bot_token
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._setup_listeners()

    @property
    def supports_editing(self) -> bool:
        return True

    def _setup_listeners(self) -> None:
        @self._client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == self._client.user:
                return
            if message.author.bot:
                return

            text = message.content
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_group = not is_dm

            is_mention = False
            if self._client.user and self._client.user.mentioned_in(message):
                is_mention = True
                text = text.replace(f"<@{self._client.user.id}>", "").strip()

            attachments: list[Attachment] = []
            for att in message.attachments:
                attachments.append(
                    Attachment(
                        url=att.url,
                        mime_type=att.content_type or "application/octet-stream",
                        filename=att.filename,
                        size=att.size,
                    )
                )

            thread_id = None
            if isinstance(message.channel, discord.Thread):
                thread_id = str(message.channel.id)

            msg = InboundMessage(
                channel=self.name,
                sender_id=str(message.author.id),
                sender_name=message.author.display_name,
                text=text,
                thread_id=thread_id,
                conversation_id=str(message.channel.id),
                raw_event={
                    "message_id": message.id,
                    "channel_id": message.channel.id,
                    "guild_id": (message.guild.id if message.guild else None),
                },
                is_group=is_group,
                is_mention=is_mention,
                attachments=attachments,
            )
            await self.dispatch(msg)

    async def start(self) -> None:
        self._connect_task = asyncio.create_task(
            self._client.start(self._bot_token),
            name=f"discord-connect-{self._account_id}",
        )
        self._connect_task.add_done_callback(self._on_task_done)
        logger.info("discord adapter started (account=%s)", self._account_id)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("discord client task failed: %s", exc)

    async def stop(self) -> None:
        await self._client.close()
        if hasattr(self, "_connect_task") and not self._connect_task.done():
            self._connect_task.cancel()

    async def send(self, message: OutboundMessage) -> str | None:
        try:
            channel_id = int(message.conversation_id or message.recipient_id)
        except (ValueError, TypeError):
            logger.error("invalid discord channel id: %s", message.conversation_id)
            return None
        channel = self._client.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            logger.error(
                "discord channel %s not found or not messageable",
                message.conversation_id,
            )
            return None

        sent: discord.Message | None = None
        if message.text:
            sent = await channel.send(message.text)

        for att in message.attachments:
            if att.data:
                f = discord.File(
                    io.BytesIO(att.data),
                    filename=att.filename or "file",
                )
                await channel.send(file=f)
            elif att.url:
                await channel.send(att.url)

        return str(sent.id) if sent else None

    async def edit_message(
        self,
        message_id: str,
        conversation_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        try:
            ch_id = int(conversation_id)
            m_id = int(message_id)
        except (ValueError, TypeError):
            logger.warning("invalid discord ids: channel=%s msg=%s", conversation_id, message_id)
            return
        channel = self._client.get_channel(ch_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            return
        try:
            msg = await channel.fetch_message(m_id)
            await msg.edit(content=text)
        except Exception:
            logger.warning("discord message edit failed for msg_id=%s", message_id)

    async def send_typing(
        self,
        conversation_id: str,
        thread_id: str | None = None,
    ) -> None:
        try:
            ch_id = int(conversation_id)
        except (ValueError, TypeError):
            return
        channel = self._client.get_channel(ch_id)
        if channel and isinstance(channel, discord.abc.Messageable):
            try:
                await channel.typing()
            except Exception:
                logger.debug("discord typing indicator failed")
