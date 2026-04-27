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

import re
from dataclasses import dataclass
from enum import Enum

_RE_DOUBLE_NEWLINE = re.compile(r"\n{2,}")
_RE_FENCE_OPEN = re.compile(r"^```(\w*)", re.MULTILINE)


class ChunkMode(Enum):
    LENGTH = "length"
    NEWLINE = "newline"


CHANNEL_LIMITS: dict[str, int] = {
    "slack": 4000,
    "whatsapp": 4096,
    "google_chat": 4096,
    "telegram": 4096,
    "discord": 2000,
    "email": 0,
}


@dataclass
class ChunkConfig:
    mode: ChunkMode = ChunkMode.NEWLINE
    default_limit: int = 4000


class MessageChunker:
    def __init__(self, config: ChunkConfig | None = None) -> None:
        self._config = config or ChunkConfig()

    def chunk(self, text: str, channel: str) -> list[str]:
        limit = CHANNEL_LIMITS.get(channel, self._config.default_limit)
        if limit <= 0 or len(text) <= limit:
            return [text]

        if self._config.mode == ChunkMode.NEWLINE:
            return self._chunk_newline(text, limit)
        return self._chunk_length(text, limit)

    def _chunk_length(self, text: str, limit: int) -> list[str]:
        chunks: list[str] = []
        pos = 0
        while pos < len(text):
            end = min(pos + limit, len(text))
            if end < len(text):
                break_pos = self._find_break(text, pos, end)
                end = break_pos
            chunks.append(text[pos:end].rstrip())
            pos = end
            while pos < len(text) and text[pos] in (" ", "\n"):
                pos += 1
        return self._fixup_fences([c for c in chunks if c])

    def _chunk_newline(self, text: str, limit: int) -> list[str]:
        paragraphs = _RE_DOUBLE_NEWLINE.split(text)
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(para) > limit:
                    chunks.extend(self._chunk_length(para, limit))
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return self._fixup_fences(chunks)

    def _fixup_fences(self, chunks: list[str]) -> list[str]:
        result: list[str] = []
        fence_open = False
        fence_lang = ""

        for i, chunk in enumerate(chunks):
            if fence_open:
                chunk = f"```{fence_lang}\n{chunk}"

            opens = list(_RE_FENCE_OPEN.finditer(chunk))
            for m in opens:
                if fence_open:
                    fence_open = False
                    fence_lang = ""
                else:
                    fence_open = True
                    fence_lang = m.group(1)

            if fence_open and i < len(chunks) - 1:
                chunk = chunk + "\n```"

            result.append(chunk)

        return result

    def _find_break(self, text: str, start: int, end: int) -> int:
        segment = text[start:end]
        half = len(segment) // 2
        nl = segment.rfind("\n")
        if nl > half:
            return start + nl + 1
        ws = segment.rfind(" ")
        if ws > half:
            return start + ws + 1
        return end
