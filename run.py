# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Entry point: starts the gateway (and optionally the dummy A2A agent)."""

import argparse
import logging
import multiprocessing

import uvicorn

from gateway.config import load_config
from gateway.core.logging import configure_logging
from gateway.server import create_app


def run_agent(port: int) -> None:
    from agent.dummy import app

    uvicorn.run(app, host="0.0.0.0", port=port)


def main() -> None:
    parser = argparse.ArgumentParser(description="a2a-gateway")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--with-agent",
        action="store_true",
        help="Also start the dummy ADK agent on port 8001",
    )
    parser.add_argument(
        "--agent-port", type=int, default=8001, help="Port for the dummy agent"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging)

    if args.with_agent:
        agent_proc = multiprocessing.Process(
            target=run_agent, args=(args.agent_port,), daemon=True
        )
        agent_proc.start()
        logging.info("dummy agent starting on port %d", args.agent_port)

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
