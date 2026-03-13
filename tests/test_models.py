# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wechat_oa_reader.models import (
    Account,
    ArticleContent,
    ArticleList,
    ArticleSummary,
    Credentials,
    ProxyConfig,
    RateLimitConfig,
)


def test_credentials_minimal() -> None:
    creds = Credentials(token="t", cookie="c")
    assert creds.token == "t"
    assert creds.cookie == "c"
    assert creds.fakeid is None


def test_credentials_full() -> None:
    creds = Credentials(
        token="t",
        cookie="c",
        fakeid="f",
        nickname="n",
        expire_time=123,
    )
    assert creds.model_dump() == {
        "token": "t",
        "cookie": "c",
        "fakeid": "f",
        "nickname": "n",
        "expire_time": 123,
    }


def test_credentials_validation_error() -> None:
    with pytest.raises(ValidationError):
        Credentials(token="only-token")


def test_account_from_dict() -> None:
    account = Account.model_validate({"fakeid": "f", "nickname": "name"})
    assert account.fakeid == "f"
    assert account.nickname == "name"


def test_article_summary_required_fields() -> None:
    summary = ArticleSummary(aid="1", title="t", link="https://example.com")
    assert summary.aid == "1"


def test_article_summary_optional_fields() -> None:
    summary = ArticleSummary(aid="1", title="t", link="https://example.com")
    assert summary.digest is None
    assert summary.cover is None
    assert summary.author is None
    assert summary.update_time == 0
    assert summary.create_time == 0


def test_article_list_empty() -> None:
    article_list = ArticleList(items=[])
    assert article_list.total == 0
    assert article_list.offset == 0


def test_article_list_with_items() -> None:
    items = [ArticleSummary(aid="1", title="t", link="https://example.com")]
    article_list = ArticleList(items=items, total=1, offset=0)
    assert len(article_list.items) == 1
    assert article_list.total == 1


def test_article_content() -> None:
    content = ArticleContent(
        url="https://mp.weixin.qq.com/s?a=1",
        title="title",
        author="author",
        publish_time=1,
        html="<p>x</p>",
        plain_text="x",
        images=["https://mmbiz.qpic.cn/1.jpg"],
    )
    assert content.title == "title"


def test_proxy_config_defaults() -> None:
    cfg = ProxyConfig()
    assert cfg.urls == []
    assert cfg.fail_cooldown == 120


def test_rate_limit_config_defaults() -> None:
    cfg = RateLimitConfig()
    assert cfg.requests_per_minute == 10
    assert cfg.article_fetch_interval == 3.0


def test_rate_limit_config_custom() -> None:
    cfg = RateLimitConfig(requests_per_minute=20, article_fetch_interval=1.5)
    assert cfg.requests_per_minute == 20
    assert cfg.article_fetch_interval == 1.5
