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

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml

logger = logging.getLogger(__name__)

T = TypeVar("T")

# --- Channel account configs ---


@dataclass
class SlackAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    bot_token: str = ""
    app_token: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class WhatsAppAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    verify_token: str = ""
    access_token: str = ""
    phone_number_id: str = ""
    app_secret: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class GoogleChatAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    service_account_path: str = ""
    verification_token: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class DiscordAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    bot_token: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class TelegramAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    bot_token: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class EmailAccountConfig:
    account_id: str = "default"
    enabled: bool = False
    listen_host: str = "localhost"
    listen_port: int = 1025
    smtp_host: str = "localhost"
    smtp_port: int = 587
    from_address: str = "agent@example.com"
    smtp_user: str = ""
    smtp_password: str = ""
    context_template: str = ""
    context_enabled: bool = True
    features: dict[str, bool] = field(default_factory=dict)


@dataclass
class CustomChannelConfig:
    class_path: str = ""
    account_id: str = "default"
    enabled: bool = True
    kwargs: dict[str, Any] = field(default_factory=dict)
    features: dict[str, bool] = field(default_factory=dict)


# --- Feature configs ---


@dataclass
class ChunkingConfig:
    enabled: bool = True
    mode: str = "newline"
    default_limit: int = 4000


@dataclass
class DebounceConfig:
    enabled: bool = True
    window_ms: int = 500
    max_messages: int = 10
    max_chars: int = 4000


@dataclass
class RateLimitEntry:
    max_requests: int = 60
    window_seconds: float = 60.0


@dataclass
class BackoffEntry:
    initial: float = 1.0
    factor: float = 2.0
    max_delay: float = 300.0
    max_retries: int = 5


@dataclass
class RateLimitingConfig:
    enabled: bool = True
    a2a: RateLimitEntry = field(default_factory=RateLimitEntry)
    channel: RateLimitEntry = field(
        default_factory=lambda: RateLimitEntry(max_requests=30)
    )
    backoff: BackoffEntry = field(default_factory=BackoffEntry)
    channel_overrides: dict[str, RateLimitEntry] = field(default_factory=dict)
    backoff_overrides: dict[str, BackoffEntry] = field(default_factory=dict)


@dataclass
class AckConfig:
    slack: dict[str, str] = field(default_factory=lambda: {"emoji": "eyes"})
    whatsapp: dict[str, str] = field(default_factory=lambda: {"read_receipts": "true"})
    google_chat: dict[str, str] = field(default_factory=lambda: {"emoji": "eyes"})


@dataclass
class TypingConfig:
    enabled: bool = True
    ttl_seconds: float = 30.0


@dataclass
class StreamingConfig:
    enabled: bool = True
    update_interval_ms: int = 500


@dataclass
class ConcurrencyConfig:
    enabled: bool = True
    max_concurrent: int = 5
    per: str = "conversation"


@dataclass
class SessionConfig:
    enabled: bool = True
    idle_timeout_minutes: float = 30.0


@dataclass
class HealthConfig:
    enabled: bool = True
    stale_timeout_seconds: float = 300.0


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "text"
    subsystem_levels: dict[str, str] = field(default_factory=dict)


@dataclass
class GroupPolicyEntry:
    mode: str = "open"
    overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class GroupPoliciesConfig:
    slack: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)
    whatsapp: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)
    google_chat: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)
    email: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)
    telegram: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)
    discord: GroupPolicyEntry = field(default_factory=GroupPolicyEntry)


@dataclass
class A2AAuthConfig:
    type: str = ""
    token: str = ""
    scopes: list[str] = field(default_factory=list)


# --- Top-level config ---


@dataclass
class GatewayConfig:
    a2a_server_url: str = "http://localhost:8001"
    a2a_agent_card_path: str = "/.well-known/agent-card.json"
    a2a_auth: A2AAuthConfig | None = None
    host: str = "0.0.0.0"
    port: int = 8000

    slack_accounts: list[SlackAccountConfig] = field(default_factory=list)
    whatsapp_accounts: list[WhatsAppAccountConfig] = field(default_factory=list)
    google_chat_accounts: list[GoogleChatAccountConfig] = field(default_factory=list)
    discord_accounts: list[DiscordAccountConfig] = field(default_factory=list)
    telegram_accounts: list[TelegramAccountConfig] = field(default_factory=list)
    email_accounts: list[EmailAccountConfig] = field(default_factory=list)
    custom_channels: list[CustomChannelConfig] = field(default_factory=list)

    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    debounce: DebounceConfig = field(default_factory=DebounceConfig)
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)

    group_policies: GroupPoliciesConfig | None = None
    logging: LoggingConfig | None = None
    typing: TypingConfig | None = None
    ack: AckConfig | None = None


