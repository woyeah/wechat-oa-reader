# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from wechat_oa_reader.fetcher import Fetcher
from wechat_oa_reader.models import WeiboCommentList, WeiboPost, WeiboPostList, WeiboUser
from wechat_oa_reader.weibo import WeiboClient


def _config_payload(login: bool) -> dict:
    return {"ok": 1, "data": {"login": login, "uid": "1234567890"}}


def _user_payload() -> dict:
    return {
        "ok": 1,
        "data": {
            "userInfo": {
                "id": 1234567890,
                "screen_name": "test_user",
                "avatar_large": "https://example.com/avatar.jpg",
                "description": "bio text",
                "followers_count": 1000,
                "follow_count": 500,
                "verified": True,
                "verified_reason": "official",
            },
            "tabsInfo": {
                "tabs": [
                    {"tabKey": "weibo", "containerid": "1076031234567890"},
                ]
            },
        },
    }


def _posts_payload() -> dict:
    return {
        "ok": 1,
        "data": {
            "cardlistInfo": {"since_id": "next_cursor", "total": 100},
            "cards": [
                {
                    "card_type": 9,
                    "mblog": {
                        "bid": "abc123",
                        "mid": "5000000000001",
                        "user": {"id": 1234567890},
                        "text": "<p>Hello world</p>",
                        "pics": [{"large": {"url": "https://example.com/pic1.jpg"}}],
                        "page_info": {"urls": {"mp4_720p_mp4": "https://example.com/video.mp4"}},
                        "retweeted_status": None,
                        "isLongText": False,
                        "created_at": "Mon Jan 01 08:00:00 +0800 2024",
                        "attitudes_count": 10,
                        "reposts_count": 3,
                        "comments_count": 5,
                    },
                }
            ],
        },
    }


def _single_post_payload(is_long_text: bool = False) -> dict:
    return {
        "ok": 1,
        "data": {
            "bid": "abc123",
            "mid": "5000000000001",
            "user": {"id": 1234567890},
            "text": "<p>Full content here</p>",
            "pics": [],
            "isLongText": is_long_text,
            "created_at": "Mon Jan 01 08:00:00 +0800 2024",
            "attitudes_count": 20,
            "reposts_count": 5,
            "comments_count": 8,
        },
    }


def _long_text_payload() -> dict:
    return {
        "ok": 1,
        "data": {
            "longTextContent": "<p>This is the full expanded long text content...</p>",
        },
    }


def _comments_payload() -> dict:
    return {
        "ok": 1,
        "data": {
            "data": [
                {
                    "id": "c001",
                    "user": {"id": 9999, "screen_name": "commenter1"},
                    "text": "Nice post!",
                    "created_at": "Mon Jan 01 09:00:00 +0800 2024",
                    "like_count": 3,
                }
            ],
            "max_id": "max_cursor_123",
            "total_number": 50,
        },
    }


def _search_payload(use_string_counts: bool = False) -> dict:
    followers_count: int | str = 200
    follow_count: int | str = 100
    if use_string_counts:
        followers_count = "1.58万"
        follow_count = "320.5万"

    return {
        "ok": 1,
        "data": {
            "cards": [
                {
                    "card_type": 11,
                    "card_group": [
                        {
                            "card_type": 10,
                            "user": {
                                "id": 1111,
                                "screen_name": "found_user",
                                "avatar_large": "https://example.com/a.jpg",
                                "description": "desc",
                                "followers_count": followers_count,
                                "follow_count": follow_count,
                                "verified": False,
                                "verified_reason": "",
                            },
                        }
                    ],
                }
            ]
        },
    }


def test_weibo_client_init() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    assert client._cookie == "SUB=abc123"
    assert isinstance(client._fetcher, Fetcher)


def test_weibo_client_is_authenticated() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    assert client.is_authenticated is True


def test_weibo_client_not_authenticated() -> None:
    client = WeiboClient(cookie="")

    assert client.is_authenticated is False


@pytest.mark.asyncio
async def test_weibo_client_check_auth_success() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_config_payload(True))) as mock_request:
        ok = await client.check_auth()

    assert ok is True
    mock_request.assert_awaited_once_with("/api/config")


@pytest.mark.asyncio
async def test_weibo_client_check_auth_failure() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_config_payload(False))) as mock_request:
        ok = await client.check_auth()

    assert ok is False
    mock_request.assert_awaited_once_with("/api/config")


@pytest.mark.asyncio
async def test_weibo_client_get_user() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_user_payload())):
        user = await client.get_user("1234567890")

    assert isinstance(user, WeiboUser)
    assert user.uid == "1234567890"
    assert user.nickname == "test_user"
    assert user.avatar == "https://example.com/avatar.jpg"
    assert user.description == "bio text"
    assert user.followers_count == 1000
    assert user.following_count == 500
    assert user.verified is True
    assert user.verified_reason == "official"


