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

import base64
import binascii
import logging
from typing import Any

from gateway.core.types import Attachment

logger = logging.getLogger(__name__)


def extract_file_parts(result: dict[str, Any]) -> list[Attachment]:
    attachments: list[Attachment] = []

    for artifact in result.get("artifacts") or []:
        _extract_from_parts(artifact.get("parts", []), attachments)

    status_msg = (result.get("status") or {}).get("message") or {}
    _extract_from_parts(status_msg.get("parts", []), attachments)

    return attachments


def _extract_from_parts(parts: list[dict[str, Any]], out: list[Attachment]) -> None:
    for part in parts:
        if "text" in part:
            continue
        if "url" not in part and "raw" not in part:
            continue
        att = Attachment(
            mime_type=part.get("mediaType", "application/octet-stream"),
            filename=part.get("filename"),
        )
        if "url" in part:
            att.url = part["url"]
        else:
            try:
                raw = base64.b64decode(part["raw"])
            except (binascii.Error, ValueError):
                logger.warning("malformed base64 in file part, skipping")
                continue
            att.data = raw
            att.size = len(raw)
        out.append(att)
