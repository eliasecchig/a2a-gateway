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

_RE_CODE_BLOCK = re.compile(r"(```[\s\S]*?```)")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_UNDERLINE = re.compile(r"__(.+?)__")
_RE_STRIKE = re.compile(r"~~(.+?)~~")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_RE_IMAGE = re.compile(r"!\[.*?\]\(.*?\)")
_RE_HR = re.compile(r"^---+$", re.MULTILINE)


class MarkdownAdapter(ABC):
    @abstractmethod
    def format_text(self, text: str) -> str: ...


class PassthroughMarkdown(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        return text


class WhatsAppMarkdownAdapter(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        parts = _RE_CODE_BLOCK.split(text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                result.append(part)
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        text = _RE_BOLD.sub(r"*\1*", text)
        text = _RE_UNDERLINE.sub(r"_\1_", text)
        text = _RE_STRIKE.sub(r"~\1~", text)
        text = _RE_LINK.sub(r"\1 (\2)", text)
        text = _RE_HEADING.sub("", text)
        text = _RE_IMAGE.sub("", text)
        text = _RE_HR.sub("", text)
        return text


class SlackMarkdownAdapter(MarkdownAdapter):
    def format_text(self, text: str) -> str:
        text = html.unescape(text)
        parts = _RE_CODE_BLOCK.split(text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                result.append(part)
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        text = _RE_BOLD.sub(r"*\1*", text)
        text = _RE_LINK.sub(r"<\2|\1>", text)
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
