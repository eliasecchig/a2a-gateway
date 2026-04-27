from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ECHO_AGENT_PORT = 8001
ECHO_AGENT_URL = f"http://127.0.0.1:{ECHO_AGENT_PORT}"


def require_env(*vars: str) -> dict[str, str]:
    missing = [v for v in vars if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)}")
    return {v: os.environ[v] for v in vars}


@pytest.fixture(scope="session")
def echo_agent():
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.live.echo_agent:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(ECHO_AGENT_PORT),
        ],
        cwd=str(Path(__file__).parents[2]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for _ in range(30):
        try:
            r = httpx.get(f"{ECHO_AGENT_URL}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("Echo agent failed to start")

    yield ECHO_AGENT_URL

    proc.terminate()
    proc.wait(timeout=5)
