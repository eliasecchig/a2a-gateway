# Custom channels

Need a platform the gateway doesn't cover? Subclass `SimpleChannel`, implement `send()`, and feed inbound messages to `dispatch()`. Your channel gets the full pipeline — rate limiting, chunking, debounce, streaming, typing indicators — for free.

## Minimal example

```python
import httpx
from gateway.ext import SimpleChannel, InboundMessage, OutboundMessage

class RocketChatChannel(SimpleChannel):
    channel_type = "rocketchat"

    def __init__(self, base_url: str, token: str, **kwargs):
        super().__init__(**kwargs)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Auth-Token": token},
        )

    async def send(self, message: OutboundMessage) -> str | None:
        resp = await self._http.post("/api/v1/chat.sendMessage", json={
            "channel": message.conversation_id,
            "text": message.text,
        })
        return resp.json().get("message", {}).get("_id")
```

## Registration

**Programmatic** — pass instances directly when creating the app:

```python
from gateway.config import load_config
from gateway.server import create_app

config = load_config()
app = create_app(config, custom_channels=[
    RocketChatChannel(
        base_url="https://chat.example.com",
        token="my-token",
        account_id="prod",
    ),
])
```

**YAML** — declare the dotted class path in `config.yaml` and the gateway imports it at startup:

```yaml
custom_channels:
  - class_path: "my_package.RocketChatChannel"
    account_id: "prod"
    kwargs:
      base_url: "https://chat.example.com"
      token: "my-token"
    features:
      typing: true
```

`kwargs` are forwarded to `__init__`. Per-channel `features` toggle pipeline behavior individually.

## Inbound messages

**Polling / streaming channels** — start a background task in `start()`, track it, and cancel it in `stop()`:

```python
import asyncio
import contextlib
import logging

logger = logging.getLogger(__name__)

class RocketChatChannel(SimpleChannel):
    channel_type = "rocketchat"

    async def start(self) -> None:
        self._task = asyncio.create_task(
            self._poll(), name=f"rocketchat-poll-{self._account_id}"
        )
        self._task.add_done_callback(self._on_task_done)

    async def stop(self) -> None:
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _poll(self) -> None:
        async for event in self.client.stream():
            await self.dispatch(InboundMessage(
                channel="rocketchat",
                conversation_id=event.room_id,
                sender_id=event.user_id,
                text=event.text,
            ))

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        if exc := task.exception():
            logger.error("poll task failed: %s", exc)
```

**Webhook-based channels** — define a FastAPI router on your adapter. The gateway discovers and includes it automatically:

```python
from fastapi import APIRouter, Request

class MyWebhookChannel(SimpleChannel):
    channel_type = "my_webhook"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router = APIRouter(prefix="/my-webhook")

        @self.router.post("/events")
        async def handle_event(request: Request):
            data = await request.json()
            await self.dispatch(InboundMessage(
                channel=self.name,
                sender_id=data["user_id"],
                text=data["text"],
                conversation_id=data["room_id"],
            ))
            return {"ok": True}
```

## Interface reference

`SimpleChannel` extends `ChannelAdapter` with no-op `start()` and `stop()`. You must implement `send()`. Everything else is optional.

**Required:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `send` | `async def send(self, message: OutboundMessage) -> str \| None` | Send a message. Return the message ID or `None`. |

**Optional overrides:**

| Method / Property | Description |
|-------------------|-------------|
| `start()` | Initialize connections, start polling tasks |
| `stop()` | Graceful shutdown, cancel tasks |
| `edit_message(message_id, conversation_id, text, thread_id)` | Edit a previously sent message |
| `send_typing(conversation_id, thread_id)` | Send a typing indicator |
| `send_ack(message, config)` | Send an immediate acknowledgment (emoji, read receipt) |
| `supports_editing` (property) | Return `True` to enable streaming edit-in-place |

**Message types** (all importable from `gateway.ext`):

| Type | Key fields |
|------|-----------|
| `InboundMessage` | `channel`, `sender_id`, `sender_name`, `text`, `conversation_id`, `thread_id`, `is_group`, `is_mention`, `attachments` |
| `OutboundMessage` | `channel`, `recipient_id`, `text`, `conversation_id`, `thread_id`, `attachments`, `interactive` |
| `Attachment` | `url`, `data`, `mime_type`, `filename`, `size` |

## See also

- [Configuration](configuration.md) — per-channel feature flags, rate limit overrides
- [Push API](push-api.md) — send messages to your custom channel via the A2A endpoint at `POST /push`
