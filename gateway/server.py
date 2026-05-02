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

import importlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gateway.config import GatewayConfig
from gateway.core.a2a_client import A2AClient
from gateway.core.auth import (
    AuthProvider,
    GoogleAccessTokenAuth,
    GoogleIDTokenAuth,
    StaticTokenAuth,
)
from gateway.core.channel import ChannelAdapter
from gateway.core.chunking import ChunkConfig, ChunkMode
from gateway.core.concurrency import ConcurrencyLimiter
from gateway.core.debounce import DebounceConfig
from gateway.core.health import HealthMonitor
from gateway.core.policies import GroupMode, GroupPolicyChecker, GroupPolicyConfig
from gateway.core.rate_limit import BackoffConfig, RateLimitConfig
from gateway.core.router import Router
from gateway.core.types import OutboundMessage
from gateway.core.typing_indicator import TypingIndicator

logger = logging.getLogger(__name__)


def create_app(
    config: GatewayConfig,
    custom_channels: list[ChannelAdapter] | None = None,
) -> FastAPI:
    policy_checker = _build_policy_checker(config)
    debounce_cfg = _build_debounce(config)
    chunk_cfg = _build_chunk(config)
    a2a_rate, channel_rates, backoff, backoff_overrides = _build_rate_limiting(config)
    health = _build_health(config)
    concurrency = _build_concurrency(config)
    typing = _build_typing(config)
    ack_cfg = _build_ack(config)
    a2a_auth = _build_a2a_auth(config)

    router = Router(
        A2AClient(config.a2a_server_url, auth=a2a_auth),
        policy_checker=policy_checker,
        debounce_config=debounce_cfg,
        chunk_config=chunk_cfg,
        a2a_rate_limit=a2a_rate,
        channel_rate_limits=channel_rates,
        backoff_config=backoff,
        backoff_overrides=backoff_overrides,
        health_monitor=health,
        session_idle_timeout_minutes=(
            config.session.idle_timeout_minutes if config.session.enabled else None
        ),
        concurrency_limiter=concurrency,
        typing_indicator=typing,
        ack_config=ack_cfg,
        streaming_update_interval_ms=(
            config.streaming.update_interval_ms if config.streaming.enabled else None
        ),
    )

    webhook_adapters = []

    for acct in config.slack_accounts:
        from gateway.channels.slack import SlackAdapter

        router.register(
            SlackAdapter(
                bot_token=acct.bot_token,
                app_token=acct.app_token,
                account_id=acct.account_id,
            ),
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )

    for acct in config.whatsapp_accounts:
        from gateway.channels.whatsapp import WhatsAppAdapter

        adapter = WhatsAppAdapter(
            access_token=acct.access_token,
            phone_number_id=acct.phone_number_id,
            verify_token=acct.verify_token,
            app_secret=acct.app_secret,
            account_id=acct.account_id,
        )
        router.register(
            adapter,
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )
        webhook_adapters.append(adapter)

    for acct in config.google_chat_accounts:
        from gateway.channels.google_chat import GoogleChatAdapter

        adapter = GoogleChatAdapter(
            service_account_path=acct.service_account_path,
            account_id=acct.account_id,
            verification_token=acct.verification_token,
        )
        router.register(
            adapter,
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )
        webhook_adapters.append(adapter)

    for acct in config.discord_accounts:
        from gateway.channels.discord import DiscordAdapter

        router.register(
            DiscordAdapter(
                bot_token=acct.bot_token,
                account_id=acct.account_id,
            ),
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )

    for acct in config.telegram_accounts:
        from gateway.channels.telegram import TelegramAdapter

        router.register(
            TelegramAdapter(
                bot_token=acct.bot_token,
                account_id=acct.account_id,
            ),
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )

    for acct in config.email_accounts:
        from gateway.channels.email import EmailAdapter

        router.register(
            EmailAdapter(
                listen_host=acct.listen_host,
                listen_port=acct.listen_port,
                smtp_host=acct.smtp_host,
                smtp_port=acct.smtp_port,
                from_address=acct.from_address,
                smtp_user=acct.smtp_user,
                smtp_password=acct.smtp_password,
                account_id=acct.account_id,
            ),
            features=acct.features,
            context_template=acct.context_template,
            context_enabled=acct.context_enabled,
        )

    for custom in config.custom_channels:
        if "." not in custom.class_path:
            raise ValueError(
                f"custom channel class_path must be a dotted path,"
                f" got: {custom.class_path!r}"
            )
        module_path, class_name = custom.class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            raise ImportError(
                f"{custom.class_path}: {class_name!r} not found in module {module_path!r}"
            )
        if not (isinstance(cls, type) and issubclass(cls, ChannelAdapter)):
            raise TypeError(f"{custom.class_path} is not a ChannelAdapter subclass")
        adapter = cls(account_id=custom.account_id, **custom.kwargs)
        router.register(adapter, features=custom.features)
        if hasattr(adapter, "router"):
            webhook_adapters.append(adapter)

    if custom_channels:
        for adapter in custom_channels:
            router.register(adapter)
            if hasattr(adapter, "router"):
                webhook_adapters.append(adapter)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await router.start_all()
        logger.info(
            "gateway started — %d channel(s) active, A2A server: %s",
            len(router.channels),
            config.a2a_server_url,
        )
        yield
        await router.stop_all()

    app = FastAPI(title="a2a-gateway", lifespan=lifespan)

    for adapter in webhook_adapters:
        app.include_router(adapter.router)

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    async def ready() -> dict[str, str] | JSONResponse:
        if health and not health.is_ready():
            return JSONResponse(
                status_code=503,
                content={"status": "not ready"},
            )
        return {"status": "ok"}

    @app.get("/health")
    async def health_endpoint() -> dict[str, Any]:
        base: dict[str, object] = {
            "status": "ok",
            "channels": list(router.channels.keys()),
            "a2a_server": config.a2a_server_url,
        }
        if health:
            base.update(health.get_status())
        caps = router.get_cached_capabilities()
        if caps:
            base["agent_capabilities"] = {
                "streaming": caps.streaming,
                "max_message_length": caps.max_message_length,
                "supported_content_types": caps.supported_content_types,
            }
        return base

    @app.post("/push")
    async def push(request: Request) -> JSONResponse:
        try:
            body = json.loads(await request.body())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=422,
                content={"error": "invalid JSON body"},
            )

        channel = body.get("channel")
        recipient_id = body.get("recipient_id")
        text = body.get("text")

        if not channel or not recipient_id or not text:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "channel, recipient_id, and text are required"
                },
            )

        adapter = router.channels.get(channel)
        if not adapter:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"channel {channel!r} not found",
                    "available": list(router.channels.keys()),
                },
            )

        msg = OutboundMessage(
            channel=channel,
            recipient_id=recipient_id,
            text=text,
            thread_id=body.get("thread_id"),
            conversation_id=body.get("conversation_id"),
        )
        try:
            message_id = await adapter.send(msg)
        except Exception:
            logger.exception("push send failed on channel %s", channel)
            return JSONResponse(
                status_code=502,
                content={"error": "adapter send failed"},
            )
        return JSONResponse(
            content={"status": "sent", "message_id": message_id},
        )

    return app


