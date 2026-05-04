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
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AgentCapabilities:
    streaming: bool = False
    max_message_length: int | None = None
    supported_content_types: list[str] = field(default_factory=lambda: ["text/plain"])
    raw: dict = field(default_factory=dict)


class CapabilityDiscovery:
    def __init__(self, agent_card_path: str = "/.well-known/agent-card.json") -> None:
        self._agent_card_path = agent_card_path
        self._cached: AgentCapabilities | None = None

    async def discover(self, server_url: str) -> AgentCapabilities:
        url = server_url.rstrip("/") + self._agent_card_path
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                card = resp.json()
        except Exception:
            logger.warning("capability discovery failed for %s", url, exc_info=True)
            caps = AgentCapabilities()
            self._cached = caps
            return caps

        caps = self._parse(card)
        self._cached = caps
        return caps

    def get_cached(self) -> AgentCapabilities | None:
        return self._cached

    @staticmethod
    def _parse(card: dict[str, Any]) -> AgentCapabilities:
        capabilities = card.get("capabilities", {})
        streaming = capabilities.get("streaming", {})

        content_types: set[str] = set()
        for skill in card.get("skills", []):
            content_types.update(skill.get("inputModes", []))
            content_types.update(skill.get("outputModes", []))

        return AgentCapabilities(
            streaming=bool(streaming),
            max_message_length=card.get("maxMessageLength"),
            supported_content_types=sorted(content_types) or ["text/plain"],
            raw=card,
        )
