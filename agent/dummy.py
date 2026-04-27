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

"""Dummy ADK agent exposed as an A2A server on port 8001."""

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent

agent = Agent(
    model="gemini-2.0-flash",
    name="dummy_agent",
    description="A test agent for the a2a-gateway. Echoes messages with a friendly greeting.",
    instruction=(
        "You are a helpful test agent called Dummy. "
        "When a user sends you a message, greet them warmly "
        "and echo back what they said. Keep it short."
    ),
)

app = to_a2a(agent, port=8001)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
