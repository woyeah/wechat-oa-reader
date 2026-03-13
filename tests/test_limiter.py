# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import time

import pytest

from wechat_oa_reader.limiter import RateLimiter


@pytest.mark.asyncio
async def test_limiter_allows_requests() -> None:
    limiter = RateLimiter(requests_per_minute=10, article_fetch_interval=0.01)
    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_limiter_article_interval() -> None:
    limiter = RateLimiter(requests_per_minute=100, article_fetch_interval=0.2)
    await limiter.acquire_article()
    start = time.monotonic()
    await limiter.acquire_article()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.19


def test_limiter_default_config() -> None:
    limiter = RateLimiter()
    assert limiter._limit == 10
    assert limiter._article_interval == 3.0


def test_limiter_custom_config() -> None:
    limiter = RateLimiter(requests_per_minute=20, article_fetch_interval=1.5)
    assert limiter._limit == 20
    assert limiter._article_interval == 1.5
