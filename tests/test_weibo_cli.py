# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime

import click
from click.testing import CliRunner

from wechat_oa_reader.cli import cli
from wechat_oa_reader.models import WeiboComment, WeiboCommentList, WeiboPost, WeiboPostList, WeiboUser
from wechat_oa_reader.weibo import WeiboClient


def test_weibo_status_no_cookie(monkeypatch) -> None:
    def _raise() -> WeiboClient:
        raise click.ClickException("No WEIBO_COOKIE found. Set it in .env file.")

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", _raise)
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "status"])
    assert result.exit_code != 0
    assert "No WEIBO_COOKIE found" in result.output


def test_weibo_status_ok(monkeypatch) -> None:
    async def _check_auth() -> bool:
        return True

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "check_auth", lambda self: _check_auth())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "status"])
    assert result.exit_code == 0
    assert '"authenticated": true' in result.output


def test_weibo_user(monkeypatch) -> None:
    user = WeiboUser(uid="123", nickname="alice", verified=True)

    async def _get_user() -> WeiboUser:
        return user

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "get_user", lambda self, uid: _get_user())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "user", "123"])
    assert result.exit_code == 0
    assert '"uid": "123"' in result.output
    assert '"nickname": "alice"' in result.output


def test_weibo_posts(monkeypatch) -> None:
    post = WeiboPost(
        bid="BID001",
        mid="MID001",
        uid="123",
        text="hello",
        html="hello",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )
    posts = WeiboPostList(items=[post], total=1, since_id="next")

    async def _get_posts() -> WeiboPostList:
        return posts

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "get_posts", lambda self, uid, count: _get_posts())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "posts", "123", "-n", "20"])
    assert result.exit_code == 0
    assert '"bid": "BID001"' in result.output
    assert '"total": 1' in result.output


def test_weibo_fetch(monkeypatch) -> None:
    post = WeiboPost(
        bid="BID001",
        mid="MID001",
        uid="123",
        text="content",
        html="content",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )

    async def _fetch_post() -> WeiboPost:
        return post

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "fetch_post", lambda self, bid: _fetch_post())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "fetch", "BID001"])
    assert result.exit_code == 0
    assert '"bid": "BID001"' in result.output
    assert '"text": "content"' in result.output


def test_weibo_fetch_text(monkeypatch) -> None:
    post = WeiboPost(
        bid="BID001",
        mid="MID001",
        uid="123",
        text="plain text output",
        html="plain text output",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )

    async def _fetch_post() -> WeiboPost:
        return post

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "fetch_post", lambda self, bid: _fetch_post())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "fetch", "BID001", "--text"])
    assert result.exit_code == 0
    assert "plain text output" in result.output
    assert '"bid": "BID001"' not in result.output


def test_weibo_comments(monkeypatch) -> None:
    comment = WeiboComment(
        id="c1",
        uid="u1",
        nickname="bob",
        text="nice",
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )
    comments = WeiboCommentList(items=[comment], total=1, max_id="next")

    async def _get_comments() -> WeiboCommentList:
        return comments

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "get_comments", lambda self, post_id, count: _get_comments())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "comments", "p1", "-n", "20"])
    assert result.exit_code == 0
    assert '"id": "c1"' in result.output
    assert '"nickname": "bob"' in result.output


def test_weibo_search(monkeypatch) -> None:
    users = [WeiboUser(uid="123", nickname="alice"), WeiboUser(uid="456", nickname="charlie")]

    async def _search_users() -> list[WeiboUser]:
        return users

    monkeypatch.setattr("wechat_oa_reader.cli._load_weibo_client_or_exit", lambda: WeiboClient(cookie="cookie"))
    monkeypatch.setattr(WeiboClient, "search_users", lambda self, query: _search_users())
    runner = CliRunner()
    result = runner.invoke(cli, ["weibo", "search", "ali"])
    assert result.exit_code == 0
    assert '"uid": "123"' in result.output
    assert '"uid": "456"' in result.output
