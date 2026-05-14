# a2a-gateway

[![CI](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml/badge.svg)](https://github.com/eliasecchig/a2a-gateway/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

A gateway that connects any [A2A (Agent-to-Agent)](https://google.github.io/A2A/) protocol agent to Telegram, Slack, WhatsApp, Google Chat, Email, Discord, and your own custom channels. You build the agent, the gateway handles the channels.

```
 Telegram ──┐                        ┌─────────────────────┐
    Slack ──┤                        │   Your A2A Agent    │
 WhatsApp ──┤                        │   (ADK, LangGraph,  │
   G Chat ──┼──▶  a2a-gateway  ──A2A─┤    CrewAI, custom…) │
    Email ──┤  ◀──── /push (A2A) ────┤                     │
  Discord ──┤                        └─────────────────────┘
   Custom ──┘
```

Adding a built-in channel is mostly just setting env vars. Need a platform we don't support? Subclass `SimpleChannel`, implement one method, and you're in. The gateway takes care of message chunking, rate limiting, retries, debouncing, typing indicators, streaming responses, and per-channel markdown formatting. Everything is opt-in: if you don't configure a feature, it doesn't run.

## Quick start

### Docker (recommended)

```bash
docker run -p 8000:8000 \
  -e A2A_SERVER_URL=http://host.docker.internal:8001 \
  -e TELEGRAM_BOT_TOKEN=your-bot-token \
  ghcr.io/eliasecchig/a2a-gateway:main
```

Get a bot token from [@BotFather](https://t.me/BotFather) in under a minute.

### From source

> **Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/eliasecchig/a2a-gateway.git
cd a2a-gateway
uv sync
```

Run with env vars (no config file needed):

```bash
export A2A_SERVER_URL=http://localhost:8001
export TELEGRAM_BOT_TOKEN=your-bot-token
uv run a2a-gateway
```

Or with a config file:

```bash
cp config.example.yaml config.yaml
uv run a2a-gateway --config config.yaml
```

Or with the built-in test agent (a minimal A2A echo server — no LLM, no credentials needed):

```bash
uv run a2a-gateway --with-agent
```

The gateway starts on `http://localhost:8000`.

## Supported channels

| Channel | Transport | Public URL needed? | Editing | Typing |
|---------|-----------|-------------------|---------|--------|
| Telegram | Bot API (polling) | No | Yes | Native |
| Slack | Socket Mode | No | Yes | Opt-in |
| Discord | Gateway (websocket) | No | Yes | Native |
| WhatsApp | Meta Cloud API webhook | Yes | No | Opt-in |
| Google Chat | Webhook + REST API | Yes | Yes | Opt-in |
| Email | SMTP (aiosmtpd) | No | No | - |

All channels use official APIs.

## How it works

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

## Documentation

| Topic | Description |
|-------|-------------|
| [Configuration](docs/configuration.md) | Env vars, config file, A2A auth, default/opt-in features |
| [Custom channels](docs/custom-channels.md) | Build your own channel adapter with `SimpleChannel` |
| [Push API](docs/push-api.md) | Send messages to any channel via the A2A JSON-RPC endpoint at `POST /push` |

## Docker

A prebuilt image is published to GHCR on every push to `main` (see [Quick start](#quick-start) for usage). To build locally:

```bash
docker build -t a2a-gateway .
docker run -p 8000:8000 \
  -e A2A_SERVER_URL=http://your-agent:8001 \
  -e TELEGRAM_BOT_TOKEN=your-bot-token \
  a2a-gateway
```

Mount a config file: `-v $(pwd)/config.yaml:/app/config.yaml`.

## Testing

```bash
uv run pytest tests/ -v                  # all offline
uv run pytest -m live tests/live/ -v     # live integration tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright 2026 Google LLC. Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
