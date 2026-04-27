from __future__ import annotations

from gateway.core.policies import GroupMode, GroupPolicyChecker, GroupPolicyConfig
from gateway.core.types import InboundMessage


def _msg(
    channel: str = "slack",
    is_group: bool = True,
    is_mention: bool = False,
    conv: str = "C123",
) -> InboundMessage:
    return InboundMessage(
        channel=channel,
        sender_id="u1",
        sender_name="Alice",
        text="hello",
        conversation_id=conv,
        is_group=is_group,
        is_mention=is_mention,
    )


class TestGroupPolicyChecker:
    def test_dm_always_passes(self):
        checker = GroupPolicyChecker(
            {"slack": GroupPolicyConfig(mode=GroupMode.DISABLED)}
        )
        assert checker.should_process(_msg(is_group=False)) is True

    def test_open_mode_passes(self):
        checker = GroupPolicyChecker({"slack": GroupPolicyConfig(mode=GroupMode.OPEN)})
        assert checker.should_process(_msg()) is True

    def test_mention_only_no_mention_blocked(self):
        checker = GroupPolicyChecker(
            {"slack": GroupPolicyConfig(mode=GroupMode.MENTION_ONLY)}
        )
        assert checker.should_process(_msg(is_mention=False)) is False

    def test_mention_only_with_mention_passes(self):
        checker = GroupPolicyChecker(
            {"slack": GroupPolicyConfig(mode=GroupMode.MENTION_ONLY)}
        )
        assert checker.should_process(_msg(is_mention=True)) is True

    def test_disabled_blocked(self):
        checker = GroupPolicyChecker(
            {"slack": GroupPolicyConfig(mode=GroupMode.DISABLED)}
        )
        assert checker.should_process(_msg()) is False

    def test_per_group_override(self):
        checker = GroupPolicyChecker(
            {
                "slack": GroupPolicyConfig(
                    mode=GroupMode.DISABLED,
                    overrides={"C123": GroupMode.OPEN},
                )
            }
        )
        assert checker.should_process(_msg(conv="C123")) is True
        assert checker.should_process(_msg(conv="C999")) is False

    def test_multi_account_uses_base_channel(self):
        checker = GroupPolicyChecker(
            {"slack": GroupPolicyConfig(mode=GroupMode.DISABLED)}
        )
        assert checker.should_process(_msg(channel="slack:workspace_a")) is False

    def test_missing_channel_defaults_to_open(self):
        checker = GroupPolicyChecker({})
        assert checker.should_process(_msg(channel="slack")) is True
