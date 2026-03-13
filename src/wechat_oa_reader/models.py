# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    token: str
    cookie: str
    fakeid: str | None = None
    nickname: str | None = None
    expire_time: int | None = None


class Account(BaseModel):
    fakeid: str
    nickname: str
    alias: str | None = None
    head_img: str | None = None
    service_type: int | None = None


class ArticleSummary(BaseModel):
    aid: str
    title: str
    link: str
    digest: str | None = None
    cover: str | None = None
    author: str | None = None
    update_time: int = 0
    create_time: int = 0


class ArticleList(BaseModel):
    items: list[ArticleSummary]
    total: int = 0
    offset: int = 0


class ArticleContent(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    publish_time: int = 0
    html: str
    plain_text: str
    images: list[str]


class ProxyConfig(BaseModel):
    urls: list[str] = Field(default_factory=list)
    fail_cooldown: int = 120


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 10
    article_fetch_interval: float = 3.0
