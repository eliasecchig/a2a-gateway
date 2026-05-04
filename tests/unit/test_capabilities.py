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

import httpx
import respx

from gateway.core.capabilities import AgentCapabilities, CapabilityDiscovery


class TestAgentCapabilities:
    def test_defaults(self):
        caps = AgentCapabilities()
        assert caps.streaming is False
        assert caps.max_message_length is None
        assert caps.supported_content_types == ["text/plain"]
        assert caps.raw == {}


class TestCapabilityDiscovery:
    @respx.mock
    async def test_discover_parses_agent_card(self):
        card = {
            "name": "test-agent",
            "capabilities": {"streaming": {"modes": ["sse"]}},
            "skills": [
                {
                    "id": "chat",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain", "application/json"],
                }
            ],
        }
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(200, json=card)
        )

        discovery = CapabilityDiscovery()
        caps = await discovery.discover("http://localhost:8001")

        assert caps.streaming is True
        assert caps.supported_content_types == [
            "application/json",
            "text/plain",
        ]
        assert caps.raw == card

    @respx.mock
    async def test_discover_no_streaming(self):
        card = {"name": "test-agent", "capabilities": {}, "skills": []}
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(200, json=card)
        )

        discovery = CapabilityDiscovery()
        caps = await discovery.discover("http://localhost:8001")

        assert caps.streaming is False
        assert caps.supported_content_types == ["text/plain"]

    @respx.mock
    async def test_discover_with_max_message_length(self):
        card = {
            "name": "test-agent",
            "capabilities": {},
            "maxMessageLength": 8192,
            "skills": [],
        }
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(200, json=card)
        )

        discovery = CapabilityDiscovery()
        caps = await discovery.discover("http://localhost:8001")

        assert caps.max_message_length == 8192

    @respx.mock
    async def test_discover_failure_returns_defaults(self):
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(404)
        )

        discovery = CapabilityDiscovery()
        caps = await discovery.discover("http://localhost:8001")

        assert caps.streaming is False
        assert caps.max_message_length is None

    @respx.mock
    async def test_discover_caches_result(self):
        card = {"name": "test-agent", "capabilities": {}, "skills": []}
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(200, json=card)
        )

        discovery = CapabilityDiscovery()
        assert discovery.get_cached() is None

        caps = await discovery.discover("http://localhost:8001")
        cached = discovery.get_cached()

        assert cached is caps

    @respx.mock
    async def test_discover_caches_on_failure(self):
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(500)
        )

        discovery = CapabilityDiscovery()
        await discovery.discover("http://localhost:8001")

        assert discovery.get_cached() is not None

    @respx.mock
    async def test_discover_strips_trailing_slash(self):
        card = {"name": "test-agent", "capabilities": {}, "skills": []}
        respx.get("http://localhost:8001/.well-known/agent-card.json").mock(
            return_value=httpx.Response(200, json=card)
        )

        discovery = CapabilityDiscovery()
        caps = await discovery.discover("http://localhost:8001/")

        assert caps.raw == card

    def test_parse_deduplicates_content_types(self):
        card = {
            "capabilities": {},
            "skills": [
                {"inputModes": ["text/plain"], "outputModes": ["text/plain"]},
                {"inputModes": ["text/plain", "image/png"], "outputModes": []},
            ],
        }
        caps = CapabilityDiscovery._parse(card)
        assert caps.supported_content_types == ["image/png", "text/plain"]
