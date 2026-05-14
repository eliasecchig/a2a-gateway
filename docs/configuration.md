# Configuration

The gateway can be configured through environment variables, a YAML config file, or both. Set a channel's token and the gateway enables it automatically.

## Environment variables

This is the recommended approach for Docker and CI. Set only the variables you need — unused channels stay disabled.

**Gateway:**

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_SERVER_URL` | `http://localhost:8001` | Your A2A agent URL |
| `A2A_AGENT_CARD_PATH` | `/.well-known/agent-card.json` | Path to the agent card endpoint (A2A spec 1.0 default) |
| `GATEWAY_HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port (matches Cloud Run convention) |
| `A2A_AUTH` | - | Auth mode: `google_id_token`, `google_access_token`, or `token` |
| `A2A_AUTH_TOKEN` | - | Static bearer token (when `A2A_AUTH=token`) |
| `GATEWAY_PUBLIC_BASE_URL` | - | Public base URL the gateway is reachable at (e.g. `https://gw.example.com`). When set, the [push agent card](push-api.md) advertises absolute URLs in `supportedInterfaces`; otherwise relative URLs are used. |

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
| `EMAIL_SMTP_HOST` | - | Outbound SMTP host (enables Email) |
| `EMAIL_SMTP_PORT` | `587` | Outbound SMTP port |
| `EMAIL_SMTP_USER` | - | SMTP auth username (optional) |
| `EMAIL_SMTP_PASSWORD` | - | SMTP auth password (optional) |
| `EMAIL_FROM_ADDRESS` | `agent@example.com` | Sender address |
| `EMAIL_LISTEN_HOST` | `0.0.0.0` | Inbound SMTP listener host |
| `EMAIL_LISTEN_PORT` | `1025` | Inbound SMTP listener port |

**Telegram:**

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather (enables Telegram) |

**Discord:**

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Bot token (enables Discord) |

## Config file

For multi-account setups or fine-grained feature control, use `config.yaml`:

```yaml
a2a:
  server_url: "http://localhost:8001"
  # agent_card_path: "/.well-known/agent-card.json"  # default (A2A spec 1.0)

channels:
  slack:
    enabled: true
    bot_token: "xoxb-your-bot-token"
    app_token: "xapp-your-app-token"
    features:
      typing: true
      ack: true
```

Each channel supports a single-account format (dict) or multi-account format (list). The dict format implicitly uses `account_id: "default"`. You can run multiple accounts per channel:

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

Env vars only apply to channels not already configured in YAML. If a channel is defined in YAML, its env vars are ignored. You can mix both: use YAML for channels that need multi-account or fine-grained config, and env vars for the rest.

## A2A authentication

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

## Default features

These features run out of the box with sensible defaults. No config needed, but you can override or disable any of them.

| Feature | Default | What it does |
|---------|---------|-------------|
| **Chunking** | newline mode, 4000 char limit | Splits long responses at paragraph boundaries, per-channel limits |
| **Debouncing** | 500ms window, 10 messages | Coalesces rapid messages into a single A2A call |
| **Rate limiting** | 60 req/min (A2A), 30 req/min (channel) | Protects both sides with exponential backoff retries |
| **Streaming** | enabled, 500ms update interval | Edits messages in-place as tokens arrive (if agent supports it) |
| **Health endpoints** | 5 min stale timeout | `/live`, `/ready`, `/health` for k8s probes |
| **Outbound push** | always on | [`POST /push`](push-api.md) — A2A JSON-RPC endpoint that delivers messages through any channel without an inbound trigger |
| **Session management** | 30 min idle timeout | Tracks conversation context, cleans up idle sessions |
| **Concurrency limits** | 5 per conversation | Prevents a single conversation from overloading the agent |
| **Capability discovery** | always on | Fetches the agent card on startup, adapts automatically |
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

## Opt-in features

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

## See also

- [Custom channels](custom-channels.md) — build your own channel adapter
- [Push API](push-api.md) — send messages without an inbound trigger
