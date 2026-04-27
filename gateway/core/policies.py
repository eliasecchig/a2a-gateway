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
from enum import Enum

from gateway.core.types import InboundMessage

logger = logging.getLogger(__name__)


class GroupMode(Enum):
    OPEN = "open"
    MENTION_ONLY = "mention_only"
    DISABLED = "disabled"


@dataclass
class GroupPolicyConfig:
    mode: GroupMode = GroupMode.OPEN
    overrides: dict[str, GroupMode] = field(default_factory=dict)


class GroupPolicyChecker:
    def __init__(self, policies: dict[str, GroupPolicyConfig] | None = None) -> None:
        self._policies = policies or {}

    def should_process(self, msg: InboundMessage) -> bool:
        if not msg.is_group:
            return True

        base_channel = msg.channel.partition(":")[0]
        policy = self._policies.get(base_channel, GroupPolicyConfig())

        conv_id = msg.conversation_id or ""
        mode = policy.overrides.get(conv_id, policy.mode)

        if mode == GroupMode.DISABLED:
            logger.debug("group policy: blocked in %s (disabled)", conv_id)
            return False
        if mode == GroupMode.MENTION_ONLY and not msg.is_mention:
            logger.debug("group policy: no mention in %s", conv_id)
            return False
        return True
