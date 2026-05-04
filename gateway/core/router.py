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
import time

from gateway.core.a2a_client import A2AClient, A2AResponse, A2AStreamEvent
from gateway.core.capabilities import AgentCapabilities, CapabilityDiscovery
from gateway.core.channel import ChannelAdapter
from gateway.core.chunking import ChunkConfig, MessageChunker
from gateway.core.concurrency import ConcurrencyLimiter
from gateway.core.context import ChannelContextInjector
from gateway.core.debounce import DebounceConfig, Debouncer
from gateway.core.health import HealthMonitor
from gateway.core.markdown import get_markdown_adapter
from gateway.core.policies import GroupPolicyChecker
from gateway.core.rate_limit import (
    BackoffConfig,
    RateLimitConfig,
    RateLimiter,
    RetryWithBackoff,
)
from gateway.core.session import SessionState, SessionStore
from gateway.core.types import InboundMessage, OutboundMessage
from gateway.core.typing_indicator import TypingIndicator

logger = logging.getLogger(__name__)


class Router:
    def __init__(
        self,
        a2a_client: A2AClient,
        *,
        policy_checker: GroupPolicyChecker | None = None,
        debounce_config: DebounceConfig | None = None,
        chunk_config: ChunkConfig | None = None,
        a2a_rate_limit: RateLimitConfig | None = None,
        channel_rate_limits: dict[str, RateLimitConfig] | None = None,
        backoff_config: BackoffConfig | None = None,
        backoff_overrides: dict[str, BackoffConfig] | None = None,
        health_monitor: HealthMonitor | None = None,
        session_idle_timeout_minutes: float | None = None,
        concurrency_limiter: ConcurrencyLimiter | None = None,
        typing_indicator: TypingIndicator | None = None,
        ack_config: dict[str, dict] | None = None,
        streaming_update_interval_ms: int | None = None,
        agent_card_path: str = "/.well-known/agent-card.json",
    ) -> None:
        self.a2a = a2a_client
        self.channels: dict[str, ChannelAdapter] = {}
        self._session_store = SessionStore(session_idle_timeout_minutes)
        self._account_features: dict[str, dict[str, bool]] = {}
        self._health = health_monitor
        self._concurrency = concurrency_limiter
        self._typing = typing_indicator
        self._ack_config = ack_config
        self._capability_discovery = CapabilityDiscovery(agent_card_path)
        self._agent_capabilities: AgentCapabilities | None = None
        self._streaming_update_interval_ms = streaming_update_interval_ms

        self._policy = policy_checker
        self._chunker = MessageChunker(chunk_config) if chunk_config else None
        self._retry = RetryWithBackoff(backoff_config)
        self._channel_retries: dict[str, RetryWithBackoff] = {}
        if backoff_overrides:
            for ch, bo in backoff_overrides.items():
                self._channel_retries[ch] = RetryWithBackoff(bo)

        self._a2a_limiter = RateLimiter(a2a_rate_limit) if a2a_rate_limit else None
        self._channel_limiters: dict[str, RateLimiter] = {}
        if channel_rate_limits:
            for ch, cfg in channel_rate_limits.items():
                self._channel_limiters[ch] = RateLimiter(cfg)

        self._debouncer: Debouncer | None = None
        if debounce_config:
            self._debouncer = Debouncer(debounce_config, self._handle_inner)

        self._context_injector = ChannelContextInjector()

    def register(
        self,
        adapter: ChannelAdapter,
        *,
        features: dict[str, bool] | None = None,
        context_template: str = "",
        context_enabled: bool = True,
    ) -> None:
        self._context_injector.register(
            adapter.name,
            template=context_template,
            enabled=context_enabled,
        )
        if features:
            self._account_features[adapter.name] = features

        pipeline = self._debouncer.submit if self._debouncer else self._handle_inner

        if self._ack_config and self._feature_enabled(adapter.name, "ack"):
            base_ch = self._base_channel(adapter.name)
            ch_ack_config = self._ack_config.get(base_ch)

            async def _ack_then_pipeline(
                msg, _adapter=adapter, _cfg=ch_ack_config, _next=pipeline
            ):
                try:
                    await _adapter.send_ack(msg, _cfg)
                except Exception:
                    logger.debug("ack failed for %s", msg.channel)
                await _next(msg)

            adapter.on_message = _ack_then_pipeline
        else:
            adapter.on_message = pipeline

        self.channels[adapter.name] = adapter
        logger.info("registered channel: %s", adapter.name)

    def _feature_enabled(self, channel_name: str, feature: str) -> bool:
        acct_features = self._account_features.get(channel_name)
        if acct_features is None:
            return True
        return acct_features.get(feature, True)

    async def start_all(self) -> None:
        self._agent_capabilities = await self._capability_discovery.discover(
            self.a2a.server_url
        )
        logger.info(
            "agent capabilities: streaming=%s",
            self._agent_capabilities.streaming,
        )

        self._session_store.start_sweep()
        for adapter in self.channels.values():
            await adapter.start()
            if self._health:
                self._health.record_connect(adapter.name)

    def get_cached_capabilities(self) -> AgentCapabilities | None:
        return self._capability_discovery.get_cached()

    async def stop_all(self) -> None:
        await self._session_store.stop_sweep()
        if self._debouncer:
            await self._debouncer.close()
        for adapter in self.channels.values():
            if self._health:
                self._health.record_disconnect(adapter.name)
            await adapter.stop()
        await self.a2a.close()

    @staticmethod
    def _base_channel(channel: str) -> str:
        return channel.partition(":")[0]

    async def _handle_inner(self, msg: InboundMessage) -> None:
        if self._policy and not self._policy.should_process(msg):
            return

        session_key = f"{msg.channel}:{msg.conversation_id or msg.sender_id}"
        session = self._session_store.get(session_key)
        text = self._context_injector.inject(msg.text, msg.channel, session)
        base_ch = self._base_channel(msg.channel)

        if self._health:
            self._health.record_heartbeat(msg.channel)

        log_extra = {"channel": msg.channel, "sender_id": msg.sender_id}
        logger.info(
            "[%s] %s: %s",
            msg.channel,
            msg.sender_name,
            msg.text[:80],
            extra=log_extra,
        )

        if self._a2a_limiter:
            await self._a2a_limiter.acquire()

        adapter = self.channels.get(msg.channel)
        if self._typing and adapter and self._feature_enabled(msg.channel, "typing"):
            await self._typing.start(
                adapter,
                session_key,
                msg.conversation_id or msg.sender_id,
                msg.thread_id,
            )

        use_streaming = (
            self._streaming_update_interval_ms is not None
            and self._agent_capabilities is not None
            and self._agent_capabilities.streaming
            and adapter is not None
            and adapter.supports_editing
        )

        try:
            if use_streaming:
                assert adapter is not None
                await self._handle_streaming(
                    msg,
                    session,
                    session_key,
                    base_ch,
                    adapter,
                    log_extra,
                    text=text,
                )
                return

            result = await self._call_a2a(msg, session, session_key, log_extra, text=text)
        finally:
            if self._typing:
                await self._typing.stop(session_key)

        if result is None:
            return
        resp, a2a_ms = result

        self._session_store.update(session_key, resp.context_id)

        formatted_text = get_markdown_adapter(base_ch).format_text(resp.text)

        chunks = (
            self._chunker.chunk(formatted_text, base_ch)
            if self._chunker
            else [formatted_text]
        )

        logger.info(
            "[%s] response: %d chars, %d chunk(s), %.0fms",
            msg.channel,
            len(resp.text),
            len(chunks),
            a2a_ms,
            extra={
                **log_extra,
                "a2a_duration_ms": round(a2a_ms, 1),
                "chunks_sent": len(chunks),
            },
        )

        if not adapter:
            return

        for i, chunk_text in enumerate(chunks):
            is_last = i == len(chunks) - 1
            reply = OutboundMessage(
                channel=msg.channel,
                recipient_id=msg.sender_id,
                text=chunk_text,
                thread_id=msg.thread_id,
                conversation_id=msg.conversation_id,
                attachments=resp.attachments if is_last else [],
            )
            limiter = self._channel_limiters.get(base_ch)
            if limiter:
                await limiter.acquire()
            await adapter.send(reply)

    async def _handle_streaming(  # noqa: PLR0917
        self,
        msg: InboundMessage,
        session: SessionState,
        session_key: str,
        base_ch: str,
        adapter: ChannelAdapter,
        log_extra: dict[str, str],
        *,
        text: str,
    ) -> None:
        t0 = time.monotonic()
        interval_s = (self._streaming_update_interval_ms or 500) / 1000.0
        last_update = 0.0
        sent_msg_id: str | None = None
        accumulated_text = ""
        final_event: A2AStreamEvent | None = None

        retry = self._get_retry(msg.channel)
        try:
            async for event in retry.execute_stream(
                self.a2a.send_message_stream,
                text=text,
                context_id=session.context_id,
            ):
                if event.text:
                    accumulated_text = event.text

                if event.is_final:
                    final_event = event
                    break

                now = time.monotonic()
                if accumulated_text and (now - last_update) >= interval_s:
                    formatted = get_markdown_adapter(base_ch).format_text(
                        accumulated_text
                    )
                    if sent_msg_id is None:
                        reply = OutboundMessage(
                            channel=msg.channel,
                            recipient_id=msg.sender_id,
                            text=formatted,
                            thread_id=msg.thread_id,
                            conversation_id=msg.conversation_id,
                        )
                        sent_msg_id = await adapter.send(reply)
                    else:
                        await adapter.edit_message(
                            sent_msg_id,
                            msg.conversation_id or msg.sender_id,
                            formatted,
                            msg.thread_id,
                        )
                    last_update = now
        except Exception:
            logger.exception("streaming A2A call failed for session %s", session_key)
            if self._health:
                self._health.record_error(msg.channel, "a2a_stream_failed")
            await adapter.send(
                OutboundMessage(
                    channel=msg.channel,
                    recipient_id=msg.sender_id,
                    text="Sorry, I couldn't process your message right now.",
                    thread_id=msg.thread_id,
                    conversation_id=msg.conversation_id,
                )
            )
            return
        finally:
            if self._typing:
                await self._typing.stop(session_key)

        a2a_ms = (time.monotonic() - t0) * 1000

        if final_event and final_event.text:
            accumulated_text = final_event.text

        if final_event:
            self._session_store.update(session_key, final_event.context_id)

        formatted = get_markdown_adapter(base_ch).format_text(accumulated_text)

        if sent_msg_id is not None:
            await adapter.edit_message(
                sent_msg_id,
                msg.conversation_id or msg.sender_id,
                formatted,
                msg.thread_id,
            )
        elif accumulated_text:
            await adapter.send(
                OutboundMessage(
                    channel=msg.channel,
                    recipient_id=msg.sender_id,
                    text=formatted,
                    thread_id=msg.thread_id,
                    conversation_id=msg.conversation_id,
                    attachments=(final_event.attachments if final_event else []),
                )
            )

        logger.info(
            "[%s] streamed response: %d chars, %.0fms",
            msg.channel,
            len(accumulated_text),
            a2a_ms,
            extra={
                **log_extra,
                "a2a_duration_ms": round(a2a_ms, 1),
                "streaming": True,
            },
        )

    def _get_retry(self, channel: str) -> RetryWithBackoff:
        base_ch = self._base_channel(channel)
        return self._channel_retries.get(base_ch, self._retry)

    async def _call_a2a(
        self,
        msg: InboundMessage,
        session: SessionState,
        session_key: str,
        log_extra: dict[str, str],
        *,
        text: str,
    ) -> tuple[A2AResponse, float] | None:
        retry = self._get_retry(msg.channel)

        async def _do_call() -> tuple[A2AResponse, float]:
            t0 = time.monotonic()
            resp = await retry.execute(
                self.a2a.send_message,
                text=text,
                context_id=session.context_id,
            )
            return resp, (time.monotonic() - t0) * 1000

        try:
            if self._concurrency:
                key = self._concurrency.resolve_key(msg)
                async with self._concurrency.acquire(key):
                    return await _do_call()
            else:
                return await _do_call()
        except Exception:
            a2a_ms = 0.0
            logger.exception(
                "A2A call failed for session %s",
                session_key,
                extra={
                    **log_extra,
                    "a2a_duration_ms": round(a2a_ms, 1),
                },
            )
            if self._health:
                self._health.record_error(msg.channel, "a2a_call_failed")
            adapter = self.channels.get(msg.channel)
            if adapter:
                await adapter.send(
                    OutboundMessage(
                        channel=msg.channel,
                        recipient_id=msg.sender_id,
                        text="Sorry, I couldn't process your message right now.",
                        thread_id=msg.thread_id,
                        conversation_id=msg.conversation_id,
                    )
                )
            return None
