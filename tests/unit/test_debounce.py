from __future__ import annotations

import asyncio

import pytest

from gateway.core.debounce import DebounceConfig, Debouncer
from gateway.core.types import Attachment, InboundMessage


def _msg(
    text: str = "hello", channel: str = "test", sender: str = "u1", conv: str = "c1", **kw
) -> InboundMessage:
    return InboundMessage(
        channel=channel,
        sender_id=sender,
        sender_name=sender,
        text=text,
        conversation_id=conv,
        **kw,
    )


@pytest.mark.asyncio
class TestDebouncer:
    async def test_single_message_flushes_after_window(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=100, max_messages=10, max_chars=4000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("hello"))
        await asyncio.sleep(0.2)
        assert len(flushed) == 1
        assert flushed[0].text == "hello"

    async def test_two_rapid_messages_coalesced(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=200, max_messages=10, max_chars=4000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("hello"))
        await debouncer.submit(_msg("world"))
        await asyncio.sleep(0.3)
        assert len(flushed) == 1
        assert flushed[0].text == "hello\nworld"

    async def test_max_messages_flushes_immediately(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=5000, max_messages=3, max_chars=40000)
        debouncer = Debouncer(config, callback)
        for i in range(3):
            await debouncer.submit(_msg(f"msg{i}"))
        assert len(flushed) == 1
        assert flushed[0].text == "msg0\nmsg1\nmsg2"

    async def test_max_chars_flushes_immediately(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=5000, max_messages=100, max_chars=20)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("a" * 25))
        assert len(flushed) == 1

    async def test_different_conversations_independent(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=100, max_messages=10, max_chars=4000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("a", conv="c1"))
        await debouncer.submit(_msg("b", conv="c2"))
        await asyncio.sleep(0.2)
        assert len(flushed) == 2
        texts = {m.text for m in flushed}
        assert texts == {"a", "b"}

    async def test_close_flushes_all_pending(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=10000, max_messages=100, max_chars=40000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("a", conv="c1"))
        await debouncer.submit(_msg("b", conv="c2"))
        await debouncer.close()
        assert len(flushed) == 2

    async def test_attachments_merged(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=100, max_messages=10, max_chars=4000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(
            _msg("a", attachments=[Attachment(url="http://a.png", mime_type="image/png")])
        )
        await debouncer.submit(
            _msg("b", attachments=[Attachment(url="http://b.png", mime_type="image/png")])
        )
        await asyncio.sleep(0.2)
        assert len(flushed) == 1
        assert len(flushed[0].attachments) == 2

    async def test_is_mention_ored(self):
        flushed: list[InboundMessage] = []

        async def callback(msg: InboundMessage) -> None:
            flushed.append(msg)

        config = DebounceConfig(window_ms=100, max_messages=10, max_chars=4000)
        debouncer = Debouncer(config, callback)
        await debouncer.submit(_msg("a", is_mention=False))
        await debouncer.submit(_msg("b", is_mention=True))
        await asyncio.sleep(0.2)
        assert flushed[0].is_mention is True
