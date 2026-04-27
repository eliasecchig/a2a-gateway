from __future__ import annotations

import pytest

from gateway.core.markdown import (
    PassthroughMarkdown,
    SlackMarkdownAdapter,
    WhatsAppMarkdownAdapter,
    get_markdown_adapter,
)


class TestWhatsAppMarkdown:
    @pytest.fixture
    def adapter(self) -> WhatsAppMarkdownAdapter:
        return WhatsAppMarkdownAdapter()

    def test_bold_conversion(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("**bold**") == "*bold*"

    def test_underline_conversion(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("__underline__") == "_underline_"

    def test_strikethrough_conversion(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("~~strike~~") == "~strike~"

    def test_link_to_plain(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("[click](https://x.com)") == "click (https://x.com)"

    def test_heading_stripped(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("## Heading") == "Heading"

    def test_code_fence_preserved(self, adapter: WhatsAppMarkdownAdapter):
        text = "before ```code **bold**``` after"
        result = adapter.format_text(text)
        assert "```code **bold**```" in result

    def test_image_converted(self, adapter: WhatsAppMarkdownAdapter):
        result = adapter.format_text("![alt](img.png)")
        assert "img.png" not in result or "alt" in result

    def test_hr_removed(self, adapter: WhatsAppMarkdownAdapter):
        assert adapter.format_text("---").strip() == ""


class TestSlackMarkdown:
    @pytest.fixture
    def adapter(self) -> SlackMarkdownAdapter:
        return SlackMarkdownAdapter()

    def test_bold_conversion(self, adapter: SlackMarkdownAdapter):
        assert adapter.format_text("**bold**") == "*bold*"

    def test_link_to_slack_format(self, adapter: SlackMarkdownAdapter):
        assert adapter.format_text("[text](https://x.com)") == "<https://x.com|text>"

    def test_html_unescape(self, adapter: SlackMarkdownAdapter):
        assert adapter.format_text("&amp; &lt;") == "& <"

    def test_code_fence_preserved(self, adapter: SlackMarkdownAdapter):
        text = "hi ```**bold** inside``` bye"
        result = adapter.format_text(text)
        assert "```**bold** inside```" in result


class TestPassthrough:
    def test_returns_unchanged(self):
        adapter = PassthroughMarkdown()
        text = "**bold** [link](url)"
        assert adapter.format_text(text) == text


class TestGetMarkdownAdapter:
    def test_whatsapp(self):
        assert isinstance(get_markdown_adapter("whatsapp"), WhatsAppMarkdownAdapter)

    def test_slack(self):
        assert isinstance(get_markdown_adapter("slack"), SlackMarkdownAdapter)

    def test_google_chat_passthrough(self):
        assert isinstance(get_markdown_adapter("google_chat"), PassthroughMarkdown)

    def test_email_passthrough(self):
        assert isinstance(get_markdown_adapter("email"), PassthroughMarkdown)

    def test_unknown_channel_passthrough(self):
        assert isinstance(get_markdown_adapter("unknown"), PassthroughMarkdown)
