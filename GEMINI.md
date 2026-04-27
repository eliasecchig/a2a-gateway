# GEMINI.md — A2A Gateway Agent Guidelines

## Project Overview

A multi-channel gateway that bridges messaging platforms (Slack, WhatsApp, Google Chat, Discord, Telegram, Email) to any A2A-compliant agent via the Agent-to-Agent (A2A) protocol (JSON-RPC 2.0 over HTTP + SSE).

- **Language:** Python 3.12+
- **Framework:** FastAPI with uvicorn
- **Async:** Full asyncio — no blocking calls on the event loop

## Commands

```bash
uv sync                                    # Install dependencies
uv run python run.py                       # Start the gateway
uv run pytest                              # Run tests (skips live tests)
uv run pytest -m live                      # Run live integration tests
uv run ruff check gateway/ tests/ run.py   # Lint
uv run ruff format gateway/ tests/ run.py  # Format
```

## Project Structure

```
gateway/
  channels/          # Channel adapters (one file per platform)
    slack.py, whatsapp.py, google_chat.py, discord.py, telegram.py, email.py
  core/              # Shared infrastructure
    channel.py       # ChannelAdapter base class
    types.py         # InboundMessage, OutboundMessage, Attachment dataclasses
    router.py        # Message pipeline (dispatch → A2A → response)
    a2a_client.py    # HTTP + SSE client for A2A protocol
    rate_limit.py    # RateLimiter + RetryWithBackoff
    concurrency.py   # Per-conversation/user/global semaphore limiter
    debounce.py      # Message coalescing within time window
    chunking.py      # Split long responses for channel limits
    session.py       # Session state with TTL-based sweep
    health.py        # Health monitoring and readiness
    typing_indicator.py
    capabilities.py  # A2A agent card discovery
    policies.py      # Group chat policy enforcement
    markdown.py      # Markdown adaptation per channel
    media.py         # Attachment handling
    logging.py       # Structured logging setup
    interactive.py, interactive_callbacks.py  # Buttons, cards, selects
    ack.py           # Acknowledgment (reactions, read receipts)
  config.py          # Dataclass-based configuration (YAML + env vars)
  server.py          # FastAPI app factory, lifespan, endpoint wiring
tests/
  unit/              # Isolated component tests
  integration/       # Router pipeline + server endpoint tests
  contracts/         # Adapter interface contract tests
  live/              # Real service tests (require credentials)
  helpers/           # MockAdapter, fake A2A server
  conftest.py        # Shared fixtures
```

## Architecture

### Adapter Pattern

Every channel implements `ChannelAdapter` (`gateway/core/channel.py`):

```python
class MyAdapter(ChannelAdapter):
    channel_type = "my_channel"           # Required: sets the adapter name

    def __init__(self, ..., account_id: str = "default") -> None:
        super().__init__(account_id=account_id)  # Must call with account_id

    async def start(self) -> None: ...    # Connect / start polling
    async def stop(self) -> None: ...     # Graceful shutdown
    async def send(self, message: OutboundMessage) -> str | None: ...
```

Optional overrides: `edit_message()`, `send_typing()`, `send_ack()`, `supports_editing` property.

The base class provides `name` (returns `"my_channel"` or `"my_channel:account_id"`), `dispatch()` (forwards inbound messages to the router), and `on_message` callback slot.

### Router Pipeline

`Router` (`gateway/core/router.py`) wires everything together:

1. Adapter registers via `router.register(adapter)`
2. Router sets `adapter.on_message` to its pipeline (optionally wrapped with ack, debounce)
3. On inbound message: group policy check → session lookup → typing indicator → A2A call (streaming or non-streaming) → chunk response → rate-limited send

### Configuration

Dataclass-based config in `gateway/config.py`:

- `GatewayConfig` is the top-level container
- Feature configs: `ChunkingConfig`, `DebounceConfig`, `RateLimitingConfig`, `ConcurrencyConfig`, etc.
- Account configs: `SlackAccountConfig`, `WhatsAppAccountConfig`, etc.
- Loading: YAML file parsed first, then env var overrides applied via `_apply_env_overrides()`
- Unknown config keys produce a warning (not a crash)
- Helper `_build(cls, data)` filters dict keys to match dataclass fields

