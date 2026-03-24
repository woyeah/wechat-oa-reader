# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from .fetcher import Fetcher
from .limiter import RateLimiter
from .models import (
    RateLimitConfig,
    WeiboComment,
    WeiboCommentList,
    WeiboPost,
    WeiboPostList,
    WeiboUser,
)
from .proxy import ProxyPool


class WeiboClient:
    _BASE_URL = "https://m.weibo.cn"
    _DATETIME_FMT = "%a %b %d %H:%M:%S %z %Y"

    def __init__(
        self,
        cookie: str,
        proxies: list[str] | None = None,
        rate_limit: RateLimitConfig | None = None,
    ):
        self._cookie = cookie
        self._proxy_pool = ProxyPool(proxies) if proxies else None
        limiter_cfg = rate_limit or RateLimitConfig()
        self._rate_limiter = RateLimiter(
            limiter_cfg.requests_per_minute,
            limiter_cfg.article_fetch_interval,
        )
        self._fetcher = Fetcher(proxy_pool=self._proxy_pool, rate_limiter=self._rate_limiter)
        self._weibo_container_ids: dict[str, str] = {}

    @property
    def is_authenticated(self) -> bool:
        return bool(self._cookie)

    async def _request(self, path: str, *, params: dict | None = None) -> dict:
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            "Referer": "https://m.weibo.cn/",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": self._cookie,
        }

        url = f"{self._BASE_URL}{path}"
        request_kwargs: dict[str, Any] = {
            "params": params,
            "headers": headers,
        }

        proxy = self._proxy_pool.next() if self._proxy_pool and self._proxy_pool.enabled else None
        if proxy:
            request_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, **request_kwargs)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        if proxy and self._proxy_pool:
            self._proxy_pool.mark_ok(proxy)
        return data

    async def check_auth(self) -> bool:
        data = await self._request("/api/config")
        return bool(data.get("data", {}).get("login"))

    async def get_user(self, uid: str) -> WeiboUser:
        data = await self._request(
            "/api/container/getIndex",
            params={"type": "uid", "value": uid},
        )

        payload = data.get("data", {})
        user_info = payload.get("userInfo", {})
        container_id = self._extract_weibo_containerid(payload)
        if container_id:
            self._weibo_container_ids[str(uid)] = container_id

        return self._parse_user(user_info)

    async def get_posts(
        self,
        uid: str,
        since_id: str | None = None,
        count: int = 20,
    ) -> WeiboPostList:
        container_id = self._weibo_container_ids.get(str(uid))
        if not container_id:
            await self.get_user(uid)
            container_id = self._weibo_container_ids.get(str(uid))

        params: dict[str, Any] = {
            "containerid": container_id or "",
            "count": count,
        }
        if since_id is not None:
            params["since_id"] = since_id

        data = await self._request("/api/container/getIndex", params=params)
        payload = data.get("data", {})
        cards = payload.get("cards", [])
        items = [
            self._parse_post(card.get("mblog", {}))
            for card in cards
            if card.get("card_type") == 9 and card.get("mblog")
        ]

        cardlist_info = payload.get("cardlistInfo", {})
        return WeiboPostList(
            items=items,
            total=cardlist_info.get("total"),
            since_id=cardlist_info.get("since_id"),
        )

    async def fetch_post(self, bid: str) -> WeiboPost:
        data = await self._request("/statuses/show", params={"id": bid})
        mblog = data.get("data", {})
        post = self._parse_post(mblog)

        if post.is_long_text:
            long_text = await self._request("/statuses/longtext", params={"id": post.mid})
            long_text_content = long_text.get("data", {}).get("longTextContent")
            if isinstance(long_text_content, str) and long_text_content:
                post.text = long_text_content
                post.html = long_text_content

        return post

    async def get_comments(
        self,
        post_id: str,
        max_id: str | None = None,
        count: int = 20,
    ) -> WeiboCommentList:
        params: dict[str, Any] = {
            "id": post_id,
            "count": count,
        }
        if max_id is not None:
            params["max_id"] = max_id

        data = await self._request("/api/comments/show", params=params)
        payload = data.get("data", {})
        items = [self._parse_comment(item) for item in payload.get("data", [])]

        return WeiboCommentList(
            items=items,
            total=payload.get("total_number"),
            max_id=payload.get("max_id"),
        )

    async def search_users(self, query: str) -> list[WeiboUser]:
        data = await self._request(
            "/api/container/getIndex",
            params={"containerid": f"100103type=3&q={query}"},
        )

        payload = data.get("data", {})
        users: list[WeiboUser] = []
        for card in payload.get("cards", []):
            if card.get("card_type") != 11:
                continue
            for sub_card in card.get("card_group", []):
                if sub_card.get("card_type") != 10:
                    continue
                user_info = sub_card.get("user")
                if user_info:
                    users.append(self._parse_user(user_info))
        return users

    @classmethod
    def _parse_datetime(cls, value: str) -> datetime:
        return datetime.strptime(value, cls._DATETIME_FMT)

    @staticmethod
    def _parse_user(user_info: dict[str, Any]) -> WeiboUser:
        verified_reason = user_info.get("verified_reason")
        return WeiboUser(
            uid=str(user_info.get("id", "")),
            nickname=user_info.get("screen_name", ""),
            avatar=user_info.get("avatar_large") or None,
            description=user_info.get("description") or None,
            followers_count=user_info.get("followers_count"),
            following_count=user_info.get("follow_count"),
            verified=bool(user_info.get("verified")),
            verified_reason=verified_reason or None,
        )

    @classmethod
    def _parse_post(cls, mblog: dict[str, Any]) -> WeiboPost:
        pics = mblog.get("pics") or []
        images = [
            pic.get("large", {}).get("url")
            for pic in pics
            if isinstance(pic, dict) and pic.get("large", {}).get("url")
        ]

        page_urls = (mblog.get("page_info") or {}).get("urls") or {}
        video_url = (
            page_urls.get("mp4_720p_mp4")
            or page_urls.get("mp4_hd_url")
            or page_urls.get("mp4_sd_url")
            or page_urls.get("stream_url")
            or page_urls.get("url")
        )

        repost_data = mblog.get("retweeted_status")
        repost = cls._parse_post(repost_data) if isinstance(repost_data, dict) and repost_data else None

        text = mblog.get("text", "")
        mid = str(mblog.get("mid", ""))
        return WeiboPost(
            bid=mblog.get("bid", ""),
            mid=mid,
            uid=str((mblog.get("user") or {}).get("id", "")),
            text=text,
            html=text,
            images=images,
            video_url=video_url,
            repost=repost,
            is_long_text=bool(mblog.get("isLongText")),
            created_at=cls._parse_datetime(mblog.get("created_at", "")),
            likes_count=mblog.get("attitudes_count", 0),
            reposts_count=mblog.get("reposts_count", 0),
            comments_count=mblog.get("comments_count", 0),
        )

    @classmethod
    def _parse_comment(cls, item: dict[str, Any]) -> WeiboComment:
        user = item.get("user", {})
        return WeiboComment(
            id=str(item.get("id", "")),
            uid=str(user.get("id", "")),
            nickname=user.get("screen_name", ""),
            text=item.get("text", ""),
            created_at=cls._parse_datetime(item.get("created_at", "")),
            likes_count=item.get("like_count", 0),
        )

    @staticmethod
    def _extract_weibo_containerid(payload: dict[str, Any]) -> str | None:
        tabs = payload.get("tabsInfo", {}).get("tabs", [])
        for tab in tabs:
            if tab.get("tabKey") == "weibo":
                container_id = tab.get("containerid")
                if container_id:
                    return str(container_id)
        return None
