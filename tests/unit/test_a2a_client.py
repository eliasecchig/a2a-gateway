from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from gateway.core.a2a_client import A2AClient, A2AError, A2AResponse


@pytest.mark.asyncio
class TestA2AClient:
    @respx.mock
    async def test_send_message_payload_structure(self):
        route = respx.post("http://localhost:8001").mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "id": "task-1",
                        "contextId": "ctx-1",
                        "artifacts": [{"parts": [{"text": "hi"}]}],
                    },
                },
            )
        )
        client = A2AClient("http://localhost:8001")
        resp = await client.send_message("hello")
        assert resp.text == "hi"

        request = route.calls.last.request
        body = request.extensions.get("json") or __import__("json").loads(request.content)
        assert body["method"] == "SendMessage"
        assert body["jsonrpc"] == "2.0"
        assert body["params"]["message"]["parts"][0]["text"] == "hello"
        assert "kind" not in body["params"]["message"]["parts"][0]
        assert request.headers["A2A-Version"] == "1.0"
        await client.close()

    @respx.mock
    async def test_context_and_task_id_included(self):
        route = respx.post("http://localhost:8001").mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "id": "t1",
                        "contextId": "c1",
                        "artifacts": [{"parts": [{"text": "ok"}]}],
                    },
                },
            )
        )
        client = A2AClient("http://localhost:8001")
        await client.send_message("hi", context_id="ctx-1", task_id="task-1")

        request = route.calls.last.request
        body = __import__("json").loads(request.content)
        assert body["params"]["message"]["contextId"] == "ctx-1"
        assert body["params"]["message"]["taskId"] == "task-1"
        await client.close()

    @respx.mock
    async def test_error_response_raises(self):
        respx.post("http://localhost:8001").mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32000, "message": "agent error"},
                },
            )
        )
        client = A2AClient("http://localhost:8001")
        with pytest.raises(A2AError, match="agent error"):
            await client.send_message("hi")
        await client.close()

    @respx.mock
    async def test_http_error_raises(self):
        respx.post("http://localhost:8001").mock(
            return_value=Response(500, text="internal error")
        )
        client = A2AClient("http://localhost:8001")
        with pytest.raises(httpx.HTTPStatusError):
            await client.send_message("hi")
        await client.close()


class TestA2AResponse:
    def test_from_result_text_from_artifacts(self):
        result = {
            "id": "task-1",
            "contextId": "ctx-1",
            "artifacts": [{"parts": [{"text": "hello"}]}],
        }
        resp = A2AResponse.from_result(result)
        assert resp.text == "hello"
        assert resp.context_id == "ctx-1"
        assert resp.task_id == "task-1"

    def test_from_result_text_from_status_message(self):
        result = {
            "id": "t1",
            "status": {"message": {"parts": [{"text": "fallback"}]}},
        }
        resp = A2AResponse.from_result(result)
        assert resp.text == "fallback"

    def test_from_result_no_text(self):
        resp = A2AResponse.from_result({})
        assert resp.text == "(no response)"

    def test_from_result_file_attachments_extracted(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {"text": "here"},
                        {"url": "https://x.com/f.png", "mediaType": "image/png"},
                    ]
                }
            ]
        }
        resp = A2AResponse.from_result(result)
        assert len(resp.attachments) == 1
        assert resp.attachments[0].url == "https://x.com/f.png"
