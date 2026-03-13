# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, article_fetch_interval: float = 3.0):
        self._window = 60.0
        self._limit = requests_per_minute
        self._article_interval = article_fetch_interval
        self._requests: deque[float] = deque()
        self._last_article: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.time()
                while self._requests and now - self._requests[0] > self._window:
                    self._requests.popleft()
                if len(self._requests) < self._limit:
                    self._requests.append(time.time())
                    return
                sleep_time = self._window - (now - self._requests[0]) + 0.01
            await asyncio.sleep(sleep_time)

    async def acquire_article(self) -> None:
        await self.acquire()
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_article
            if elapsed < self._article_interval:
                wait = self._article_interval - elapsed
            else:
                wait = 0.0
            self._last_article = time.time()
        if wait > 0:
            await asyncio.sleep(wait)
