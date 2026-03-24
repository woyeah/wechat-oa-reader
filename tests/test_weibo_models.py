# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from wechat_oa_reader.models import (
    WeiboArticle,
    WeiboComment,
    WeiboCommentList,
    WeiboPost,
    WeiboPostList,
    WeiboUser,
)


def test_weibo_user_minimal() -> None:
    user = WeiboUser(uid="u1", nickname="alice")
    assert user.uid == "u1"
    assert user.nickname == "alice"


def test_weibo_user_full() -> None:
    user = WeiboUser(
        uid="u1",
        nickname="alice",
        avatar="https://example.com/avatar.jpg",
        description="bio",
        followers_count=100,
        following_count=50,
        verified=True,
        verified_reason="official",
    )
    assert user.model_dump() == {
        "uid": "u1",
        "nickname": "alice",
        "avatar": "https://example.com/avatar.jpg",
        "description": "bio",
        "followers_count": 100,
        "following_count": 50,
        "verified": True,
        "verified_reason": "official",
    }


def test_weibo_user_defaults() -> None:
    user = WeiboUser(uid="u1", nickname="alice")
    assert user.avatar is None
    assert user.description is None
    assert user.followers_count is None
    assert user.following_count is None
    assert user.verified is False
    assert user.verified_reason is None


def test_weibo_post_minimal() -> None:
    created_at = datetime(2024, 1, 1, 8, 0, 0)
    post = WeiboPost(
        bid="b1",
        mid="m1",
        uid="u1",
        text="hello",
        created_at=created_at,
    )
    assert post.bid == "b1"
    assert post.mid == "m1"
    assert post.uid == "u1"
    assert post.text == "hello"
    assert post.created_at == created_at


def test_weibo_post_full() -> None:
    created_at = datetime(2024, 1, 1, 8, 0, 0)
    repost = WeiboPost(
        bid="b0",
        mid="m0",
        uid="u0",
        text="original",
        created_at=datetime(2023, 12, 31, 22, 0, 0),
    )
    post = WeiboPost(
        bid="b1",
        mid="m1",
        uid="u1",
        text="full text",
        html="<p>full text</p>",
        images=["https://example.com/1.jpg", "https://example.com/2.jpg"],
        video_url="https://example.com/video.mp4",
        repost=repost,
        is_long_text=True,
        created_at=created_at,
        likes_count=10,
        reposts_count=3,
        comments_count=5,
    )
    assert post.model_dump() == {
        "bid": "b1",
        "mid": "m1",
        "uid": "u1",
        "text": "full text",
        "html": "<p>full text</p>",
        "images": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
        "video_url": "https://example.com/video.mp4",
        "repost": {
            "bid": "b0",
            "mid": "m0",
            "uid": "u0",
            "text": "original",
            "html": None,
            "images": [],
            "video_url": None,
            "repost": None,
            "is_long_text": False,
            "created_at": datetime(2023, 12, 31, 22, 0, 0),
            "likes_count": 0,
            "reposts_count": 0,
            "comments_count": 0,
        },
        "is_long_text": True,
        "created_at": created_at,
        "likes_count": 10,
        "reposts_count": 3,
        "comments_count": 5,
    }


def test_weibo_post_repost() -> None:
    repost = WeiboPost(
        bid="b0",
        mid="m0",
        uid="u0",
        text="source",
        created_at=datetime(2024, 1, 1, 7, 0, 0),
    )
    post = WeiboPost(
        bid="b1",
        mid="m1",
        uid="u1",
        text="forward",
        repost=repost,
        created_at=datetime(2024, 1, 1, 8, 0, 0),
    )
    assert post.repost is not None
    assert post.repost.bid == "b0"
    assert post.repost.text == "source"


def test_weibo_post_defaults() -> None:
    post = WeiboPost(
        bid="b1",
        mid="m1",
        uid="u1",
        text="hello",
        created_at=datetime(2024, 1, 1, 8, 0, 0),
    )
    assert post.html is None
    assert post.images == []
    assert post.video_url is None
    assert post.repost is None
    assert post.is_long_text is False
    assert post.likes_count == 0
    assert post.reposts_count == 0
    assert post.comments_count == 0


