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

import itertools
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from gateway.core.auth import AuthProvider

logger = logging.getLogger(__name__)

_STREAM_READ_TIMEOUT = 300.0


def _extract_text_from_result(result: dict[str, Any]) -> str:
    parts_text: list[str] = []
    for artifact in result.get("artifacts") or []:
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                parts_text.append(part.get("text", ""))

    if not parts_text:
        status = result.get("status", {})
        msg = status.get("message") or {}
        for part in msg.get("parts", []):
            if part.get("kind") == "text":
                parts_text.append(part.get("text", ""))

    return "".join(parts_text)


def _build_params(
    text: str,
    context_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": uuid.uuid4().hex,
        },
    }
    if context_id:
        params["message"]["contextId"] = context_id
    if task_id:
        params["message"]["taskId"] = task_id
    return params


class A2AClient:
    """Minimal A2A protocol client (JSON-RPC 2.0, message/send)."""

    def __init__(
        self,
        server_url: str,
        auth: AuthProvider | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=60.0)
        self._request_id = itertools.count(1)
        self._auth = auth

    async def _auth_headers(self) -> dict[str, str]:
        if self._auth is None:
            return {}
        return await self._auth.get_headers()

    async def close(self) -> None:
        await self._http.aclose()

    async def get_agent_card(self) -> dict[str, Any]:
        url = self.server_url.rstrip("/") + "/.well-known/agent.json"
        headers = await self._auth_headers()
        resp = await self._http.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def send_message(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> A2AResponse:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_id),
            "method": "message/send",
            "params": _build_params(text, context_id, task_id),
        }

        headers = await self._auth_headers()
        resp = await self._http.post(self.server_url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()

        if "error" in body:
            raise A2AError(body["error"])

        return A2AResponse.from_result(body.get("result", {}))

    async def send_message_stream(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> AsyncIterator[A2AStreamEvent]:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_id),
            "method": "message/stream",
            "params": _build_params(text, context_id, task_id),
        }

        headers = await self._auth_headers()
        async with self._http.stream(
            "POST",
            self.server_url,
            json=payload,
            headers=headers,
            timeout=httpx.Timeout(60.0, read=_STREAM_READ_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("malformed SSE data, skipping: %s", data[:200])
                    continue
                result = event.get("result", {})
                yield A2AStreamEvent.from_result(result)


class A2AStreamEvent:
    def __init__(  # noqa: PLR0917
        self,
        text: str,
        is_final: bool = False,
        context_id: str | None = None,
        task_id: str | None = None,
        raw: dict[str, Any] | None = None,
        attachments: list[Any] | None = None,
    ) -> None:
        self.text = text
        self.is_final = is_final
        self.context_id = context_id
        self.task_id = task_id
        self.raw = raw or {}
        self.attachments = attachments or []

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> A2AStreamEvent:
        from gateway.core.media import extract_file_parts

        status = result.get("status", {})
        is_final = status.get("state") in ("completed", "failed", "canceled")

        return cls(
            text=_extract_text_from_result(result),
            is_final=is_final,
            context_id=result.get("contextId"),
            task_id=result.get("id"),
            raw=result,
            attachments=extract_file_parts(result) if is_final else [],
        )


class A2AResponse:
    def __init__(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
        raw: dict[str, Any] | None = None,
        attachments: list[Any] | None = None,
    ) -> None:
        self.text = text
        self.context_id = context_id
        self.task_id = task_id
        self.raw = raw or {}
        self.attachments = attachments or []

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> A2AResponse:
        from gateway.core.media import extract_file_parts

        text = _extract_text_from_result(result) or "(no response)"

        return cls(
            text=text,
            context_id=result.get("contextId"),
            task_id=result.get("id"),
            raw=result,
            attachments=extract_file_parts(result),
        )


class A2AError(Exception):
    def __init__(self, error: dict[str, Any]) -> None:
        self.code = error.get("code", -1)
        self.message = error.get("message", "unknown error")
        super().__init__(f"A2A error {self.code}: {self.message}")
