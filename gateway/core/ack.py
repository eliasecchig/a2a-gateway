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

logger = logging.getLogger(__name__)


@dataclass
class AckConfig:
    slack: dict[str, str] = field(default_factory=lambda: {"emoji": "eyes"})
    whatsapp: dict[str, bool] = field(default_factory=lambda: {"read_receipts": True})
    google_chat: dict[str, str] = field(default_factory=lambda: {"emoji": "eyes"})
