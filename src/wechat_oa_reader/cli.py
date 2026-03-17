# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import json
import urllib.parse
from pathlib import Path

import click

from . import __version__
from .auth import load_credentials, login_with_qrcode, save_credentials
from .client import WeChatClient
from .models import Credentials


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