def load_config(path: str | Path = "config.yaml") -> GatewayConfig:
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    a2a = raw.get("a2a", {})
    channels = raw.get("channels", {})

    cfg = GatewayConfig(
        a2a_server_url=a2a.get("server_url", "http://localhost:8001"),
        a2a_agent_card_path=a2a.get("agent_card_path", "/.well-known/agent-card.json"),
        a2a_auth=_build_optional(A2AAuthConfig, a2a.get("auth")),
        host=raw.get("host", "0.0.0.0"),
        port=raw.get("port", 8000),
        slack_accounts=_parse_accounts(SlackAccountConfig, channels.get("slack")),
        whatsapp_accounts=_parse_accounts(
            WhatsAppAccountConfig, channels.get("whatsapp")
        ),
        google_chat_accounts=_parse_accounts(
            GoogleChatAccountConfig, channels.get("google_chat")
        ),
        discord_accounts=_parse_accounts(DiscordAccountConfig, channels.get("discord")),
        telegram_accounts=_parse_accounts(
            TelegramAccountConfig, channels.get("telegram")
        ),
        email_accounts=_parse_accounts(EmailAccountConfig, channels.get("email")),
        custom_channels=[
            cc
            for entry in raw.get("custom_channels", [])
            if (cc := _build(CustomChannelConfig, entry)).enabled
        ],
        chunking=_build_with_defaults(ChunkingConfig, raw.get("chunking")),
        debounce=_build_with_defaults(DebounceConfig, raw.get("debounce")),
        rate_limiting=_parse_rate_limiting(raw.get("rate_limiting", {})),
        health=_build_with_defaults(HealthConfig, raw.get("health")),
        session=_build_with_defaults(SessionConfig, raw.get("session")),
        concurrency=_build_with_defaults(ConcurrencyConfig, raw.get("concurrency")),
        streaming=_build_with_defaults(StreamingConfig, raw.get("streaming")),
        group_policies=_parse_group_policies(raw.get("group_policies")),
        logging=_parse_logging(raw.get("logging")),
        typing=_build_optional(TypingConfig, raw.get("typing")),
        ack=_parse_ack(raw.get("ack")),
    )

    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: GatewayConfig) -> None:
    import os

    env = os.environ.get

    if val := env("A2A_SERVER_URL"):
        cfg.a2a_server_url = val
    if val := env("A2A_AGENT_CARD_PATH"):
        cfg.a2a_agent_card_path = val
    if auth_type := env("A2A_AUTH"):
        if cfg.a2a_auth is None:
            cfg.a2a_auth = A2AAuthConfig()
        cfg.a2a_auth.type = auth_type
        if token := env("A2A_AUTH_TOKEN"):
            cfg.a2a_auth.token = token
    if val := env("GATEWAY_HOST"):
        cfg.host = val
    if val := env("PORT"):
        try:
            cfg.port = int(val)
        except ValueError:
            raise ValueError(f"PORT must be an integer, got: {val!r}") from None

    if (token := env("SLACK_BOT_TOKEN")) and not cfg.slack_accounts:
        cfg.slack_accounts = [
            SlackAccountConfig(
                enabled=True,
                bot_token=token,
                app_token=env("SLACK_APP_TOKEN", ""),
            )
        ]

    if (token := env("WHATSAPP_ACCESS_TOKEN")) and not cfg.whatsapp_accounts:
        cfg.whatsapp_accounts = [
            WhatsAppAccountConfig(
                enabled=True,
                access_token=token,
                phone_number_id=env("WHATSAPP_PHONE_NUMBER_ID", ""),
                verify_token=env("WHATSAPP_VERIFY_TOKEN", ""),
                app_secret=env("WHATSAPP_APP_SECRET", ""),
            )
        ]

    if (
        sa_path := env("GOOGLE_CHAT_SERVICE_ACCOUNT_PATH")
    ) and not cfg.google_chat_accounts:
        cfg.google_chat_accounts = [
            GoogleChatAccountConfig(
                enabled=True,
                service_account_path=sa_path,
            )
        ]

    if (dc_token := env("DISCORD_BOT_TOKEN")) and not cfg.discord_accounts:
        cfg.discord_accounts = [DiscordAccountConfig(enabled=True, bot_token=dc_token)]

    if (tg_token := env("TELEGRAM_BOT_TOKEN")) and not cfg.telegram_accounts:
        cfg.telegram_accounts = [TelegramAccountConfig(enabled=True, bot_token=tg_token)]

    if (host := env("EMAIL_SMTP_HOST")) and not cfg.email_accounts:
        cfg.email_accounts = [
            EmailAccountConfig(
                enabled=True,
                listen_host=env("EMAIL_LISTEN_HOST", "0.0.0.0"),
                listen_port=_safe_int(
                    env("EMAIL_LISTEN_PORT", "1025"), "EMAIL_LISTEN_PORT"
                ),
                smtp_host=host,
                smtp_port=_safe_int(env("EMAIL_SMTP_PORT", "587"), "EMAIL_SMTP_PORT"),
                from_address=env("EMAIL_FROM_ADDRESS", "agent@example.com"),
                smtp_user=env("EMAIL_SMTP_USER", ""),
                smtp_password=env("EMAIL_SMTP_PASSWORD", ""),
            )
        ]


