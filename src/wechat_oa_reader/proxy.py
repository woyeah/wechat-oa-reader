# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import threading
import time
import urllib.parse


class ProxyPool:
    def __init__(self, proxies: list[str] | None = None, fail_cooldown: int = 120):
        self._proxies = list(proxies or [])
        if self._proxies:
            for proxy in self._proxies:
                scheme = urllib.parse.urlparse(proxy).scheme.lower()
                if not scheme:
                    raise ValueError(
                        f"Invalid proxy URL (no scheme): {proxy}. Allowed: http, https, socks5, socks5h"
                    )
                if scheme not in ("http", "https", "socks5", "socks5h"):
                    raise ValueError(
                        f"Invalid proxy scheme '{scheme}' in: {proxy}. Allowed: http, https, socks5, socks5h"
                    )
        self._index = 0
        self._fail_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self._fail_cooldown = fail_cooldown

    @property
    def enabled(self) -> bool:
        return bool(self._proxies)

    @property
    def count(self) -> int:
        return len(self._proxies)

    def next(self) -> str | None:
        if not self._proxies:
            return None

        now = time.time()
        with self._lock:
            for _ in range(len(self._proxies)):
                proxy = self._proxies[self._index % len(self._proxies)]
                self._index += 1
                if self._fail_until.get(proxy, 0) <= now:
                    return proxy
        return None

    def get_all(self) -> list[str]:
        return list(self._proxies)

    def mark_failed(self, proxy: str) -> None:
        with self._lock:
            self._fail_until[proxy] = time.time() + self._fail_cooldown

    def mark_ok(self, proxy: str) -> None:
        with self._lock:
            self._fail_until.pop(proxy, None)

    def get_status(self) -> dict:
        now = time.time()
        healthy: list[str] = []
        failed: list[str] = []
        for proxy in self._proxies:
            if self._fail_until.get(proxy, 0) > now:
                failed.append(proxy)
            else:
                healthy.append(proxy)
        return {
            "enabled": self.enabled,
            "total": self.count,
            "healthy": len(healthy),
            "failed": len(failed),
            "failed_proxies": failed,
        }
