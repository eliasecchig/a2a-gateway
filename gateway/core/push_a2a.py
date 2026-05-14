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

"""A2A push endpoint: deliver A2A messages to channel adapters."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from a2a.helpers import get_message_text
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    Part,
    Role,
)

from gateway.core.types import OutboundMessage

if TYPE_CHECKING:
    from fastapi import FastAPI

    from gateway.core.router import Router

logger = logging.getLogger(__name__)

PUSH_PATH = "/push"

CHANNEL_KEY = "gateway/channel"
RECIPIENT_KEY = "gateway/recipient_id"
THREAD_KEY = "gateway/thread_id"
CONVERSATION_KEY = "gateway/conversation_id"


class PushRoutingError(Exception):
    """Raised when an inbound A2A message lacks valid routing metadata."""


def _require_string(metadata: dict, key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise PushRoutingError(f"missing or empty required metadata field: {key!r}")
    return value


def _optional_string(metadata: dict, key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise PushRoutingError(
            f"metadata field {key!r} must be a non-empty string when present"
        )
    return value


class GatewayPushExecutor(AgentExecutor):
    """Routes inbound A2A messages to a channel adapter via the Router."""

    def __init__(self, router: Router) -> None:
        self._router = router

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        if message is None:
            raise PushRoutingError("message is required")

        metadata = dict(message.metadata or {})
        channel = _require_string(metadata, CHANNEL_KEY)
        recipient_id = _require_string(metadata, RECIPIENT_KEY)
        thread_id = _optional_string(metadata, THREAD_KEY)
        conversation_id = _optional_string(metadata, CONVERSATION_KEY)
        text = get_message_text(message)
        if not text:
            raise PushRoutingError("message has no text parts")

        adapter = self._router.channels.get(channel)
        if adapter is None:
            available = sorted(self._router.channels)
            raise PushRoutingError(
                f"channel {channel!r} not registered (available: {available})"
            )

        outbound = OutboundMessage(
            channel=channel,
            recipient_id=recipient_id,
            text=text,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )
        try:
            message_id = await adapter.send(outbound)
        except Exception as exc:
            logger.exception("push delivery failed on channel %s", channel)
            raise PushRoutingError(f"adapter send failed: {exc}") from exc

        reply_meta = {"gateway/message_id": message_id} if message_id else None
        reply = Message(
            message_id=uuid.uuid4().hex,
            role=Role.ROLE_AGENT,
            parts=[Part(text=f"delivered to {channel}")],
            context_id=context.context_id,
            metadata=reply_meta,
        )
        await event_queue.enqueue_event(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def build_push_agent_card(router: Router) -> AgentCard:
    skills = [
        AgentSkill(
            id=f"send_{name}",
            name=f"Send via {name}",
            description=(
                f"Deliver a message through the {name!r} channel adapter. "
                f"Set message.metadata[{CHANNEL_KEY!r}] to {name!r} and "
                f"message.metadata[{RECIPIENT_KEY!r}] to the platform "
                "user/chat ID."
            ),
            tags=["push", "outbound", name],
        )
        for name in sorted(router.channels)
    ]
    return AgentCard(
        name="a2a-gateway-push",
        description=(
            "Outbound delivery surface. Send an A2A message with channel "
            "routing metadata and the gateway forwards it to the matching "
            "channel adapter."
        ),
        version="1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=skills,
    )


def mount_push_a2a_routes(app: FastAPI, router: Router) -> None:
    agent_card = build_push_agent_card(router)
    handler = DefaultRequestHandler(
        agent_executor=GatewayPushExecutor(router),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    for route in create_agent_card_routes(
        agent_card, card_url=f"{PUSH_PATH}/.well-known/agent-card.json"
    ):
        app.router.routes.append(route)
    for route in create_jsonrpc_routes(handler, rpc_url=PUSH_PATH):
        app.router.routes.append(route)