Env var convention: `SLACK_BOT_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `A2A_SERVER_URL`, `GATEWAY_PORT`.

## Code Style

### Essentials

- Every module starts with `from __future__ import annotations`
- Type hints on all function parameters and return types
- Union syntax: `str | None` (not `Optional[str]`)
- Line length: **90 characters** (configured in ruff)
- Imports: absolute only (`from gateway.core.types import InboundMessage`)
- Use `TYPE_CHECKING` guard for imports only needed by type checkers

### Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Classes | PascalCase | `ChannelAdapter`, `RateLimiter` |
| Functions / methods | snake_case | `send_message`, `_handle_inner` |
| Constants | UPPER_SNAKE | `RETRYABLE_EXCEPTIONS`, `GRAPH_API` |
| Private members | leading underscore | `_http`, `_lock`, `_sessions` |
| Files | snake_case, match content | `rate_limit.py`, `google_chat.py` |

### Comments and Docstrings

- Default to **no comments**. Only add one when the *why* is non-obvious.
- No multi-paragraph docstrings. One short sentence max.
- Key base classes get a brief docstring explaining the contract; methods don't.

### Ruff Rules

Configured in `pyproject.toml`. Key enabled rules: `E`, `F`, `W`, `I`, `C`, `B`, `UP`, `RUF`, `SIM`, `T20` (no `print()` in library code), `PLR0917` (max 5 positional params), `PLW1514` (require encoding in `open()`). Tests are exempt from `T20`.

## Async Patterns

### Task Lifecycle

Every background task must be:

1. **Named** — `asyncio.create_task(..., name="descriptive-name")`
2. **Tracked** — stored in an instance attribute (`self._task`)
3. **Monitored** — `task.add_done_callback(self._on_task_done)` to log failures
4. **Cancelled on shutdown** — `task.cancel()` in `stop()`

```python
# Correct pattern (see gateway/channels/slack.py)
self._start_task = asyncio.create_task(
    self._handler.start_async(), name=f"slack-socket-{self._account_id}"
)
self._start_task.add_done_callback(self._on_task_done)

