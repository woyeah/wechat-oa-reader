# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from pathlib import Path

import click

from . import __version__
from .auth import load_credentials, login_with_qrcode, save_credentials
from .client import WeChatClient
from .models import Credentials
from .weibo import WeiboClient


def _validate_urls(urls: list[str]) -> list[str]:
    valid_urls: list[str] = []
    for raw_url in urls:
        url = raw_url.strip()
        if not url:
            continue
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            raise click.BadParameter(
                f"Invalid URL scheme '{scheme}' in: {url}. Only http/https allowed."
            )
        valid_urls.append(url)
    return valid_urls


def _load_client_or_exit() -> WeChatClient:
    creds = load_credentials()
    if not creds:
        raise click.ClickException("No credentials found. Run `wechat-oa login` first.")
    return WeChatClient(token=creds.token, cookie=creds.cookie)


def _load_weibo_client_or_exit() -> WeiboClient:
    from dotenv import dotenv_values

    config = dotenv_values(".env")
    cookie = config.get("WEIBO_COOKIE") or os.environ.get("WEIBO_COOKIE", "")
    if not cookie:
        raise click.ClickException("No WEIBO_COOKIE found. Set it in .env file.")
    return WeiboClient(cookie=cookie)


@click.group()
@click.version_option(version=__version__, prog_name="wechat-oa")
def cli() -> None:
    """CLI for wechat-oa-reader."""


@cli.command()
@click.option("--manual", is_flag=True, help="Enter credentials manually")
@click.option("--token", default="", help="WeChat token")
@click.option("--cookie", default="", help="WeChat cookie")
@click.option("--fakeid", default="", help="WeChat fakeid")
@click.option("--nickname", default="", help="WeChat nickname")
def login(manual: bool, token: str, cookie: str, fakeid: str, nickname: str) -> None:
    """Login with QR code or manual credentials."""

    if manual:
        if not token or not cookie:
            raise click.ClickException("`--token` and `--cookie` are required when `--manual` is set.")
        creds = Credentials(token=token, cookie=cookie, fakeid=fakeid or None, nickname=nickname or None)
        save_credentials(creds)
        click.echo("Credentials saved to .env")
        return

    creds = asyncio.run(login_with_qrcode())
    save_credentials(creds)
    click.echo(f"Logged in as: {creds.nickname or 'unknown'}")


@cli.command()
@click.argument("query")
@click.option("--count", "count", default=5, type=int)
def search(query: str, count: int) -> None:
    """Search public accounts."""

    client = _load_client_or_exit()
    accounts = asyncio.run(client.search_accounts(query=query, count=count))
    click.echo(json.dumps([acc.model_dump() for acc in accounts], ensure_ascii=False, indent=2))


@cli.command()
@click.argument("fakeid")
@click.option("-n", "count", default=10, type=int)
@click.option("--offset", default=0, type=int)
@click.option("--keyword", default=None)
def articles(fakeid: str, count: int, offset: int, keyword: str | None) -> None:
    """List articles of an account."""

    client = _load_client_or_exit()
    result = asyncio.run(client.get_articles(fakeid=fakeid, count=count, offset=offset, keyword=keyword))
    click.echo(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


@cli.command()
@click.argument("url", required=False)
@click.option("--batch", "batch_file", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("-o", "output", type=click.Path(path_type=Path), default=None)
@click.option("--text", "as_text", is_flag=True, help="Output plain text only")
def fetch(url: str | None, batch_file: Path | None, output: Path | None, as_text: bool) -> None:
    """Fetch one or multiple articles."""

    client = _load_client_or_exit()

    if batch_file:
        urls = _validate_urls(batch_file.read_text(encoding="utf-8").splitlines())
        items = asyncio.run(client.fetch_articles(urls))
        payload = [item.plain_text if as_text else item.model_dump() for item in items]
    else:
        if not url:
            raise click.ClickException("Provide URL or --batch file")
        item = asyncio.run(client.fetch_article(url))
        if item is None:
            raise click.ClickException("Fetch failed")
        payload = item.plain_text if as_text else item.model_dump()

    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output.write_text(content, encoding="utf-8")
        click.echo(f"Saved to {output}")
    else:
        click.echo(content)


@cli.command()
def status() -> None:
    """Show credential status."""

    creds = load_credentials()
    if not creds:
        click.echo("Not authenticated")
        return
    click.echo(
        json.dumps(
            {
                "authenticated": True,
                "nickname": creds.nickname,
                "fakeid": creds.fakeid,
                "expire_time": creds.expire_time,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@cli.group()
def weibo() -> None:
    """Weibo commands."""


@weibo.command("status")
def weibo_status() -> None:
    """Check Weibo authentication status."""

    client = _load_weibo_client_or_exit()
    authenticated = asyncio.run(client.check_auth())
    click.echo(json.dumps({"authenticated": authenticated}, ensure_ascii=False, indent=2))


@weibo.command("user")
@click.argument("uid")
def weibo_user(uid: str) -> None:
    """Get Weibo user info."""

    client = _load_weibo_client_or_exit()
    user = asyncio.run(client.get_user(uid))
    click.echo(json.dumps(user.model_dump(), ensure_ascii=False, indent=2, default=str))


@weibo.command("posts")
@click.argument("uid")
@click.option("-n", "count", default=20, type=int)
def weibo_posts(uid: str, count: int) -> None:
    """List Weibo posts by user."""

    client = _load_weibo_client_or_exit()
    posts = asyncio.run(client.get_posts(uid=uid, count=count))
    click.echo(json.dumps(posts.model_dump(), ensure_ascii=False, indent=2, default=str))


@weibo.command("fetch")
@click.argument("bid")
@click.option("--text", "as_text", is_flag=True, help="Output plain text only")
def weibo_fetch(bid: str, as_text: bool) -> None:
    """Fetch a single Weibo post."""

    client = _load_weibo_client_or_exit()
    post = asyncio.run(client.fetch_post(bid))
    if as_text:
        click.echo(post.text)
        return
    click.echo(json.dumps(post.model_dump(), ensure_ascii=False, indent=2, default=str))


@weibo.command("article")
@click.argument("article_id")
@click.option("--text", "as_text", is_flag=True, help="Output plain text only")
def weibo_article(article_id: str, as_text: bool) -> None:
    """Fetch a Weibo headline article."""
    client = _load_weibo_client_or_exit()
    article = asyncio.run(client.fetch_article(article_id))
    if as_text:
        click.echo(article.plain_text)
    else:
        click.echo(json.dumps(article.model_dump(), ensure_ascii=False, indent=2, default=str))


@weibo.command("comments")
@click.argument("post_id")
@click.option("-n", "count", default=20, type=int)
def weibo_comments(post_id: str, count: int) -> None:
    """Get comments for a Weibo post."""

    client = _load_weibo_client_or_exit()
    comments = asyncio.run(client.get_comments(post_id=post_id, count=count))
    click.echo(json.dumps(comments.model_dump(), ensure_ascii=False, indent=2, default=str))


@weibo.command("search")
@click.argument("query")
def weibo_search(query: str) -> None:
    """Search Weibo users."""

    client = _load_weibo_client_or_exit()
    users = asyncio.run(client.search_users(query))
    click.echo(
        json.dumps([user.model_dump() for user in users], ensure_ascii=False, indent=2, default=str)
    )
