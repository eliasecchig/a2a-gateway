from __future__ import annotations

import pytest

from gateway.core.chunking import CHANNEL_LIMITS, ChunkConfig, ChunkMode, MessageChunker


@pytest.fixture
def chunker_newline() -> MessageChunker:
    return MessageChunker(ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=100))


@pytest.fixture
def chunker_length() -> MessageChunker:
    return MessageChunker(ChunkConfig(mode=ChunkMode.LENGTH, default_limit=100))


class TestChunkNewline:
    def test_short_text_single_chunk(self, chunker_newline: MessageChunker):
        result = chunker_newline.chunk("Hello world", "slack")
        assert result == ["Hello world"]

    def test_text_at_exact_limit(self, chunker_newline: MessageChunker):
        text = "a" * 100
        result = chunker_newline.chunk(text, "slack")
        assert result == [text]

    def test_text_over_limit_splits(self, chunker_newline: MessageChunker):
        text = "A" * 60 + "\n\n" + "B" * 60
        result = chunker_newline.chunk(text, "unknown_channel")
        assert len(result) == 2
        assert result[0] == "A" * 60
        assert result[1] == "B" * 60

    def test_paragraph_boundary_preferred(self, chunker_newline: MessageChunker):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunker = MessageChunker(ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=40))
        result = chunker.chunk(text, "unknown_channel")
        assert len(result) >= 2
        assert "First paragraph." in result[0]

    def test_code_fence_never_split(self, chunker_newline: MessageChunker):
        text = "Before\n\n```python\nprint('hello')\nprint('world')\n```\n\nAfter more text that pushes over limit"
        chunker = MessageChunker(ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=60))
        result = chunker.chunk(text, "slack")
        full = "\n".join(result)
        fence_count = full.count("```")
        assert fence_count % 2 == 0

    def test_code_fence_spanning_chunks(self):
        code = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(20)) + "\n```"
        chunker = MessageChunker(ChunkConfig(mode=ChunkMode.NEWLINE, default_limit=80))
        result = chunker.chunk(code, "slack")
        if len(result) > 1:
            assert result[0].rstrip().endswith("```")
            assert result[1].startswith("```")


class TestChunkLength:
    def test_short_text_single_chunk(self, chunker_length: MessageChunker):
        result = chunker_length.chunk("Hello", "slack")
        assert result == ["Hello"]

    def test_hard_split_at_limit(self, chunker_length: MessageChunker):
        text = "word " * 30
        result = chunker_length.chunk(text.strip(), "unknown_channel")
        assert all(len(c) <= 100 for c in result)

    def test_prefers_whitespace_break(self, chunker_length: MessageChunker):
        text = "Hello world " * 12
        result = chunker_length.chunk(text.strip(), "unknown_channel")
        for chunk in result[:-1]:
            assert not chunk.endswith(" ")


class TestChannelLimits:
    def test_email_unlimited(self):
        chunker = MessageChunker(ChunkConfig(default_limit=100))
        text = "x" * 500
        result = chunker.chunk(text, "email")
        assert result == [text]

    def test_slack_limit(self):
        assert CHANNEL_LIMITS["slack"] == 4000

    def test_whatsapp_limit(self):
        assert CHANNEL_LIMITS["whatsapp"] == 4096

    @pytest.mark.parametrize(
        "channel,expected_limit",
        [
            ("slack", 4000),
            ("whatsapp", 4096),
            ("google_chat", 4096),
            ("email", 0),
        ],
    )
    def test_channel_limits_values(self, channel: str, expected_limit: int):
        assert CHANNEL_LIMITS[channel] == expected_limit
