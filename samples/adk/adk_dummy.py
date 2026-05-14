"""ADK-based dummy agent (a2a-sdk 0.3) on port 8002.

Runs in its own uv project under samples/adk/ to avoid a2a-sdk version
conflict with the main gateway venv. From samples/adk/:

    uv sync
    uv run python adk_dummy.py
"""

from __future__ import annotations

import logging

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent

logger = logging.getLogger(__name__)


agent = Agent(
    model="gemini-2.0-flash",
    name="adk_dummy_agent",
    description="ADK-based dummy agent (a2a-sdk 0.3) for backward-compat testing.",
    instruction=(
        "You are a helpful test agent called Dummy. "
        "When a user sends you a message, greet them warmly "
        "and echo back what they said. Keep it short."
    ),
)

app = to_a2a(agent, port=8002)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8002)
