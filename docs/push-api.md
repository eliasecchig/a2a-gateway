# Push API

`POST /push` sends a message through any registered channel without an inbound trigger — useful for scheduled nudges, alerts, or agent-initiated outreach.

## Request

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
| `channel` | yes | Adapter name: `slack`, `whatsapp`, `telegram`, etc. For multi-account setups, use `channel:account_id` (e.g. `slack:workspace_a`) |
| `recipient_id` | yes | Platform user/chat ID (Slack: `U12345`, WhatsApp: phone number, Telegram: chat ID) |
| `text` | yes | Message body |
| `thread_id` | no | Reply in a specific thread |
| `conversation_id` | no | Channel/group/space ID for context (Slack: `C12345`, Telegram: group chat ID) |

## Responses

| Status | Meaning |
|--------|---------|
| `200` | `{"status": "sent", "message_id": "..."}` — delivered to the channel adapter |
| `404` | Channel not found (response includes `available` channels list) |
| `422` | Missing or invalid fields |
| `502` | Adapter failed to send |

The message bypasses the A2A agent and goes directly to the channel adapter. Channel-side [rate limiting](configuration.md#default-features) applies. To discover available channel names, check `GET /health` → `channels`.

> **Authentication:** The push endpoint has no built-in authentication. In production, protect it with a reverse proxy, network policy, or API gateway.

## Python example

```python
import httpx

async def send_nudge():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://your-gateway/push",
            json={
                "channel": "slack",
                "recipient_id": "U12345ABC",
                "text": "Weekly reminder: review your open PRs!",
            },
        )
        resp.raise_for_status()
        return resp.json()
```

## See also

- [Configuration](configuration.md) — rate limiting, channel setup
- [Custom channels](custom-channels.md) — build adapters for unsupported platforms
