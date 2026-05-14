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
from gateway.core.media import extract_file_parts

logger = logging.getLogger(__name__)

_STREAM_READ_TIMEOUT = 300.0
_VERSION_HEADER = "A2A-Version"
_PROTOCOL_VERSION = "1.0"
_TERMINAL_STATES = (
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
)

_FINAL_FLAG_KEY = "__a2a_final__"
_FORCE_TEXT_KEY = "__a2a_force_text__"


def _unwrap_result(result: dict[str, Any]) -> dict[str, Any]:
    if "task" in result and isinstance(result["task"], dict):
        return result["task"]
    if "message" in result and isinstance(result["message"], dict):
        msg = result["message"]
        return {
            "id": None,
            "contextId": msg.get("contextId"),
            "status": {"message": msg},
        }
    if "statusUpdate" in result and isinstance(result["statusUpdate"], dict):
        update = result["statusUpdate"]
        unwrapped: dict[str, Any] = {
            "id": update.get("taskId"),
            "contextId": update.get("contextId"),
            "status": update.get("status", {}),
            _FORCE_TEXT_KEY: True,
        }
        if update.get("final") is True:
            unwrapped[_FINAL_FLAG_KEY] = True
        return unwrapped
    if "artifactUpdate" in result and isinstance(result["artifactUpdate"], dict):
        update = result["artifactUpdate"]
        artifact = update.get("artifact", {})
        return {
            "id": update.get("taskId"),
            "contextId": update.get("contextId"),
            "status": {"state": ""},
            "artifacts": [artifact],
            _FORCE_TEXT_KEY: True,
        }
    return {}


def _extract_part_text(parts: list[dict[str, Any]]) -> str:
    return "".join(part["text"] for part in parts if "text" in part)


def _extract_artifact_text(task: dict[str, Any]) -> str:
    parts_text: list[str] = []
    for artifact in task.get("artifacts") or []:
        parts_text.append(_extract_part_text(artifact.get("parts", [])))
    return "".join(parts_text)


def _extract_text_from_task(task: dict[str, Any]) -> str:
    text = _extract_artifact_text(task)
    if text:
        return text

    status = task.get("status", {})
    msg = status.get("message") or {}
    return _extract_part_text(msg.get("parts", []))


def _build_params(
    text: str,
    context_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "message": {
            "role": "ROLE_USER",
            "parts": [{"text": text}],
            "messageId": uuid.uuid4().hex,
        },
    }
    if context_id:
        params["message"]["contextId"] = context_id
    if task_id:
        params["message"]["taskId"] = task_id
    return params


class A2AClient:
    """Minimal A2A protocol client (JSON-RPC 2.0, A2A protocol v1.0)."""

    def __init__(
        self,
        server_url: str,
        auth: AuthProvider | None = None,
        agent_card_path: str = "/.well-known/agent-card.json",
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self._agent_card_path = agent_card_path
        self._http = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )
        self._request_id = itertools.count(1)
        self._auth = auth

    async def _request_headers(self) -> dict[str, str]:
        headers = {_VERSION_HEADER: _PROTOCOL_VERSION}
        if self._auth is not None:
            headers.update(await self._auth.get_headers())
        return headers

    async def close(self) -> None:
        await self._http.aclose()

    async def get_agent_card(self) -> dict[str, Any]:
        url = self.server_url.rstrip("/") + self._agent_card_path
        headers = await self._request_headers()
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
            "method": "SendMessage",
            "params": _build_params(text, context_id, task_id),
        }

        headers = await self._request_headers()
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
            "method": "SendStreamingMessage",
            "params": _build_params(text, context_id, task_id),
        }

        headers = await self._request_headers()
        async with self._http.stream(
            "POST",
            self.server_url,
            json=payload,
            headers=headers,
            timeout=httpx.Timeout(60.0, read=_STREAM_READ_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            event_type: str | None = None
            async for line in resp.aiter_lines():
                if line == "":
                    event_type = None
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                    continue
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    body = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("malformed SSE data, skipping: %s", data[:200])
                    continue
                if event_type == "error":
                    if "error" in body:
                        raise A2AError(body["error"])
                    continue
                yield A2AStreamEvent.from_result(body.get("result", {}))


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
        task = _unwrap_result(result)
        status = task.get("status", {})
        is_final = (
            status.get("state") in _TERMINAL_STATES
            or "message" in result
            or task.get(_FINAL_FLAG_KEY) is True
        )
        force_text = task.get(_FORCE_TEXT_KEY) is True

        if is_final or force_text:
            text = _extract_text_from_task(task)
        else:
            text = _extract_artifact_text(task)

        return cls(
            text=text,
            is_final=is_final,
            context_id=task.get("contextId"),
            task_id=task.get("id"),
            raw=result,
            attachments=extract_file_parts(task) if is_final else [],
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
        task = _unwrap_result(result)
        text = _extract_text_from_task(task) or "(no response)"

        return cls(
            text=text,
            context_id=task.get("contextId"),
            task_id=task.get("id"),
            raw=result,
            attachments=extract_file_parts(task),
        )


class A2AError(Exception):
    def __init__(self, error: dict[str, Any]) -> None:
        self.code = error.get("code", -1)
        self.message = error.get("message", "unknown error")
        super().__init__(f"A2A error {self.code}: {self.message}")
