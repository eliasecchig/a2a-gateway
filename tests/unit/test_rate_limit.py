from __future__ import annotations

import asyncio

import pytest

from gateway.core.rate_limit import (
    BackoffConfig,
    RateLimitConfig,
    RateLimiter,
    RetryWithBackoff,
)


@pytest.mark.asyncio
class TestRateLimiter:
    async def test_under_limit_returns_immediately(self):
        limiter = RateLimiter(RateLimitConfig(max_requests=5, window_seconds=10.0))
        await limiter.acquire()

    async def test_different_keys_independent(self):
        limiter = RateLimiter(RateLimitConfig(max_requests=1, window_seconds=10.0))
        await limiter.acquire("key_a")
        await limiter.acquire("key_b")

    async def test_at_limit_waits(self):
        limiter = RateLimiter(RateLimitConfig(max_requests=1, window_seconds=0.1))
        await limiter.acquire()
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.05


@pytest.mark.asyncio
class TestRetryWithBackoff:
    async def test_succeeds_first_try(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            return "ok"

        retry = RetryWithBackoff(BackoffConfig(max_retries=3, initial=0.01))
        result = await retry.execute(fn)
        assert result == "ok"
        assert calls == 1

    async def test_fails_then_succeeds(self):
        attempt = 0

        async def fn():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise RuntimeError("fail")
            return "ok"

        retry = RetryWithBackoff(
            BackoffConfig(max_retries=5, initial=0.01, factor=1.0),
            retryable=(RuntimeError,),
        )
        result = await retry.execute(fn)
        assert result == "ok"
        assert attempt == 3

    async def test_exceeds_max_retries_raises(self):
        async def fn():
            raise ValueError("always fails")

        retry = RetryWithBackoff(
            BackoffConfig(max_retries=2, initial=0.01),
            retryable=(ValueError,),
        )
        with pytest.raises(ValueError, match="always fails"):
            await retry.execute(fn)

    async def test_backoff_delay_grows(self):
        attempt = 0

        async def fn():
            nonlocal attempt
            attempt += 1
            if attempt < 4:
                raise RuntimeError("fail")
            return "done"

        config = BackoffConfig(initial=0.01, factor=2.0, max_retries=5, jitter_pct=0.0)
        retry = RetryWithBackoff(config, retryable=(RuntimeError,))
        result = await retry.execute(fn)
        assert result == "done"


@pytest.mark.asyncio
class TestRetryWithBackoffStream:
    async def test_stream_succeeds_first_try(self):
        async def gen():
            yield 1
            yield 2

        retry = RetryWithBackoff(BackoffConfig(max_retries=3, initial=0.01))
        items = [x async for x in retry.execute_stream(gen)]
        assert items == [1, 2]

    async def test_stream_retries_on_failure(self):
        attempt = 0

        async def gen():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError("refused")
            yield "ok"

        retry = RetryWithBackoff(
            BackoffConfig(max_retries=5, initial=0.01, factor=1.0),
            retryable=(ConnectionError,),
        )
        items = [x async for x in retry.execute_stream(gen)]
        assert items == ["ok"]
        assert attempt == 3

    async def test_stream_exceeds_max_retries(self):
        async def gen():
            raise ConnectionError("down")
            yield

        retry = RetryWithBackoff(
            BackoffConfig(max_retries=2, initial=0.01),
            retryable=(ConnectionError,),
        )
        with pytest.raises(ConnectionError, match="down"):
            async for _ in retry.execute_stream(gen):
                pass

    async def test_stream_no_retry_on_non_retryable(self):
        attempt = 0

        async def gen():
            nonlocal attempt
            attempt += 1
            raise ValueError("bad")
            yield

        retry = RetryWithBackoff(
            BackoffConfig(max_retries=3, initial=0.01),
            retryable=(ConnectionError,),
        )
        with pytest.raises(ValueError, match="bad"):
            async for _ in retry.execute_stream(gen):
                pass
        assert attempt == 1
