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

from abc import ABC, abstractmethod
from typing import Any

from gateway.core.types import (
    Button,
    Card,
    InteractiveElement,
    Select,
)


class InteractiveRenderer(ABC):
    @abstractmethod
    def render(self, elements: list[InteractiveElement]) -> dict[str, Any]: ...

    def render_fallback_text(self, elements: list[InteractiveElement]) -> str:
        parts: list[str] = []
        for el in elements:
            if isinstance(el, Button):
                parts.append(f"[{el.label}]")
            elif isinstance(el, Select):
                opts = ", ".join(o.label for o in el.options)
                parts.append(f"{el.placeholder or 'Choose'}: {opts}")
            elif isinstance(el, Card):
                lines = [f"**{el.title}**"]
                if el.subtitle:
                    lines.append(el.subtitle)
                if el.body:
                    lines.append(el.body)
                for btn in el.buttons:
                    lines.append(f"  [{btn.label}]")
                parts.append("\n".join(lines))
        return "\n".join(parts)


class SlackBlockKitRenderer(InteractiveRenderer):
    def render(self, elements: list[InteractiveElement]) -> dict[str, Any]:
        blocks: list[dict] = []
        for el in elements:
            if isinstance(el, Button):
                blocks.append(self._render_button(el))
            elif isinstance(el, Select):
                blocks.append(self._render_select(el))
            elif isinstance(el, Card):
                blocks.extend(self._render_card(el))
        return {"blocks": blocks}

    @staticmethod
    def _render_button(btn: Button) -> dict:
        style_map = {"primary": "primary", "danger": "danger"}
        element: dict[str, Any] = {
            "type": "button",
            "text": {"type": "plain_text", "text": btn.label},
            "action_id": btn.action_id,
            "value": btn.value,
        }
        if btn.style in style_map:
            element["style"] = style_map[btn.style]
        return {
            "type": "actions",
            "elements": [element],
        }

    @staticmethod
    def _render_select(sel: Select) -> dict:
        return {
            "type": "actions",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": sel.action_id,
                    "placeholder": {
                        "type": "plain_text",
                        "text": sel.placeholder or "Choose...",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": o.label,
                            },
                            "value": o.value,
                        }
                        for o in sel.options
                    ],
                }
            ],
        }

    @staticmethod
    def _render_card(card: Card) -> list[dict]:
        blocks: list[dict] = []
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": card.title},
            }
        )
        if card.subtitle or card.body:
            text = card.subtitle
            if card.body:
                text = f"{text}\n{card.body}" if text else card.body
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            )
        if card.image_url:
            blocks.append(
                {
                    "type": "image",
                    "image_url": card.image_url,
                    "alt_text": card.title,
                }
            )
        if card.buttons:
            elements = []
            for btn in card.buttons:
                elements.append(
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": btn.label,
                        },
                        "action_id": btn.action_id,
                        "value": btn.value,
                    }
                )
            blocks.append({"type": "actions", "elements": elements})
        return blocks


class FallbackTextRenderer(InteractiveRenderer):
    def render(self, elements: list[InteractiveElement]) -> dict[str, Any]:
        return {"text": self.render_fallback_text(elements)}


_RENDERERS: dict[str, type[InteractiveRenderer]] = {
    "slack": SlackBlockKitRenderer,
}

_cache: dict[str, InteractiveRenderer] = {}


def get_interactive_renderer(channel: str) -> InteractiveRenderer:
    if channel not in _cache:
        cls = _RENDERERS.get(channel, FallbackTextRenderer)
        _cache[channel] = cls()
    return _cache[channel]
