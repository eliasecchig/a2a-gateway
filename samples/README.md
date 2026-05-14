# Samples

## Minimal echo agent — `dummy_agent.py`

Minimal A2A echo agent for testing the gateway locally. Run with `uv run python -m samples.dummy_agent`. Listens on port 8001.

## ADK-based v0.3 agent — `adk/`

Standalone uv project under `samples/adk/`. Uses ADK + Gemini to expose a real LLM-backed agent that speaks the a2a-sdk 0.3 wire format. Used to verify the gateway's backward compatibility with v0.3 servers.

Lives in its own uv project because ADK pins `a2a-sdk<0.4`, which conflicts with the gateway's `a2a-sdk>=1.0`. See `samples/adk/README.md` for run instructions.
