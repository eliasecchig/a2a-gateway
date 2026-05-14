# Push API (A2A JSON-RPC)

`POST /push` is an A2A JSON-RPC endpoint that delivers a message through any registered channel adapter — useful for scheduled nudges, alerts, or agent-initiated outreach.

The agent card describing the endpoint and its registered channels is served at `GET /push/.well-known/agent-card.json`.

## Request

```bash
curl -X POST https://your-gateway/push \
  -H 'Content-Type: application/json' \
  -H 'A2A-Version: 1.0' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "SendMessage",
    "params": {
      "message": {
        "role": "ROLE_USER",
        "messageId": "abc123",
        "parts": [{"text": "Weekly reminder: review your open PRs!"}],
        "metadata": {
          "gateway/channel": "slack",
          "gateway/recipient_id": "U12345ABC",
          "gateway/thread_id": "1234567890.123456",
          "gateway/conversation_id": "C12345ABC"
        }
      }
    }
  }'
```

| Metadata key | Required | Description |
|--------------|----------|-------------|
| `gateway/channel` | yes | Adapter name: `slack`, `whatsapp`, `telegram`, etc. For multi-account setups, use `channel:account_id` (e.g. `slack:workspace_a`) |
| `gateway/recipient_id` | yes | Platform user/chat ID (Slack: `U12345`, WhatsApp: phone number, Telegram: chat ID) |
| `gateway/thread_id` | no | Reply in a specific thread |
| `gateway/conversation_id` | no | Channel/group/space ID for context (Slack: `C12345`, Telegram: group chat ID) |

Message body comes from concatenated text parts of `params.message.parts`. The `A2A-Version: 1.0` request header is required.

## Responses

A2A endpoints always respond with HTTP `200` and use the JSON-RPC envelope to signal success or failure.

**Success:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "message": {
      "messageId": "...",
      "contextId": "...",
      "role": "ROLE_AGENT",
      "parts": [{"text": "delivered to slack"}],
      "metadata": {"gateway/message_id": "1234567890.123456"}
    }
  }
}
```

The reply's `metadata.gateway/message_id` carries the adapter's returned message ID if available; the `metadata` field is omitted when the adapter returns no ID.

**Failure:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "channel 'unknown' not registered (available: ['slack', 'telegram'])"
  }
}
```

Common causes: missing or invalid routing metadata, unknown channel, adapter send failed. The exact `code` follows JSON-RPC convention; assert on `error.message` substring rather than `code` for stable error handling.

The message bypasses the upstream A2A agent and goes directly to the channel adapter. Channel-side [rate limiting](configuration.md#default-features) applies.

> **Authentication:** The push endpoint has no built-in authentication. In production, protect it with a reverse proxy, network policy, or API gateway.

## Agent card

```bash
curl -s https://your-gateway/push/.well-known/agent-card.json
```

The card lists each registered channel as a skill (`send_slack`, `send_telegram`, etc.) so A2A-aware clients can discover what the gateway can deliver to.

## Python example (`a2a-sdk` client)

```python
from a2a.client import create_client
from a2a.types import Message, Part, Role


async def send_nudge():
    client = await create_client("https://your-gateway/push")
    message = Message(
        message_id="abc123",
        role=Role.ROLE_USER,
        parts=[Part(text="Weekly reminder: review your open PRs!")],
        metadata={
            "gateway/channel": "slack",
            "gateway/recipient_id": "U12345ABC",
        },
    )
    async for chunk in client.send_message(message):
        print(chunk)
```

## See also

- [Configuration](configuration.md) — rate limiting, channel setup
- [Custom channels](custom-channels.md) — build adapters for unsupported platforms
