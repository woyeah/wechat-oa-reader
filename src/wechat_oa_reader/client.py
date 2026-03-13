# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
from typing import Any

import httpx

from .fetcher import Fetcher
from .limiter import RateLimiter
from .models import Account, ArticleContent, ArticleList, ArticleSummary, Credentials, RateLimitConfig
from .parser import extract_article_info, process_article_content
from .proxy import ProxyPool


class WeChatClient:
    def __init__(
        self,
        token: str | None = None,
        cookie: str | None = None,
        proxies: list[str] | None = None,
        rate_limit: RateLimitConfig | None = None,
    ):
        self._token = token
        self._cookie = cookie
        proxy_pool = ProxyPool(proxies) if proxies else None
        limiter_cfg = rate_limit or RateLimitConfig()
        self._rate_limiter = RateLimiter(
            limiter_cfg.requests_per_minute,
            limiter_cfg.article_fetch_interval,
        )
        self._fetcher = Fetcher(proxy_pool=proxy_pool, rate_limiter=self._rate_limiter)

    @classmethod
    async def from_credentials(cls, creds: Credentials, **kwargs: Any) -> WeChatClient:
        return cls(token=creds.token, cookie=creds.cookie, **kwargs)

    def _make_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Cookie": self._cookie or "",
        }

    async def search_accounts(self, query: str, count: int = 5) -> list[Account]:
        self._require_auth()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://mp.weixin.qq.com/cgi-bin/searchbiz",
                params={
                    "action": "search_biz",
                    "token": self._token,
                    "lang": "zh_CN",
                    "f": "json",
                    "ajax": 1,
                    "query": query,
                    "begin": 0,
                    "count": count,
                },
                headers=self._make_headers(),
            )
            response.raise_for_status()
            result = response.json()

        if result.get("base_resp", {}).get("ret") != 0:
            return []

        return [
            Account(
                fakeid=item.get("fakeid", ""),
                nickname=item.get("nickname", ""),
                alias=item.get("alias") or None,
                head_img=item.get("round_head_img") or None,
                service_type=item.get("service_type"),
            )
            for item in result.get("list", [])
        ]

    async def get_articles(
        self,
        fakeid: str,
        count: int = 10,
        offset: int = 0,
        keyword: str | None = None,
    ) -> ArticleList:
        self._require_auth()

        params = {
            "sub": "search" if keyword else "list",
            "search_field": "7" if keyword else "null",
            "begin": offset,
            "count": count,
            "query": keyword or "",
            "fakeid": fakeid,
            "type": "101_1",
            "free_publish_type": 1,
            "sub_action": "list_ex",
            "token": self._token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://mp.weixin.qq.com/cgi-bin/appmsgpublish",
                params=params,
                headers=self._make_headers(),
            )
            response.raise_for_status()
            result = response.json()

        if result.get("base_resp", {}).get("ret") != 0:
            return ArticleList(items=[], total=0, offset=offset)

        publish_page = result.get("publish_page", {})
        if isinstance(publish_page, str):
            try:
                publish_page = json.loads(publish_page)
            except json.JSONDecodeError:
                publish_page = {}

        items: list[ArticleSummary] = []
        for publish_item in publish_page.get("publish_list", []):
            publish_info = publish_item.get("publish_info", {})
            if isinstance(publish_info, str):
                try:
                    publish_info = json.loads(publish_info)
                except json.JSONDecodeError:
                    continue
            for article in publish_info.get("appmsgex", []):
                items.append(
                    ArticleSummary(
                        aid=article.get("aid", ""),
                        title=article.get("title", ""),
                        link=article.get("link", ""),
                        digest=article.get("digest") or None,
                        cover=article.get("cover") or None,
                        author=article.get("author") or None,
                        update_time=article.get("update_time", 0),
                        create_time=article.get("create_time", 0),
                    )
                )

        return ArticleList(items=items, total=publish_page.get("total_count", len(items)), offset=offset)

    async def fetch_article(self, url: str, timeout: int = 60) -> ArticleContent | None:
        html = await self._fetcher.fetch_article(
            article_url=url,
            timeout=timeout,
            wechat_token=self._token,
            wechat_cookie=self._cookie,
        )
        if not html:
            return None

        processed = process_article_content(html)
        info = extract_article_info(html)
        return ArticleContent(
            url=url,
            title=info.get("title") or None,
            author=info.get("author") or None,
            publish_time=info.get("publish_time", 0),
            html=processed["html"],
            plain_text=processed["plain_text"],
            images=processed["images"],
        )

    async def fetch_articles(
        self,
        urls: list[str],
        max_concurrency: int = 5,
        timeout: int = 60,
    ) -> list[ArticleContent]:
        batch = await self._fetcher.fetch_articles_batch(
            article_urls=urls,
            max_concurrency=max_concurrency,
            timeout=timeout,
            wechat_token=self._token,
            wechat_cookie=self._cookie,
        )

        result: list[ArticleContent] = []
        for url, html in batch.items():
            if not html:
                continue
            processed = process_article_content(html)
            info = extract_article_info(html)
            result.append(
                ArticleContent(
                    url=url,
                    title=info.get("title") or None,
                    author=info.get("author") or None,
                    publish_time=info.get("publish_time", 0),
                    html=processed["html"],
                    plain_text=processed["plain_text"],
                    images=processed["images"],
                )
            )
        return result

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token and self._cookie)

    @property
    def credentials(self) -> Credentials | None:
        if not self.is_authenticated:
            return None
        return Credentials(token=self._token or "", cookie=self._cookie or "")

    def _require_auth(self) -> None:
        if not self.is_authenticated:
            raise RuntimeError("Client is not authenticated. Provide token and cookie.")