@pytest.mark.asyncio
async def test_weibo_client_get_posts() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(
        client,
        "_request",
        new=AsyncMock(side_effect=[_user_payload(), _posts_payload()]),
    ):
        post_list = await client.get_posts("1234567890")

    assert isinstance(post_list, WeiboPostList)
    assert post_list.total == 100
    assert post_list.since_id == "next_cursor"
    assert len(post_list.items) == 1

    post = post_list.items[0]
    assert isinstance(post, WeiboPost)
    assert post.bid == "abc123"
    assert post.mid == "5000000000001"
    assert post.uid == "1234567890"
    assert post.images == ["https://example.com/pic1.jpg"]
    assert post.video_url == "https://example.com/video.mp4"
    assert post.likes_count == 10
    assert post.reposts_count == 3
    assert post.comments_count == 5


@pytest.mark.asyncio
async def test_weibo_client_get_posts_with_since_id() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(
        client,
        "_request",
        new=AsyncMock(side_effect=[_user_payload(), _posts_payload()]),
    ) as mock_request:
        await client.get_posts("1234567890", since_id="cursor_1", count=10)

    second_call = mock_request.await_args_list[1]
    assert second_call.args[0] == "/api/container/getIndex"
    assert second_call.kwargs["params"]["since_id"] == "cursor_1"
    assert second_call.kwargs["params"]["count"] == 10


@pytest.mark.asyncio
async def test_weibo_client_fetch_post() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_single_post_payload())):
        post = await client.fetch_post("abc123")

    assert isinstance(post, WeiboPost)
    assert post.bid == "abc123"
    assert post.mid == "5000000000001"
    assert post.uid == "1234567890"
    assert post.is_long_text is False
    assert post.likes_count == 20
    assert post.reposts_count == 5
    assert post.comments_count == 8


@pytest.mark.asyncio
async def test_weibo_client_fetch_post_long_text() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(
        client,
        "_request",
        new=AsyncMock(side_effect=[_single_post_payload(is_long_text=True), _long_text_payload()]),
    ) as mock_request:
        post = await client.fetch_post("abc123")

    assert post.is_long_text is True
    text_content = post.html or post.text
    assert "expanded long text content" in text_content

    assert mock_request.await_count == 2
    second_call = mock_request.await_args_list[1]
    assert second_call.args[0] == "/statuses/longtext"
    assert second_call.kwargs["params"]["id"] == "5000000000001"


@pytest.mark.asyncio
async def test_weibo_client_get_comments() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_comments_payload())):
        comments = await client.get_comments("5000000000001")

    assert isinstance(comments, WeiboCommentList)
    assert comments.total == 50
    assert comments.max_id == "max_cursor_123"
    assert len(comments.items) == 1

    item = comments.items[0]
    assert item.id == "c001"
    assert item.uid == "9999"
    assert item.nickname == "commenter1"
    assert item.text == "Nice post!"
    assert item.likes_count == 3


@pytest.mark.asyncio
async def test_weibo_client_get_comments_with_max_id() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_comments_payload())) as mock_request:
        await client.get_comments("5000000000001", max_id="m123", count=10)

    mock_request.assert_awaited_once()
    call = mock_request.await_args
    assert call.args[0] == "/api/comments/show"
    assert call.kwargs["params"]["id"] == "5000000000001"
    assert call.kwargs["params"]["max_id"] == "m123"
    assert call.kwargs["params"]["count"] == 10


@pytest.mark.asyncio
async def test_weibo_client_search_users() -> None:
    client = WeiboClient(cookie="SUB=abc123")

    with patch.object(client, "_request", new=AsyncMock(return_value=_search_payload(use_string_counts=True))):
        users = await client.search_users("found")

    assert len(users) == 1
    assert isinstance(users[0], WeiboUser)

    user = users[0]
    assert user.uid == "1111"
    assert user.nickname == "found_user"
    assert user.avatar == "https://example.com/a.jpg"
    assert user.description == "desc"
    assert user.followers_count == 15800
    assert user.following_count == 3205000
    assert user.verified is False


def test_parse_count() -> None:
    assert WeiboClient._parse_count(1000) == 1000
    assert WeiboClient._parse_count("1.58万") == 15800
    assert WeiboClient._parse_count("320.5万") == 3205000
    assert WeiboClient._parse_count("1亿") == 100000000
    assert WeiboClient._parse_count("2.5亿") == 250000000
    assert WeiboClient._parse_count("1234") == 1234
    assert WeiboClient._parse_count(None) is None
    assert WeiboClient._parse_count("") is None