def _on_task_done(self, task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("task failed: %s", exc)
```

### Lock Discipline

Never sleep while holding a lock. Release the lock first, then sleep:

```python
# Correct (see gateway/core/rate_limit.py)
while True:
    async with self._lock:
        if can_proceed:
            return
        wait = compute_wait()
    await asyncio.sleep(wait)  # Lock released before sleep
```

### Cancellation Cleanup

Use `contextlib.suppress` when awaiting a cancelled task:

```python
task.cancel()
with contextlib.suppress(asyncio.CancelledError):
    await task
```

### Blocking Calls

Never call blocking I/O on the event loop. Wrap with `asyncio.to_thread()`:

```python
# Correct (see gateway/channels/google_chat.py)
await asyncio.to_thread(self._creds.refresh, self._auth_request)
```

## Adding a New Channel Adapter

1. Create `gateway/channels/my_channel.py`
2. Subclass `ChannelAdapter`, set `channel_type = "my_channel"`
3. Call `super().__init__(account_id=account_id)` in `__init__`
4. Implement `start()`, `stop()`, `send()`
5. In your inbound handler, build an `InboundMessage` and call `await self.dispatch(msg)`
6. Add `MyChannelAccountConfig` dataclass in `config.py`
7. Add account list field to `GatewayConfig`
8. Wire up in `server.py` (adapter creation + registration)
9. Add contract test params in `tests/contracts/test_channel_contract.py`
10. Add unit tests in `tests/unit/test_my_channel.py`

For webhook-based channels (WhatsApp, Google Chat): create a `self.router = APIRouter(...)` and define routes. The server includes adapter routers automatically.

For socket/polling channels (Slack, Discord, Telegram): start a background task in `start()`, track it, add a done callback.

## Error Handling & Logging

### Log Levels

| Level | Use for | Examples |
|-------|---------|---------|
| DEBUG | Internal diagnostics, policy decisions | `"group policy: no mention in %s"` |
| INFO | Normal operations | `"adapter started"`, `"message dispatched"` |
| WARNING | Recoverable issues, retries | `"rate limit hit"`, `"edit failed"`, `"typing indicator failed"` |
| ERROR | Cannot proceed, needs attention | `"adapter connection failed"`, `"auth test failed"` |

- Expected user behavior (wrong password, invalid input) is **not** ERROR
- Transient failures (network timeout, rate limit) are WARNING
- Use `logger.warning("...", exc_info=True)` when the traceback adds diagnostic value

### Exception Handling

- Catch specific exceptions, not bare `Exception` (except in top-level adapter event handlers where you must not crash)
- For validation, raise `ValueError`/`RuntimeError` — never use `assert` for runtime validation
- Let exceptions propagate from `send()` so the router can handle retries

## Resilience Patterns

### Retry

`RetryWithBackoff` (`gateway/core/rate_limit.py`) retries only specific exception types:

```python
RETRYABLE_EXCEPTIONS = (OSError, ConnectionError, TimeoutError)
```

Exponential backoff with jitter (default ±10%). Per-channel overrides supported via config.

### Rate Limiting

`RateLimiter` — sliding window token bucket, per-key. Separate limits for A2A calls and per-channel sends.

### Concurrency Limiting

`ConcurrencyLimiter` (`gateway/core/concurrency.py`) — per-conversation (default), per-user, or global. Uses `asyncio.Semaphore` with LRU eviction capped at 10,000 entries to prevent unbounded memory growth.

### Debouncing

`Debouncer` (`gateway/core/debounce.py`) — coalesces rapid messages within a time window before forwarding to A2A. Flushes on window expiry, max message count, or max character count.

## Security

- **Webhook signature verification:** HMAC-SHA256 for WhatsApp (`hmac.compare_digest`), Bearer token for Google Chat
- **Constant-time comparison:** Always use `hmac.compare_digest()`, never `==` for tokens/signatures
- **Secrets in config:** Access tokens, app secrets, service account paths — never logged, never committed. Use env vars or YAML (gitignored)

## Testing

### Conventions

- **pytest** with `asyncio_mode = "auto"` — async test functions run automatically
- **`--strict-markers`** — undefined markers cause errors
- **`filterwarnings = ["error"]`** — warnings become test failures (with specific exemptions)
- Tests skip live tests by default (`-m 'not live'`)

### Test Organization

- Unit tests mirror source structure: `gateway/core/rate_limit.py` → `tests/unit/test_rate_limit.py`
- Contract tests (`tests/contracts/`) verify all adapters implement the `ChannelAdapter` interface via parametrized fixtures
- Integration tests (`tests/integration/`) use `httpx.AsyncClient` with `ASGITransport` to test FastAPI endpoints without a running server
- `MockAdapter` in `tests/helpers/mock_adapter.py` — uses `channel_type` base class pattern, accepts custom channel names

### Fixtures

Shared fixtures in `tests/conftest.py`:
- `sample_inbound` — a ready-made `InboundMessage`
- `sample_inbound_factory` — factory function with overrides

### Mocking

- **HTTP:** `respx` for mocking httpx calls
- **Slack:** `patch("gateway.channels.slack.AsyncApp")` to avoid real socket connections
- **Google Chat:** patch `service_account.Credentials.from_service_account_file`

## Anti-Patterns — Do Not

| Anti-pattern | Why | Correct approach |
|-------------|-----|-----------------|
| `asyncio.create_task(x)` without tracking | Task errors are silently swallowed | Store task, add done callback, cancel on shutdown |
| `await asyncio.sleep()` inside `async with lock` | Blocks all other lock waiters | Release lock before sleeping |
| Unbounded dicts/collections for per-key state | Memory grows forever | Cap size with LRU eviction |
| `except Exception` in retry logic | Retries programming errors (TypeError, ValueError) | Catch only `RETRYABLE_EXCEPTIONS` |
| `assert x is not None` for runtime checks | Stripped by `python -O`, no useful error | `if x is None: raise RuntimeError(...)` |
| `body = await request.json()` then re-reading body | Second read returns empty bytes | Read `request.body()` once, parse with `json.loads()` |
| Blocking calls on event loop (`time.sleep`, sync HTTP) | Stalls all concurrent tasks | Use `asyncio.to_thread()` or async libraries |
| `logger.debug()` for operational failures | Failures are invisible in production | Use `logger.warning()` for anything worth investigating |
| Mutable default arguments in dataclasses | Shared state between instances | Use `field(default_factory=list)` |
