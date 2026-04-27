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

import html
import re
from abc import ABC, abstractmethod


class MarkdownAdapter(ABC):
    @abstractmethod
    def format_text(self, text: str) -> str: ...


class PassthroughMarkdown(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        return text


class WhatsAppMarkdownAdapter(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        parts = re.split(r"(```[\s\S]*?```)", text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                result.append(part)
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        text = re.sub(r"__(.+?)__", r"_\1_", text)
        text = re.sub(r"~~(.+?)~~", r"~\1~", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
        return text


class SlackMarkdownAdapter(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        text = html.unescape(text)
        parts = re.split(r"(```[\s\S]*?```)", text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                result.append(part)
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
        return text


_ADAPTERS: dict[str, type[MarkdownAdapter]] = {
    "whatsapp": WhatsAppMarkdownAdapter,
    "slack": SlackMarkdownAdapter,
    "google_chat": PassthroughMarkdown,
    "telegram": PassthroughMarkdown,
    "discord": PassthroughMarkdown,
    "email": PassthroughMarkdown,
}

_cache: dict[str, MarkdownAdapter] = {}


def get_markdown_adapter(channel: str) -> MarkdownAdapter:
    if channel not in _cache:
        cls = _ADAPTERS.get(channel, PassthroughMarkdown)
        _cache[channel] = cls()
    return _cache[channel]
