"""Deterministic A2A echo server for live tests. No LLM, no Google creds.

Responds with "ECHO: <user_text>".
If the text starts with "/file", also returns a small PNG file attachment.
"""

from __future__ import annotations

import base64
import uuid

from fastapi import FastAPI, Request

app = FastAPI()

_1X1_PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


@app.post("/")
async def handle_jsonrpc(request: Request) -> dict:
    body = await request.json()
    request_id = body.get("id", 1)
    params = body.get("params", {})
    message = params.get("message", {})

    user_text = ""
    for part in message.get("parts", []):
        if part.get("kind") == "text":
            user_text += part.get("text", "")

    context_id = message.get("contextId") or uuid.uuid4().hex
    task_id = uuid.uuid4().hex

    parts: list[dict] = [{"kind": "text", "text": f"ECHO: {user_text}"}]

    if user_text.strip().startswith("/file"):
        parts.append(
            {
                "kind": "file",
                "file": {
                    "name": "test.png",
                    "mimeType": "image/png",
                    "bytes": _1X1_PNG,
                },
            }
        )

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "completed"},
            "artifacts": [{"parts": parts}],
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
