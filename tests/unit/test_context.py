from __future__ import annotations

from gateway.core.context import ChannelContextInjector
from gateway.core.session import SessionState


class TestChannelContextInjector:
    def test_default_template_slack(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack")
        session = SessionState()

        result = injector.inject("hello", "slack", session)

        assert result.startswith("[Channel: Slack")
        assert "markdown" in result
        assert "4000" in result
        assert result.endswith("\n\nhello")

    def test_default_template_email_omits_max_length(self) -> None:
        injector = ChannelContextInjector()
        injector.register("email")
        session = SessionState()

        result = injector.inject("hello", "email", session)

        assert "Max message" not in result
        assert "Channel: Email" in result
        assert "html" in result
        assert result.endswith("\n\nhello")

    def test_default_template_all_known_channels(self) -> None:
        known = [
            "slack",
            "whatsapp",
            "google_chat",
            "discord",
            "telegram",
            "email",
        ]
        for ch in known:
            injector = ChannelContextInjector()
            injector.register(ch)
            session = SessionState()

            result = injector.inject("hi", ch, session)

            assert result.endswith("\n\nhi")
            assert "[Channel:" in result

    def test_skips_injection_when_context_id_set(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack")
        session = SessionState(context_id="existing-context")

        result = injector.inject("hello", "slack", session)

        assert result == "hello"

    def test_skips_injection_when_not_registered(self) -> None:
        injector = ChannelContextInjector()
        session = SessionState()

        result = injector.inject("hello", "slack", session)

        assert result == "hello"

    def test_skips_injection_when_disabled(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack", enabled=False)
        session = SessionState()

        result = injector.inject("hello", "slack", session)

        assert result == "hello"

    def test_custom_template(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack", template="[{channel} | limit={max_length}]")
        session = SessionState()

        result = injector.inject("hello", "slack", session)

        assert result == "[Slack | limit=4000]\n\nhello"

    def test_account_qualified_channel(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack:team-a")
        session = SessionState()

        result = injector.inject("hello", "slack:team-a", session)

        assert result.startswith("[Channel: Slack")
        assert result.endswith("\n\nhello")

    def test_unknown_base_channel_skips(self) -> None:
        injector = ChannelContextInjector()
        injector.register("unknown_platform")
        session = SessionState()

        result = injector.inject("hello", "unknown_platform", session)

        assert result == "hello"

    def test_bad_template_skips_injection(self) -> None:
        injector = ChannelContextInjector()
        injector.register("slack", template="{channel} {unknown_var}")
        session = SessionState()

        result = injector.inject("hello", "slack", session)

        assert result == "hello"