def _safe_int(val: str, name: str) -> int:
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got: {val!r}") from None


def _build(cls: type[T], data: dict[str, Any]) -> T:
    valid = {f.name for f in fields(cls)}
    unknown = set(data.keys()) - valid
    if unknown:
        logger.warning("unknown config keys for %s: %s", cls.__name__, unknown)
    return cls(**{k: v for k, v in data.items() if k in valid})


def _build_with_defaults(cls: type[T], data: dict[str, Any] | None) -> T:
    if not data:
        return cls()
    return _build(cls, data)


def _build_optional(cls: type[T], data: dict[str, Any] | None) -> T | None:
    if not data:
        return None
    return _build(cls, data)


def _parse_accounts(cls: type[T], data: Any) -> list[T]:
    if data is None:
        return []
    if isinstance(data, list):
        return [_build(cls, item) for item in data if item.get("enabled", False)]
    if isinstance(data, dict) and data.get("enabled", False):
        return [_build(cls, data)]
    return []


def _parse_rate_limiting(data: dict) -> RateLimitingConfig:
    channel_overrides = {
        ch: _build(RateLimitEntry, cfg)
        for ch, cfg in data.get("channel_overrides", {}).items()
    }
    backoff_overrides = {
        ch: _build(BackoffEntry, cfg)
        for ch, cfg in data.get("backoff_overrides", {}).items()
    }
    return RateLimitingConfig(
        enabled=data.get("enabled", True),
        a2a=_build(RateLimitEntry, data.get("a2a", {})),
        channel=_build(RateLimitEntry, data.get("channel", {})),
        backoff=_build(BackoffEntry, data.get("backoff", {})),
        channel_overrides=channel_overrides,
        backoff_overrides=backoff_overrides,
    )


def _parse_group_policies(data: dict | None) -> GroupPoliciesConfig | None:
    if not data:
        return None
    return GroupPoliciesConfig(
        slack=_build(GroupPolicyEntry, data.get("slack", {})),
        whatsapp=_build(GroupPolicyEntry, data.get("whatsapp", {})),
        google_chat=_build(GroupPolicyEntry, data.get("google_chat", {})),
        email=_build(GroupPolicyEntry, data.get("email", {})),
        telegram=_build(GroupPolicyEntry, data.get("telegram", {})),
        discord=_build(GroupPolicyEntry, data.get("discord", {})),
    )


def _parse_logging(data: dict | None) -> LoggingConfig | None:
    if not data:
        return None
    return LoggingConfig(
        level=data.get("level", "INFO"),
        format=data.get("format", "text"),
        subsystem_levels=data.get("subsystem_levels", {}),
    )


def _parse_ack(data: dict | None) -> AckConfig | None:
    if not data:
        return None
    return AckConfig(
        slack=data.get("slack", {"emoji": "eyes"}),
        whatsapp=data.get("whatsapp", {"read_receipts": "true"}),
        google_chat=data.get("google_chat", {"emoji": "eyes"}),
    )
