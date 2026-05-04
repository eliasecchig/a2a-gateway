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
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_UNDERLINE = re.compile(r"__(.+?)__")
_RE_STRIKE = re.compile(r"~~(.+?)~~")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_RE_HEADING_FULL = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
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


class TelegramMarkdownAdapter(MarkdownAdapter):
    """Converts standard markdown to Telegram HTML."""

    def format_text(self, text: str) -> str:
        parts = _RE_CODE_BLOCK.split(text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                inner = part[3:-3]
                first_nl = inner.find("\n")
                if first_nl != -1:
                    hint = inner[:first_nl].strip()
                    if hint and " " not in hint:
                        inner = inner[first_nl + 1 :]
                result.append(f"<pre>{html.escape(inner)}</pre>")
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        codes: list[str] = []

        def _save(m: re.Match[str]) -> str:
            codes.append(html.escape(m.group(1)))
            return f"\x00{len(codes) - 1}\x00"

        text = _RE_INLINE_CODE.sub(_save, text)
        text = html.escape(text)
        text = _RE_BOLD.sub(r"<b>\1</b>", text)
        text = _RE_UNDERLINE.sub(r"<u>\1</u>", text)
        text = _RE_STRIKE.sub(r"<s>\1</s>", text)
        text = _RE_LINK.sub(r'<a href="\2">\1</a>', text)
        text = _RE_HEADING.sub("", text)
        text = _RE_IMAGE.sub("", text)
        text = _RE_HR.sub("", text)
        for i, code in enumerate(codes):
            text = text.replace(f"\x00{i}\x00", f"<code>{code}</code>")
        return text


class EmailMarkdownAdapter(MarkdownAdapter):
    """Converts standard markdown to email HTML."""

    def format_text(self, text: str) -> str:
        parts = _RE_CODE_BLOCK.split(text)
        result: list[str] = []
        for part in parts:
            if part.startswith("```"):
                inner = part[3:-3]
                first_nl = inner.find("\n")
                if first_nl != -1:
                    hint = inner[:first_nl].strip()
                    if hint and " " not in hint:
                        inner = inner[first_nl + 1 :]
                result.append(f"<pre>{html.escape(inner)}</pre>")
            else:
                result.append(self._convert_inline(part))
        return "".join(result)

    def _convert_inline(self, text: str) -> str:
        codes: list[str] = []

        def _save(m: re.Match[str]) -> str:
            codes.append(html.escape(m.group(1)))
            return f"\x00{len(codes) - 1}\x00"

        text = _RE_INLINE_CODE.sub(_save, text)
        text = html.escape(text)
        text = _RE_BOLD.sub(r"<b>\1</b>", text)
        text = _RE_UNDERLINE.sub(r"<u>\1</u>", text)
        text = _RE_STRIKE.sub(r"<s>\1</s>", text)
        text = _RE_LINK.sub(r'<a href="\2">\1</a>', text)

        def _heading(m: re.Match[str]) -> str:
            level = len(m.group(1))
            return f"<h{level}>{m.group(2)}</h{level}>"

        text = _RE_HEADING_FULL.sub(_heading, text)
        text = _RE_IMAGE.sub("", text)
        text = _RE_HR.sub("<hr>", text)
        for i, code in enumerate(codes):
            text = text.replace(f"\x00{i}\x00", f"<code>{code}</code>")
        text = text.replace("\n", "<br>\n")
        return text


_ADAPTERS: dict[str, type[MarkdownAdapter]] = {
    "whatsapp": WhatsAppMarkdownAdapter,
    "slack": SlackMarkdownAdapter,
    "google_chat": PassthroughMarkdown,
    "telegram": TelegramMarkdownAdapter,
    "discord": PassthroughMarkdown,
    "email": EmailMarkdownAdapter,
}

_cache: dict[str, MarkdownAdapter] = {}


def get_markdown_adapter(channel: str) -> MarkdownAdapter:
    if channel not in _cache:
        cls = _ADAPTERS.get(channel, PassthroughMarkdown)
        _cache[channel] = cls()
    return _cache[channel]
