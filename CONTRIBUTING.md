# Contributing to a2a-gateway

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Development setup

```bash
git clone https://github.com/eliasecchig/a2a-gateway.git
cd a2a-gateway
uv sync
```

## Running tests

```bash
# Full test suite (140 tests, all offline):
uv run pytest tests/ -v

# Live integration tests (email needs no credentials):
uv run pytest -m live tests/live/ -v

# Single test file:
uv run pytest tests/unit/test_chunking.py -v
```

## Code style

- Type hints on all function signatures
- No comments unless the *why* is non-obvious
- Follow existing patterns in the codebase

## Adding a new channel adapter

1. Create `gateway/channels/your_channel.py`
2. Implement the `ChannelAdapter` ABC from `gateway/core/channel.py`:

```python
from gateway.core.channel import ChannelAdapter
from gateway.core.types import OutboundMessage

class YourChannelAdapter(ChannelAdapter):
    @property
    def name(self) -> str: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, message: OutboundMessage) -> None: ...
```

3. Add a config dataclass to `gateway/config.py`
4. Wire it in `gateway/server.py`
5. Add contract tests in `tests/contracts/test_channel_contract.py`
6. Add the channel's markdown rules to `gateway/core/markdown.py` (or use `PassthroughMarkdown`)
7. Add the channel's message limit to `CHANNEL_LIMITS` in `gateway/core/chunking.py`

## Pull requests

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Make sure `uv run pytest tests/ -v` passes before opening
- Do not commit credentials or secrets

## License headers

All Python source files must include the Apache 2.0 header:

```python
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
```
