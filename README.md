# a2a-gateway

[![CI](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml/badge.svg)](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

A gateway that connects any [A2A protocol](https://google.github.io/A2A/) agent to Slack, WhatsApp, Google Chat, Email, Telegram, Discord, and your own custom channels. You build the agent, the gateway handles the channels.

```
    Slack ──┐                        ┌─────────────────────┐
 WhatsApp ──┤                        │   Your A2A Agent    │
   G Chat ──┤                        │   (ADK, LangGraph,  │
    Email ──┼──▶  a2a-gateway  ──A2A─┤    CrewAI, custom…) │
 Telegram ──┤                        └─────────────────────┘
  Discord ──┤
   Custom ──┘
```

Adding a built-in channel is mostly just setting env vars. Need a platform we don't support? Subclass `SimpleChannel`, implement one method, and you're in. The gateway takes care of message chunking, rate limiting, retries, debouncing, typing indicators, streaming responses, and per-channel markdown formatting. Everything is opt-in: if you don't configure a feature, it doesn't run.

## Quick start

> **Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/eliasecchig/a2a-gateway.git
cd a2a-gateway
uv sync
```

The simplest way to run is with env vars, no config file needed:

```bash
export A2A_SERVER_URL=http://localhost:8001
export SLACK_BOT_TOKEN=xoxb-your-token
export SLACK_APP_TOKEN=xapp-your-token
uv run a2a-gateway
```

Or with a config file (copy from `config.example.yaml`):

```bash
cp config.example.yaml config.yaml
uv run a2a-gateway --config config.yaml
```

Or with the built-in test agent (uses Gemini, needs Google Cloud credentials):

```bash
uv run a2a-gateway --with-agent
```

The gateway starts on `http://localhost:8000`.

## Supported channels

| Channel | Transport | Public URL needed? | Editing | Typing |
|---------|-----------|-------------------|---------|--------|
| Slack | Socket Mode | No | Yes | - |
| WhatsApp | Meta Cloud API webhook | Yes | No | - |
| Google Chat | Webhook + REST API | Yes | Yes | - |
| Email | SMTP (aiosmtpd) | No | No | - |
| Telegram | Bot API (polling) | No | Yes | Yes |
| Discord | Gateway (websocket) | No | Yes | Yes |

All channels use official APIs.

## Custom channels

Need a platform we don't cover? Subclass `SimpleChannel`, implement `send()`, and feed inbound messages to `dispatch()`. Your channel gets the full pipeline — rate limiting, chunking, debounce, streaming, typing indicators — for free.

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

### Registration

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

### Inbound messages

To receive messages, start a listener in `start()` and call `self.dispatch()`:

```python
async def start(self) -> None:
    self._task = asyncio.create_task(self._poll())

async def _poll(self) -> None:
    async for event in self.client.stream():
        await self.dispatch(InboundMessage(
            channel="rocketchat",
            conversation_id=event.room_id,
            sender_id=event.user_id,
            text=event.text,
        ))
```

For webhook-based channels, add a `self.router = APIRouter(...)` — the gateway includes it automatically.

## Pipeline

Every inbound message goes through this pipeline. Each step is optional and controlled by config.

```
Inbound message
  │
  ├─ ACK reaction (emoji / read receipt)
  ├─ Debounce (coalesce rapid messages)
  ├─ Group policy check (open / mention-only / disabled)
  ├─ Rate limit (A2A side)
  ├─ Concurrency limit
  ├─ Typing indicator
  │
  ├─ ──▶  A2A agent  ──▶  response (or SSE stream)
  │
  ├─ Markdown adaptation
  ├─ Chunking (split long responses, preserve code fences)
  ├─ Rate limit (channel side)
  │
  └─ Send reply (or stream edits in real time)
```

## Configuration

### Environment variables

Set a channel's token and the gateway enables it. This is the recommended approach for Docker/CI.

**Gateway:**

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_SERVER_URL` | `http://localhost:8001` | Your A2A agent URL |
| `GATEWAY_HOST` | `0.0.0.0` | Bind address |
| `GATEWAY_PORT` | `8000` | Listen port |
| `A2A_AUTH` | - | Auth mode: `google_id_token`, `google_access_token`, or `token` |
| `A2A_AUTH_TOKEN` | - | Static bearer token (when `A2A_AUTH=token`) |

**Slack:**

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot token (enables Slack) |
| `SLACK_APP_TOKEN` | App-level token for Socket Mode |

**WhatsApp:**

| Variable | Description |
|----------|-------------|
| `WHATSAPP_ACCESS_TOKEN` | Access token (enables WhatsApp) |
| `WHATSAPP_PHONE_NUMBER_ID` | Phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token |
| `WHATSAPP_APP_SECRET` | App secret for signature verification (optional) |

**Google Chat:**

| Variable | Description |
|----------|-------------|
| `GOOGLE_CHAT_SERVICE_ACCOUNT_PATH` | Path to service account JSON (enables Google Chat) |

**Email:**

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_SMTP_HOST` | - | SMTP host (enables Email) |
| `EMAIL_SMTP_PORT` | `587` | SMTP port |
| `EMAIL_FROM_ADDRESS` | `agent@example.com` | Sender address |

**Telegram:**

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather (enables Telegram) |

**Discord:**

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Bot token (enables Discord) |

### Config file

For multi-account setups or fine-grained feature control, use `config.yaml`:

```yaml
a2a:
  server_url: "http://localhost:8001"

channels:
  slack:
    enabled: true
    bot_token: "xoxb-your-bot-token"
    app_token: "xapp-your-app-token"
    features:
      typing: true
      ack: true
```

You can run multiple accounts per channel:

```yaml
channels:
  slack:
    - account_id: "workspace_a"
      enabled: true
      bot_token: "xoxb-aaa"
      app_token: "xapp-aaa"
    - account_id: "workspace_b"
      enabled: true
      bot_token: "xoxb-bbb"
      app_token: "xapp-bbb"
```

YAML takes priority over env vars. You can mix both.

### A2A authentication

If your agent runs behind an auth proxy (e.g. Cloud Run), the gateway can attach credentials to every outbound request.

**Google Cloud ID token** — for Cloud Run service-to-service. Uses Application Default Credentials to mint an ID token with the agent URL as audience:

```yaml
a2a:
  server_url: "https://my-agent-xyz.run.app"
  auth:
    type: "google_id_token"
```

**Google Cloud access token** — for Google APIs or services that accept OAuth2 access tokens:

```yaml
a2a:
  server_url: "https://my-agent-xyz.run.app"
  auth:
    type: "google_access_token"
```

**Static bearer token** — for agents behind a shared secret:

```yaml
a2a:
  server_url: "https://my-agent.example.com"
  auth:
    type: "token"
    token: "my-secret"
```

Or via env vars: `A2A_AUTH=token A2A_AUTH_TOKEN=my-secret`.

### What's on by default

These features run out of the box with sensible defaults. No config needed, but you can override or disable any of them in `config.yaml`.

| Feature | Default | What it does |
|---------|---------|-------------|
| **Chunking** | newline mode, 4000 char limit | Splits long responses at paragraph boundaries, per-channel limits |
| **Debouncing** | 500ms window, 10 messages | Coalesces rapid messages into a single A2A call |
| **Rate limiting** | 60 req/min (A2A), 30 req/min (channel) | Protects both sides with exponential backoff retries |
| **Streaming** | enabled, 500ms update interval | Edits messages in-place as tokens arrive (if agent supports it) |
| **Health endpoints** | 5 min stale timeout | `/live`, `/ready`, `/health` for k8s probes |
| **Outbound push** | always on | `POST /push` sends messages through any channel without an inbound trigger |
| **Session management** | 30 min idle timeout | Tracks conversation context, cleans up idle sessions |
| **Concurrency limits** | 5 per conversation | Prevents a single conversation from overloading the agent |
| **Capability discovery** | always on | Fetches `/.well-known/agent.json` on startup, adapts automatically |
| **Interactive elements** | always on | Buttons, selects, cards with per-channel rendering (Block Kit on Slack, text fallback elsewhere) |

Every default-on feature accepts `enabled: false` to turn it off entirely:

```yaml
debounce:
  enabled: false

streaming:
  enabled: false
```

<details>
<summary>Override the defaults</summary>

```yaml
chunking:
  enabled: true
  mode: "length"          # "newline" (default) or "length"
  default_limit: 2000

debounce:
  enabled: true
  window_ms: 300
  max_messages: 5
  max_chars: 2000

rate_limiting:
  enabled: true
  a2a:
    max_requests: 120
    window_seconds: 60
  channel:
    max_requests: 50
    window_seconds: 60
  channel_overrides:
    whatsapp: { max_requests: 20 }
  backoff:
    initial: 1.0
    factor: 2.0
    max_delay: 300
    max_retries: 5

streaming:
  enabled: true
  update_interval_ms: 300

health:
  enabled: true
  stale_timeout_seconds: 600

session:
  enabled: true
  idle_timeout_minutes: 60

concurrency:
  enabled: true
  max_concurrent: 10
  per: "user"             # "conversation" (default), "user", or "global"
```
</details>

### Opt-in features

These are off by default. Add the relevant section to `config.yaml` to turn them on.

<details>
<summary><b>Typing indicators</b></summary>

Shows a typing signal while the A2A agent is working. Auto-cancels after TTL. Native on Telegram and Discord.

```yaml
typing:
  enabled: true
  ttl_seconds: 30
```
</details>

<details>
<summary><b>ACK reactions</b></summary>

Fires an immediate acknowledgment when a message arrives, before any processing: emoji reaction on Slack, read receipt on WhatsApp, reaction on Google Chat.

```yaml
ack:
  slack:
    emoji: "eyes"
  whatsapp:
    read_receipts: true
  google_chat:
    emoji: "👀"
```
</details>

<details>
<summary><b>Group policies</b></summary>

Controls whether the bot responds in group chats: `open`, `mention_only`, or `disabled`.

```yaml
group_policies:
  slack:
    mode: "mention_only"
    overrides:
      "C12345": "open"
  telegram:
    mode: "mention_only"
  discord:
    mode: "mention_only"
```
</details>

<details>
<summary><b>Structured logging</b></summary>

Switches log output to JSON and allows per-subsystem level overrides.

```yaml
logging:
  level: "INFO"
  format: "json"
  subsystem_levels:
    gateway.core.router: "DEBUG"
```
</details>

<details>
<summary><b>Feature flags</b></summary>

Toggle pipeline features per account. Useful for disabling typing or ACK on specific accounts.

```yaml
channels:
  slack:
    enabled: true
    bot_token: "xoxb-..."
    app_token: "xapp-..."
    features:
      typing: true
      ack: false
```
</details>

## Outbound push

`POST /push` sends a message through any registered channel without an inbound trigger — useful for scheduled nudges, alerts, or agent-initiated outreach.

```bash
curl -X POST https://your-gateway/push \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "slack",
    "recipient_id": "U12345ABC",
    "text": "Weekly reminder: review your open PRs!",
    "thread_id": "1234567890.123456",
    "conversation_id": "C12345ABC"
  }'
```

| Field | Required | Description |
|-------|----------|-------------|
| `channel` | yes | Adapter name (e.g. `slack`, `whatsapp`, `telegram:prod`) |
| `recipient_id` | yes | Platform-specific user/chat ID |
| `text` | yes | Message body |
| `thread_id` | no | Reply in a specific thread |
| `conversation_id` | no | Channel/space/chat context |

Returns `{"status": "sent", "message_id": "..."}` on success. The message bypasses the A2A agent and goes directly to the channel adapter.

## Docker

A prebuilt image is published to GitHub Container Registry on every push to `main`:

```bash
docker run -p 8000:8000 \
  -e A2A_SERVER_URL=http://your-agent:8001 \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_APP_TOKEN=xapp-your-token \
  ghcr.io/eliasecchig/a2a-gateway:main
```

Or build it yourself:

```bash
docker build -t a2a-gateway .
docker run -p 8000:8000 \
  -e A2A_SERVER_URL=http://your-agent:8001 \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_APP_TOKEN=xapp-your-token \
  a2a-gateway
```

Mount a config file: `-v $(pwd)/config.yaml:/app/config.yaml`.

## Testing

```bash
uv run pytest tests/ -v                  # 354 tests, all offline
uv run pytest -m live tests/live/ -v     # live integration tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright 2026 Google LLC. Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