def test_weibo_post_list() -> None:
    items = [
        WeiboPost(
            bid="b1",
            mid="m1",
            uid="u1",
            text="p1",
            created_at=datetime(2024, 1, 1, 8, 0, 0),
        ),
        WeiboPost(
            bid="b2",
            mid="m2",
            uid="u2",
            text="p2",
            created_at=datetime(2024, 1, 1, 9, 0, 0),
        ),
    ]
    post_list = WeiboPostList(items=items, total=2, since_id="sid_2")
    assert len(post_list.items) == 2
    assert post_list.total == 2
    assert post_list.since_id == "sid_2"


def test_weibo_post_list_empty() -> None:
    post_list = WeiboPostList()
    assert post_list.items == []
    assert post_list.total is None
    assert post_list.since_id is None


def test_weibo_comment_minimal() -> None:
    created_at = datetime(2024, 1, 1, 10, 0, 0)
    comment = WeiboComment(
        id="c1",
        uid="u1",
        nickname="alice",
        text="nice",
        created_at=created_at,
    )
    assert comment.id == "c1"
    assert comment.uid == "u1"
    assert comment.nickname == "alice"
    assert comment.text == "nice"
    assert comment.created_at == created_at
    assert comment.likes_count == 0


def test_weibo_comment_list() -> None:
    items = [
        WeiboComment(
            id="c1",
            uid="u1",
            nickname="alice",
            text="nice",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            likes_count=1,
        ),
        WeiboComment(
            id="c2",
            uid="u2",
            nickname="bob",
            text="great",
            created_at=datetime(2024, 1, 1, 10, 5, 0),
            likes_count=2,
        ),
    ]
    comment_list = WeiboCommentList(items=items, total=2, max_id="max_2")
    assert len(comment_list.items) == 2
    assert comment_list.total == 2
    assert comment_list.max_id == "max_2"


def test_weibo_comment_list_empty() -> None:
    comment_list = WeiboCommentList()
    assert comment_list.items == []
    assert comment_list.total is None
    assert comment_list.max_id is None


def test_weibo_user_missing_required() -> None:
    with pytest.raises(ValidationError):
        WeiboUser(uid="u1")


def test_weibo_post_missing_required() -> None:
    with pytest.raises(ValidationError):
        WeiboPost(bid="b1", mid="m1")


def test_weibo_post_validate_from_dict() -> None:
    data = {
        "bid": "b100",
        "mid": "m100",
        "uid": "u100",
        "text": "api post",
        "html": "<p>api post</p>",
        "images": ["https://example.com/i1.jpg"],
        "video_url": None,
        "repost": {
            "bid": "b99",
            "mid": "m99",
            "uid": "u99",
            "text": "root",
            "created_at": "2024-01-01T07:00:00",
        },
        "is_long_text": False,
        "created_at": "2024-01-01T08:00:00",
        "likes_count": 12,
        "reposts_count": 4,
        "comments_count": 6,
    }
    post = WeiboPost.model_validate(data)
    assert post.bid == "b100"
    assert post.created_at == datetime(2024, 1, 1, 8, 0, 0)
    assert post.repost is not None
    assert post.repost.bid == "b99"
    assert post.repost.created_at == datetime(2024, 1, 1, 7, 0, 0)


def test_weibo_article_minimal() -> None:
    article = WeiboArticle(article_id="123", title="Test", body="<p>hi</p>", plain_text="hi")
    assert article.article_id == "123"
    assert article.title == "Test"
    assert article.body == "<p>hi</p>"
    assert article.plain_text == "hi"
    assert article.cover_img is None


def test_weibo_article_full() -> None:
    article = WeiboArticle(
        article_id="123",
        title="Test",
        body="<p>hi</p>",
        plain_text="hi",
        cover_img="https://example.com/cover.jpg",
        created_at="2024-01-01",
        uid="999",
    )
    assert article.cover_img == "https://example.com/cover.jpg"
    assert article.uid == "999"
