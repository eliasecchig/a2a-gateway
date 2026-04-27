"""Deterministic A2A echo server for live tests. No LLM, no Google creds."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request

app = FastAPI()


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

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "parts": [
                        {"kind": "text", "text": f"ECHO: {user_text}"},
                    ]
                }
            ],
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
