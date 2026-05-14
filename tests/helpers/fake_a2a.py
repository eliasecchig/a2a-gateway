from __future__ import annotations

import respx
from httpx import Response


def mock_a2a_success(
    base_url: str = "http://localhost:8001",
    text: str = "Hello from agent",
    context_id: str = "ctx-1",
    task_id: str = "task-1",
    file_parts: list[dict] | None = None,
) -> respx.Route:
    parts = [{"text": text}]
    if file_parts:
        parts.extend(file_parts)

    task = {
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "TASK_STATE_COMPLETED"},
        "artifacts": [{"parts": parts}],
    }

    return respx.post(base_url).mock(
        return_value=Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {"task": task}},
        )
    )


def mock_a2a_error(
    base_url: str = "http://localhost:8001",
    code: int = -32000,
    message: str = "internal error",
) -> respx.Route:
    return respx.post(base_url).mock(
        return_value=Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": code, "message": message},
            },
        )
    )


def mock_a2a_http_error(
    base_url: str = "http://localhost:8001",
    status_code: int = 500,
) -> respx.Route:
    return respx.post(base_url).mock(
        return_value=Response(status_code, text="server error")
    )
