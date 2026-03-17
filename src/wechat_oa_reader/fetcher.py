# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from .limiter import RateLimiter
from .proxy import ProxyPool

try:
    from curl_cffi.requests import Session as CurlSession

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _fetch_curl_cffi_sync(url: str, headers: dict[str, str], timeout: int, proxy: str | None, verify: bool) -> str:
    kwargs: dict[str, Any] = {"timeout": timeout, "allow_redirects": True, "verify": verify}
    if proxy:
        kwargs["proxy"] = proxy
    with CurlSession(impersonate="chrome120") as session:
        resp = session.get(url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.text


class Fetcher:
    def __init__(
        self,
        proxy_pool: ProxyPool | None = None,
        rate_limiter: RateLimiter | None = None,
        verify_ssl: bool = True,
    ):
        self._proxy_pool = proxy_pool
        self._rate_limiter = rate_limiter
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._verify_ssl = verify_ssl
        if not verify_ssl:
            warnings.warn(
                "SSL verification is disabled — connections are vulnerable to MITM attacks",
                stacklevel=2,
            )

    async def fetch_page(self, url: str, extra_headers: dict[str, str] | None = None, timeout: int = 30) -> str:
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        headers = {**BROWSER_HEADERS, **(extra_headers or {})}
        if self._proxy_pool and self._proxy_pool.enabled:
            tried: list[str] = []
            retries = min(3, self._proxy_pool.count)
            for _ in range(retries):
                proxy = self._proxy_pool.next()
                if proxy is None or proxy in tried:
                    break
                tried.append(proxy)
                try:
                    content = await self._do_fetch(url, headers, timeout, proxy)
                    self._proxy_pool.mark_ok(proxy)
                    return content
                except (httpx.HTTPError, httpx.StreamError, OSError, TimeoutError):
                    self._proxy_pool.mark_failed(proxy)

        return await self._do_fetch(url, headers, timeout, None)

    async def fetch_article(
        self,
        article_url: str,
        timeout: int = 60,
        wechat_token: str | None = None,
        wechat_cookie: str | None = None,
    ) -> str | None:
        full_url = article_url
        if wechat_token and "token=" not in article_url:
            separator = "&" if "?" in article_url else "?"
            full_url = f"{article_url}{separator}token={wechat_token}"

        extra_headers = {"Referer": "https://mp.weixin.qq.com/"}
        if wechat_cookie:
            extra_headers["Cookie"] = wechat_cookie

        try:
            if self._rate_limiter:
                await self._rate_limiter.acquire_article()

            headers = {**BROWSER_HEADERS, **extra_headers}

            # Use proxy rotation directly (skip fetch_page to avoid double rate-limiting)
            if self._proxy_pool and self._proxy_pool.enabled:
                tried: list[str] = []
                retries = min(3, self._proxy_pool.count)
                for _ in range(retries):
                    proxy = self._proxy_pool.next()
                    if proxy is None or proxy in tried:
                        break
                    tried.append(proxy)
                    try:
                        html = await self._do_fetch(full_url, headers, timeout, proxy)
                        self._proxy_pool.mark_ok(proxy)
                        if "js_content" not in html:
                            return None
                        return html
                    except (httpx.HTTPError, httpx.StreamError, OSError, TimeoutError):
                        self._proxy_pool.mark_failed(proxy)

            html = await self._do_fetch(full_url, headers, timeout, None)
            if "js_content" not in html:
                return None
            return html
        except (httpx.HTTPError, httpx.StreamError, OSError, TimeoutError):
            return None

    async def fetch_articles_batch(
        self,
        article_urls: list[str],
        max_concurrency: int = 5,
        timeout: int = 60,
        wechat_token: str | None = None,
        wechat_cookie: str | None = None,
    ) -> dict[str, str | None]:
        semaphore = asyncio.Semaphore(max_concurrency)
        results: dict[str, str | None] = {}

        async def fetch_one(url: str) -> None:
            async with semaphore:
                results[url] = await self.fetch_article(
                    url,
                    timeout=timeout,
                    wechat_token=wechat_token,
                    wechat_cookie=wechat_cookie,
                )

        await asyncio.gather(*(fetch_one(url) for url in article_urls), return_exceptions=True)
        return results

    async def _do_fetch(self, url: str, headers: dict[str, str], timeout: int, proxy: str | None) -> str:
        if HAS_CURL_CFFI:
            return await self._fetch_curl_cffi(url, headers, timeout, proxy)
        return await self._fetch_httpx(url, headers, timeout, proxy)

    async def _fetch_curl_cffi(self, url: str, headers: dict[str, str], timeout: int, proxy: str | None) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            _fetch_curl_cffi_sync,
            url,
            headers,
            timeout,
            proxy,
            self._verify_ssl,
        )

    async def _fetch_httpx(self, url: str, headers: dict[str, str], timeout: int, proxy: str | None) -> str:
        client_kwargs: dict[str, Any] = {"timeout": float(timeout), "follow_redirects": True}
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
