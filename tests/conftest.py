from __future__ import annotations

import pytest

from gateway.core.types import InboundMessage


@pytest.fixture
def sample_inbound() -> InboundMessage:
    return InboundMessage(
        channel="test",
        sender_id="user-1",
        sender_name="Alice",
        text="Hello agent",
        thread_id="t-1",
        conversation_id="conv-1",
    )


@pytest.fixture
def sample_inbound_factory():
    def _make(**overrides) -> InboundMessage:
        defaults = {
            "channel": "test",
            "sender_id": "user-1",
            "sender_name": "Alice",
            "text": "Hello agent",
            "thread_id": "t-1",
            "conversation_id": "conv-1",
        }
        defaults.update(overrides)
        return InboundMessage(**defaults)

    return _make
