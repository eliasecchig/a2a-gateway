"""Minimal A2A echo agent for local gateway testing."""

from __future__ import annotations

import logging

import uvicorn
from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.applications import Starlette


class EchoExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        text = get_message_text(message) if message else ""
        reply = new_text_message(
            text=f"Hello! You said: {text}",
            context_id=context.context_id,
        )
        await event_queue.enqueue_event(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="dummy_agent",
        description="Minimal echo agent for testing the a2a-gateway.",
        version="1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="echo",
                name="echo",
                description="Echoes the user's message back with a greeting.",
                tags=["echo", "test"],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=EchoExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ]
    return Starlette(routes=routes)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(build_app(), host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