def _build_a2a_auth(config: GatewayConfig) -> AuthProvider | None:
    a = config.a2a_auth
    if not a or not a.type:
        return None
    if a.type == "google_id_token":
        return GoogleIDTokenAuth(audience=config.a2a_server_url)
    if a.type == "google_access_token":
        return GoogleAccessTokenAuth(scopes=a.scopes if a.scopes else None)
    if a.type == "token":
        if not a.token:
            raise ValueError("A2A auth type 'token' requires a token value")
        return StaticTokenAuth(token=a.token)
    raise ValueError(f"unknown A2A auth type: {a.type!r}")


def _build_ack(config: GatewayConfig) -> dict[str, dict] | None:
    a = config.ack
    if not a:
        return None
    return {
        "slack": a.slack,
        "whatsapp": a.whatsapp,
        "google_chat": a.google_chat,
    }


def _build_typing(config: GatewayConfig) -> TypingIndicator | None:
    t = config.typing
    if not t or not t.enabled:
        return None
    return TypingIndicator(ttl_seconds=t.ttl_seconds)


def _build_concurrency(config: GatewayConfig) -> ConcurrencyLimiter | None:
    if not config.concurrency.enabled:
        return None
    return ConcurrencyLimiter(config.concurrency)


def _build_health(config: GatewayConfig) -> HealthMonitor | None:
    if not config.health.enabled:
        return None
    return HealthMonitor(stale_timeout_seconds=config.health.stale_timeout_seconds)


