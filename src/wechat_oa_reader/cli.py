# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Literal

import click

from . import __version__
from .auth import load_credentials, login_with_qrcode, save_credentials
from .client import WeChatClient
from .models import Credentials
from .cninfo import CninfoClient
from .weibo import WeiboClient

try:
    from .docx_writer import article_to_docx
except ImportError:
    article_to_docx = None

_DOCX_DEPENDENCY_ERROR = (
    "docx export requires python-docx, beautifulsoup4 and pillow. "
    "Reinstall: uv pip install -e ."
)
_INVALID_WINDOWS_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def _infer_fetch_format(
    output: Path | None,
    explicit_format: str | None,
    as_text: bool,
) -> Literal["text", "json", "docx"]:
    if explicit_format in {"text", "json", "docx"}:
        return explicit_format
    if output and output.suffix.lower() == ".docx":
        return "docx"
    if as_text:
        return "text"
    return "json"


def _sanitize_docx_filename(title: str | None, index: int) -> str:
    cleaned = _INVALID_WINDOWS_FILENAME_CHARS.sub("", (title or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip(" .")
    return cleaned or f"article_{index}"


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
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "docx"]),
    default=None,
    help="Output format: text, json, or docx",
)
@click.option("--text", "as_text", is_flag=True, help="Output plain text only")
def fetch(
    url: str | None,
    batch_file: Path | None,
    output: Path | None,
    output_format: str | None,
    as_text: bool,
) -> None:
    """Fetch one or multiple articles."""

    client = _load_client_or_exit()
    resolved_format = _infer_fetch_format(output=output, explicit_format=output_format, as_text=as_text)

    if resolved_format == "docx" and article_to_docx is None:
        raise click.ClickException(_DOCX_DEPENDENCY_ERROR)

    if batch_file:
        urls = _validate_urls(batch_file.read_text(encoding="utf-8").splitlines())
        items = asyncio.run(client.fetch_articles(urls))
        if resolved_format == "docx":
            if output is None:
                raise click.ClickException("docx batch export requires -o <dir>")
            if output.exists() and not output.is_dir():
                raise click.ClickException("Batch docx output path must be a directory.")
            output.mkdir(parents=True, exist_ok=True)

            for index, item in enumerate(items, start=1):
                filename = _sanitize_docx_filename(item.title, index)
                target = output / f"{filename}.docx"
                asyncio.run(article_to_docx(item, target))
                click.echo(f"Saved to {target}")
            return

        payload = [item.plain_text if resolved_format == "text" else item.model_dump() for item in items]
    else:
        if not url:
            raise click.ClickException("Provide URL or --batch file")
        item = asyncio.run(client.fetch_article(url))
        if item is None:
            raise click.ClickException("Fetch failed")

        if resolved_format == "docx":
            if output is None:
                raise click.ClickException("docx export requires -o <file.docx>")
            if output.exists() and output.is_dir():
                raise click.ClickException("docx output path must be a file path.")
            asyncio.run(article_to_docx(item, output))
            click.echo(f"Saved to {output}")
            return

        payload = item.plain_text if resolved_format == "text" else item.model_dump()

    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output.write_text(content, encoding="utf-8")
        click.echo(f"Saved to {output}")
    else:
        click.echo(content)


@cli.command()
@click.option("--live/--no-live", default=True, help="Check authentication with a live server probe")
def status(live: bool) -> None:
    """Show credential status."""

    creds = load_credentials()
    if not creds:
        click.echo("Not authenticated")
        return

    payload: dict[str, object] = {
        "authenticated": True,
        "nickname": creds.nickname,
        "fakeid": creds.fakeid,
        "expire_time": creds.expire_time,
    }

    if live:
        client = WeChatClient(token=creds.token, cookie=creds.cookie)
        payload["live_check"] = "valid" if asyncio.run(client.check_auth()) else "expired"

    click.echo(
        json.dumps(
            payload,
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


@cli.group()
def cninfo() -> None:
    """巨潮资讯 (cninfo.com.cn) commands — public listed-company disclosures."""


@cninfo.command("search")
@click.argument("query")
@click.option("-n", "max_results", default=10, type=int, help="Max results to return")
def cninfo_search(query: str, max_results: int) -> None:
    """Search listed companies by code or name."""
    client = CninfoClient()
    stocks = asyncio.run(client.search_company(query, max_results=max_results))
    click.echo(
        json.dumps(
            [s.model_dump() for s in stocks],
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


@cninfo.command("reports")
@click.argument("code")
@click.option(
    "--type",
    "report_type",
    type=click.Choice(["annual", "semiannual", "q1", "q3"]),
    required=True,
    help="Report period: annual (年报) / semiannual (半年报) / q1 (一季报) / q3 (三季报)",
)
@click.option("--org-id", default=None, help="Organization ID. Auto-resolved via search if omitted.")
@click.option("--plate", default=None, help="Exchange plate: szse / sse / bj. Auto-resolved if omitted.")
@click.option("--column", default=None, help="Override the request column (advanced)")
@click.option("--since", "start_date", default=None, help="Start date YYYY-MM-DD")
@click.option("--until", "end_date", default=None, help="End date YYYY-MM-DD")
@click.option("--page", default=1, type=int)
@click.option("-n", "page_size", default=30, type=int)
def cninfo_reports(
    code: str,
    report_type: str,
    org_id: str | None,
    plate: str | None,
    column: str | None,
    start_date: str | None,
    end_date: str | None,
    page: int,
    page_size: int,
) -> None:
    """List periodic reports (年报 / 半年报 / 一季报 / 三季报) for a stock CODE."""
    client = CninfoClient()

    async def _run() -> str:
        resolved_org_id = org_id
        resolved_plate = plate
        if not resolved_org_id or not resolved_plate:
            stocks = await client.search_company(code)
            match = next((s for s in stocks if s.code == code), None)
            if not match:
                raise click.ClickException(
                    f"Stock {code!r} not found. Pass --org-id and --plate explicitly."
                )
            resolved_org_id = resolved_org_id or match.org_id
            resolved_plate = resolved_plate or match.plate
            if not resolved_plate and not column:
                raise click.ClickException(
                    f"Cannot infer plate for {code!r}; pass --plate or --column."
                )

        result = await client.list_reports(
            code=code,
            org_id=resolved_org_id,
            report_type=report_type,
            plate=resolved_plate,
            column=column,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str)

    click.echo(asyncio.run(_run()))


@cninfo.command("download")
@click.argument("adjunct_url")
@click.option("-o", "output", default=None, type=click.Path(), help="Output PDF path")
def cninfo_download(adjunct_url: str, output: str | None) -> None:
    """Download a report PDF given its adjunctUrl or full static.cninfo.com.cn URL."""
    client = CninfoClient()
    if output:
        out_path = Path(output)
    else:
        basename = adjunct_url.rstrip("/").split("/")[-1] or "report.pdf"
        out_path = Path(basename)
    size = asyncio.run(client.download_report(adjunct_url, out_path))
    click.echo(
        json.dumps(
            {"saved": str(out_path), "size": size},
            ensure_ascii=False,
            indent=2,
        )
    )
