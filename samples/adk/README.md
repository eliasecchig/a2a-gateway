# ADK dummy agent (a2a-sdk 0.3)

Standalone uv project. Used to verify the gateway can talk to v0.3 A2A servers in the wild.

This lives in its own uv project (separate from the main gateway venv) because `google-adk` pins `a2a-sdk<0.4`, which conflicts with the gateway's `a2a-sdk>=1.0`. There is no way to coexist them in one Python environment until ADK ships v1.0 support.

## Run

From `samples/adk/`:

```bash
uv sync
uv run python adk_dummy.py
```

The agent listens on port 8002. Requires Google credentials configured for Gemini (see [google-adk docs](https://google.github.io/adk-docs/)).

## Test from the gateway

In the gateway venv (the parent project), point the gateway at `http://localhost:8002` via `A2A_SERVER_URL` and exchange messages as usual. The gateway speaks v1.0 wire format; ADK exposes both v0.3 and v1.0 method names via `enable_v0_3_compat=True`, so the handshake succeeds.
