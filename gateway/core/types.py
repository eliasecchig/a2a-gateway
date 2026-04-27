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

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Attachment:
    url: str | None = None
    data: bytes | None = None
    mime_type: str = "application/octet-stream"
    filename: str | None = None
    size: int | None = None


@dataclass(slots=True)
class InboundMessage:
    channel: str
    sender_id: str
    sender_name: str
    text: str
    thread_id: str | None = None
    conversation_id: str | None = None
    raw_event: dict[str, Any] = field(default_factory=dict)
    is_group: bool = False
    is_mention: bool = False
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(slots=True)
class Button:
    label: str
    action_id: str
    value: str = ""
    style: str = "default"


@dataclass(slots=True)
class SelectOption:
    label: str
    value: str


@dataclass(slots=True)
class Select:
    action_id: str
    placeholder: str = ""
    options: list[SelectOption] = field(default_factory=list)


@dataclass(slots=True)
class Card:
    title: str
    subtitle: str = ""
    image_url: str | None = None
    body: str = ""
    buttons: list[Button] = field(default_factory=list)
    selects: list[Select] = field(default_factory=list)


InteractiveElement = Button | Select | Card


@dataclass(slots=True)
class OutboundMessage:
    channel: str
    recipient_id: str
    text: str
    thread_id: str | None = None
    conversation_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    interactive: list[InteractiveElement] = field(default_factory=list)
