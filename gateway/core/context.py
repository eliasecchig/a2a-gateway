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

import logging
from dataclasses import dataclass

from gateway.core.session import SessionState

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = (
    "[Channel: {channel} | Supports: {supports} | Max message: {max_length} chars]"
)
_DEFAULT_TEMPLATE_NO_LIMIT = "[Channel: {channel} | Supports: {supports}]"


@dataclass(slots=True)
class ChannelMeta:
    display_name: str
    supports: list[str]
    max_message_length: int


CHANNEL_METADATA: dict[str, ChannelMeta] = {
    "slack": ChannelMeta(
        "Slack",
        ["markdown", "threads", "reactions", "editing"],
        4000,
    ),
    "whatsapp": ChannelMeta("WhatsApp", ["read receipts"], 4096),
    "google_chat": ChannelMeta(
        "Google Chat",
        ["markdown", "threads", "cards"],
        4096,
    ),
    "discord": ChannelMeta(
        "Discord",
        ["markdown", "threads", "reactions", "editing"],
        2000,
    ),
    "telegram": ChannelMeta("Telegram", ["markdown", "reactions"], 4096),
    "email": ChannelMeta("Email", ["html", "attachments", "threads"], 0),
}


@dataclass(slots=True)
class _ChannelConfig:
    template: str
    enabled: bool


class ChannelContextInjector:
    def __init__(self) -> None:
        self._channels: dict[str, _ChannelConfig] = {}

    def register(
        self,
        channel: str,
        *,
        template: str = "",
        enabled: bool = True,
    ) -> None:
        self._channels[channel] = _ChannelConfig(template=template, enabled=enabled)

    @staticmethod
    def _base_channel(channel: str) -> str:
        return channel.partition(":")[0]

    def inject(self, text: str, channel: str, session: SessionState) -> str:
        if session.context_id is not None:
            return text

        cfg = self._channels.get(channel)
        if cfg is None:
            return text
        if not cfg.enabled:
            return text

        base = self._base_channel(channel)
        meta = CHANNEL_METADATA.get(base)
        if meta is None:
            logger.debug("no metadata for channel %s, skipping context", base)
            return text

        template = cfg.template
        if not template:
            template = (
                _DEFAULT_TEMPLATE
                if meta.max_message_length > 0
                else _DEFAULT_TEMPLATE_NO_LIMIT
            )

        try:
            rendered = template.format_map(
                {
                    "channel": meta.display_name,
                    "supports": ", ".join(meta.supports),
                    "max_length": meta.max_message_length,
                }
            )
        except KeyError:
            logger.warning("bad context_template for %s, skipping", channel)
            return text
        return f"{rendered}\n\n{text}"
