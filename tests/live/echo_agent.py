"""Deterministic A2A echo server for live tests. No LLM, no Google creds.

Commands:
  (default)  → "ECHO: <user_text>"
  /file ...  → echo + 1x1 PNG attachment
  /long      → ~5000 char multi-paragraph response (triggers chunking)
  /markdown  → rich markdown (bold, code block, links, list, heading)
  /unicode   → emoji, accented chars, CJK, RTL Arabic
  /multi     → two separate artifacts
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

_LONG_PARAGRAPH = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum."
)

_LONG_TEXT = "\n\n".join([f"Section {i + 1}\n\n{_LONG_PARAGRAPH}" for i in range(12)])

_MARKDOWN_TEXT = """\
# Test Heading

This is **bold text** and this is __underlined__. Here's ~~strikethrough~~.

## Code Example

```python
def hello():
    return "world"
```

## Links and Lists

Check out [Example](https://example.com) for more info.

- First item
- Second item
- Third item

---

Final paragraph with `inline code` and more **bold**."""

_UNICODE_TEXT = (
    "Emoji: \U0001f680\U0001f30d\U0001f4a1✨\U0001f916 "
    "Accented: café naïve résumé "
    "CJK: 你好世界 "
    "Arabic (RTL): مرحبا "
    "Math: ∀x ∈ ℝ, x² ≥ 0"
)


def _build_response(
    request_id: int,
    context_id: str,
    parts: list[dict],
    *,
    extra_artifacts: list[dict] | None = None,
) -> dict:
    task_id = uuid.uuid4().hex
    artifacts = [{"parts": parts}]
    if extra_artifacts:
        artifacts.extend(extra_artifacts)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "completed"},
            "artifacts": artifacts,
        },
    }


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
    cmd = user_text.strip()

    if cmd.startswith("/long"):
        parts: list[dict] = [{"kind": "text", "text": _LONG_TEXT}]
        return _build_response(request_id, context_id, parts)

    if cmd.startswith("/markdown"):
        parts = [{"kind": "text", "text": _MARKDOWN_TEXT}]
        return _build_response(request_id, context_id, parts)

    if cmd.startswith("/unicode"):
        parts = [{"kind": "text", "text": f"ECHO: {_UNICODE_TEXT}"}]
        return _build_response(request_id, context_id, parts)

    if cmd.startswith("/multi"):
        parts = [{"kind": "text", "text": "ECHO-PART-1: first artifact"}]
        extra = [{"parts": [{"kind": "text", "text": "ECHO-PART-2: second artifact"}]}]
        return _build_response(request_id, context_id, parts, extra_artifacts=extra)

    parts = [{"kind": "text", "text": f"ECHO: {user_text}"}]

    if cmd.startswith("/file"):
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

    return _build_response(request_id, context_id, parts)


@app.get("/.well-known/agent.json")
async def agent_card() -> dict:
    return {
        "name": "Echo Agent",
        "description": "Deterministic echo agent for live tests",
        "capabilities": {},
        "skills": [
            {
                "name": "echo",
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
