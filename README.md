# a2a-gateway

[![CI](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml/badge.svg)](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

A gateway that connects any [A2A protocol](https://google.github.io/A2A/) agent to Slack, WhatsApp, Google Chat, Email, Telegram, and Discord. You build the agent, the gateway handles the channels.

```
    Slack ──┐                        ┌── Your A2A Agent
 WhatsApp ──┤                        │   (ADK, LangGraph,
   G Chat ──┼──▶  a2a-gateway  ──A2A─┤    CrewAI, custom…)
    Email ──┤                        │
 Telegram ──┤                        │
  Discord ──┘                        └──
```

Adding a channel is mostly just setting env vars. The gateway takes care of message chunking, rate limiting, retries, debouncing, typing indicators, streaming responses, and per-channel markdown formatting. Everything is opt-in: if you don't configure a feature, it doesn't run.

## Quick start

> **Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/eliasecchig/a2a-gateway.git
cd a2a-gateway
uv sync
```

Telegram and Discord are optional extras (they pull in `python-telegram-bot` and `discord.py`):

```bash
uv sync --extra telegram
uv sync --extra discord
```

The simplest way to run is with env vars, no config file needed:

```bash
export A2A_SERVER_URL=http://localhost:8001
export SLACK_BOT_TOKEN=xoxb-your-token
export SLACK_APP_TOKEN=xapp-your-token
uv run a2a-gateway
```

Or with a config file:

```bash
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

### Optional features

All features below are opt-in. Add the relevant section to `config.yaml` to enable them.

<details>
<summary><b>Chunking</b></summary>

Splits long responses at paragraph boundaries. Respects per-channel limits (Slack: 4000, WhatsApp: 4096, Telegram: 4096, Discord: 2000) and keeps code fences intact.

```yaml
chunking:
  mode: "newline"       # or "length" for hard splits
  default_limit: 4000
```
</details>

<details>
<summary><b>Debouncing</b></summary>

Buffers rapid messages into a single A2A call.

```yaml
debounce:
  window_ms: 500
  max_messages: 10
  max_chars: 4000
```
</details>

<details>
<summary><b>Rate limiting</b></summary>

Separate limits for the A2A side and the channel side, with per-channel overrides.

```yaml
rate_limiting:
  a2a:
    max_requests: 60
    window_seconds: 60
  channel:
    max_requests: 30
    window_seconds: 60
  channel_overrides:
    slack: { max_requests: 50 }
    whatsapp: { max_requests: 20 }
  backoff:
    initial: 1.0
    factor: 2.0
    max_delay: 300
    max_retries: 5
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
<summary><b>Feature flags</b></summary>

Toggle pipeline features per account.

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
<summary><b>Streaming</b></summary>

If the A2A agent supports SSE streaming (`message/stream`) and the channel supports message editing, the gateway edits the sent message in-place as tokens arrive. Falls back to regular request/response otherwise.

```yaml
streaming:
  enabled: true
  update_interval_ms: 500
```
</details>

<details>
<summary><b>Session management</b></summary>

```yaml
session:
  idle_timeout_minutes: 30
```
</details>

<details>
<summary><b>Concurrency limits</b></summary>

Caps in-flight A2A calls per conversation, user, or globally.

```yaml
concurrency:
  max_concurrent: 5
  per: "conversation"   # or "user", "global"
```
</details>

<details>
<summary><b>Structured logging</b></summary>

```yaml
logging:
  level: "INFO"
  format: "json"        # or "text"
  subsystem_levels:
    gateway.core.router: "DEBUG"
```
</details>

<details>
<summary><b>Health endpoints</b></summary>

Three endpoints for k8s probes and monitoring:

- `GET /live` — always 200
- `GET /ready` — 200 if at least one adapter is healthy, 503 otherwise
- `GET /health` — per-adapter status + agent capabilities

```yaml
health:
  stale_timeout_seconds: 300
```
</details>

<details>
<summary><b>Interactive elements</b></summary>

Buttons, dropdown selects, and cards. Slack gets native Block Kit rendering; other channels get a text fallback. Interaction callbacks (button clicks, select choices) are routed back to the A2A agent as new messages.
</details>

<details>
<summary><b>Capability discovery</b></summary>

On startup the gateway fetches `/.well-known/agent.json` from the A2A server. If the agent advertises streaming support and the channel supports editing, streaming kicks in automatically. No config needed.
</details>

## Docker

```bash
docker build -t a2a-gateway .

docker run -p 8000:8000 \
  -e A2A_SERVER_URL=http://your-agent:8001 \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_APP_TOKEN=xapp-your-token \
  a2a-gateway
```

Or mount a config file: `-v $(pwd)/config.yaml:/app/config.yaml`.

## Testing

```bash
uv run pytest tests/ -v                  # 282 tests, all offline
uv run pytest -m live tests/live/ -v     # live integration tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright 2026 Google LLC. Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