def _build_policy_checker(config: GatewayConfig) -> GroupPolicyChecker | None:
    gp = config.group_policies
    if not gp:
        return None

    policies: dict[str, GroupPolicyConfig] = {}
    for channel, entry in [
        ("slack", gp.slack),
        ("whatsapp", gp.whatsapp),
        ("google_chat", gp.google_chat),
        ("telegram", gp.telegram),
        ("discord", gp.discord),
        ("email", gp.email),
    ]:
        mode = GroupMode(entry.mode)
        overrides = {k: GroupMode(v) for k, v in entry.overrides.items()}
        policies[channel] = GroupPolicyConfig(mode=mode, overrides=overrides)

    return GroupPolicyChecker(policies)


def _build_debounce(config: GatewayConfig) -> DebounceConfig | None:
    d = config.debounce
    if not d.enabled:
        return None
    return DebounceConfig(
        window_ms=d.window_ms,
        max_messages=d.max_messages,
        max_chars=d.max_chars,
    )


def _build_chunk(config: GatewayConfig) -> ChunkConfig | None:
    if not config.chunking.enabled:
        return None
    return ChunkConfig(
        mode=ChunkMode(config.chunking.mode),
        default_limit=config.chunking.default_limit,
    )


def _build_rate_limiting(
    config: GatewayConfig,
) -> tuple[
    RateLimitConfig | None,
    dict[str, RateLimitConfig] | None,
    BackoffConfig,
    dict[str, BackoffConfig] | None,
]:
    rl = config.rate_limiting

    backoff = BackoffConfig(
        initial=rl.backoff.initial,
        factor=rl.backoff.factor,
        max_delay=rl.backoff.max_delay,
        max_retries=rl.backoff.max_retries,
    )

    backoff_overrides: dict[str, BackoffConfig] | None = None
    if rl.backoff_overrides:
        backoff_overrides = {
            ch: BackoffConfig(
                initial=bo.initial,
                factor=bo.factor,
                max_delay=bo.max_delay,
                max_retries=bo.max_retries,
            )
            for ch, bo in rl.backoff_overrides.items()
        }

    if not rl.enabled:
        return None, None, backoff, backoff_overrides

    a2a_rate = RateLimitConfig(
        max_requests=rl.a2a.max_requests,
        window_seconds=rl.a2a.window_seconds,
    )

    channel_rate = RateLimitConfig(
        max_requests=rl.channel.max_requests,
        window_seconds=rl.channel.window_seconds,
    )
    channel_rates: dict[str, RateLimitConfig] = dict.fromkeys(
        ("slack", "whatsapp", "google_chat", "email", "telegram", "discord"),
        channel_rate,
    )
    for ch, override in rl.channel_overrides.items():
        channel_rates[ch] = RateLimitConfig(
            max_requests=override.max_requests,
            window_seconds=override.window_seconds,
        )

    return a2a_rate, channel_rates, backoff, backoff_overrides
