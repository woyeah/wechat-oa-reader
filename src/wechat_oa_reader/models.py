# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


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


class WeiboUser(BaseModel):
    uid: str
    nickname: str
    avatar: str | None = None
    description: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    verified: bool = False
    verified_reason: str | None = None


class WeiboPost(BaseModel):
    bid: str
    mid: str
    uid: str
    text: str
    html: str | None = None
    images: list[str] = Field(default_factory=list)
    video_url: str | None = None
    article_url: str | None = None
    repost: WeiboPost | None = None
    is_long_text: bool = False
    created_at: datetime
    likes_count: int = 0
    reposts_count: int = 0
    comments_count: int = 0


class WeiboPostList(BaseModel):
    items: list[WeiboPost] = Field(default_factory=list)
    total: int | None = None
    since_id: str | None = None


class WeiboComment(BaseModel):
    id: str
    uid: str
    nickname: str
    text: str
    created_at: datetime
    likes_count: int = 0


class WeiboCommentList(BaseModel):
    items: list[WeiboComment] = Field(default_factory=list)
    total: int | None = None
    max_id: str | None = None


class WeiboArticle(BaseModel):
    article_id: str
    title: str
    body: str  # HTML content
    plain_text: str  # stripped HTML
    cover_img: str | None = None
    created_at: str | None = None
    uid: str | None = None


class WeComUser(BaseModel):
    userid: str
    name: str
    department: str | None = None
    avatar: str | None = None


class WeComMessage(BaseModel):
    msg_id: str
    msg_type: str
    from_user: str
    to_user: str
    content: str
    create_time: int
    direction: Literal["sent", "received"]
