"""Live e2e: gateway A2AClient (v1.0 wire) <-> samples/adk/ (a2a-sdk 0.3 + compat).

Spawns the ADK sample in its own uv venv, waits for the agent-card endpoint,
then exercises the gateway's outbound A2A client against it. Verifies the
v1.0-to-v0.3-compat path works end-to-end.

Skipped by default (live marker). Requires Gemini credentials configured for
the ADK Agent (GOOGLE_API_KEY or GOOGLE_GENAI_USE_VERTEXAI=TRUE plus
GOOGLE_CLOUD_PROJECT/GOOGLE_CLOUD_LOCATION).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from gateway.core.a2a_client import A2AClient

logger = logging.getLogger(__name__)

ADK_SAMPLE_PORT = 8002
ADK_SAMPLE_BASE = f"http://127.0.0.1:{ADK_SAMPLE_PORT}"
ADK_SAMPLE_AGENT_CARD = f"{ADK_SAMPLE_BASE}/.well-known/agent-card.json"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADK_SAMPLE_DIR = PROJECT_ROOT / "samples" / "adk"


def _has_gemini_creds() -> bool:
    if os.environ.get("GOOGLE_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return bool(
            os.environ.get("GOOGLE_CLOUD_PROJECT")
            and os.environ.get("GOOGLE_CLOUD_LOCATION")
        )
    return False


def _log_output(pipe, log_func) -> None:
    for line in iter(pipe.readline, ""):
        log_func(line.rstrip())


def _wait_for_server(url: str, timeout: float = 90, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def adk_sample() -> Iterator[str]:
    if not _has_gemini_creds():
        pytest.skip(
            "Missing Gemini credentials: set GOOGLE_API_KEY, or set "
            "GOOGLE_GENAI_USE_VERTEXAI=TRUE plus GOOGLE_CLOUD_PROJECT and "
            "GOOGLE_CLOUD_LOCATION."
        )

    proc = subprocess.Popen(
        ["uv", "run", "--project", str(ADK_SAMPLE_DIR), "python", "adk_dummy.py"],
        cwd=str(ADK_SAMPLE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )

    threading.Thread(
        target=_log_output, args=(proc.stdout, logger.info), daemon=True
    ).start()
    threading.Thread(
        target=_log_output, args=(proc.stderr, logger.error), daemon=True
    ).start()

    if not _wait_for_server(ADK_SAMPLE_AGENT_CARD):
        proc.terminate()
        proc.wait(timeout=5)
        pytest.fail(
            f"ADK sample did not start within 90s - is `uv sync` complete in "
            f"{ADK_SAMPLE_DIR}? Did Gemini credentials reach the subprocess?"
        )

    yield ADK_SAMPLE_BASE

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.mark.live
@pytest.mark.asyncio
async def test_agent_card_served(adk_sample: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{adk_sample}/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.json()
    assert card["name"] == "adk_dummy_agent"


@pytest.mark.live
@pytest.mark.asyncio
async def test_gateway_v1_client_against_adk_v03_compat(adk_sample: str) -> None:
    """Gateway A2AClient (v1.0 wire) -> ADK sample (a2a-sdk 0.3 + compat).

    Verifies the round-trip: v1.0 SendMessage method, A2A-Version: 1.0
    header, and v1.0 Part shape are accepted by the ADK server's compat
    layer; the response wire shape is parsed correctly by our client.
    """
    client = A2AClient(adk_sample)
    try:
        resp = await client.send_message(
            "Hello, please reply with a short greeting and echo back what I said."
        )
    finally:
        await client.close()

    assert resp.text, f"empty reply: {resp!r}"
    assert resp.context_id, "missing context_id in reply"
    assert resp.task_id, "missing task_id in reply"
