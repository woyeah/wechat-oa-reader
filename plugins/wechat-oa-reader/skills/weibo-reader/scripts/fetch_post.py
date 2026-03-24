#!/usr/bin/env python3
"""Fetch a single Weibo post by bid."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
import re
from html import unescape
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_error
from _errors import classify_api_response


def _build_headers(cookie: str) -> dict:
    return {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://m.weibo.cn/",
    }


def _load_cookie() -> str | None:
    """Load cookie from .env file or WEIBO_COOKIE env var."""
    env_path = Path(".env")
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path, override=True)
    return os.environ.get("WEIBO_COOKIE")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    no_tags = re.sub(r"<[^>]+>", "", text)
    return unescape(no_tags).strip()


def _extract_images(mblog: dict) -> list[str]:
    out = []
    for pic in mblog.get("pics", []) or []:
        large = pic.get("large", {}) or {}
        out.append(large.get("url") or pic.get("url") or "")
    return [u for u in out if u]


def _pick_video_url(mblog: dict) -> str | None:
    page_info = mblog.get("page_info", {}) or {}
    urls = page_info.get("urls", {}) or {}
    media_info = page_info.get("media_info", {}) or {}
    return (
        urls.get("mp4_720p_mp4")
        or urls.get("mp4_hd_mp4")
        or urls.get("mp4_ld_mp4")
        or media_info.get("stream_url_hd")
        or media_info.get("stream_url")
        or page_info.get("page_url")
    )


def _render_text(post: dict) -> str:
    lines = [
        f"@{post.get('nickname') or 'unknown'}",
        post.get("created_at") or "",
        "",
        post.get("text") or "",
    ]
    images = post.get("images") or []
    if images:
        lines.extend(["", "Images:"])
        for img in images:
            lines.append(img)
    if post.get("video_url"):
        lines.extend(["", f"Video: {post['video_url']}"])
    return "\n".join(lines).strip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch a Weibo post by bid")
    parser.add_argument("bid")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set WEIBO_COOKIE or create .env")

        resp = httpx.get(
            "https://m.weibo.cn/statuses/show",
            params={"id": args.bid},
            headers=_build_headers(cookie),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        api_err = classify_api_response(data)
        if api_err:
            print(json.dumps(api_err, ensure_ascii=False))
            sys.exit(1)

        mblog = data.get("data", {}) or {}
        mid = str(mblog.get("mid") or mblog.get("id") or "")
        long_text_html = None

        if mblog.get("isLongText") and mid:
            long_resp = httpx.get(
                "https://m.weibo.cn/statuses/longtext",
                params={"id": mid},
                headers=_build_headers(cookie),
                timeout=30.0,
            )
            long_resp.raise_for_status()
            long_data = long_resp.json()
            if long_data.get("ok") == 1:
                long_text_html = (long_data.get("data", {}) or {}).get("longTextContent")

        text_html = long_text_html or mblog.get("text", "")
        post = {
            "bid": mblog.get("bid") or args.bid,
            "mid": mid,
            "uid": str((mblog.get("user", {}) or {}).get("id") or ""),
            "nickname": (mblog.get("user", {}) or {}).get("screen_name"),
            "text": _strip_html(text_html),
            "text_html": text_html,
            "images": _extract_images(mblog),
            "video_url": _pick_video_url(mblog),
            "is_long_text": bool(mblog.get("isLongText")),
            "created_at": mblog.get("created_at"),
            "likes_count": mblog.get("attitudes_count"),
            "reposts_count": mblog.get("reposts_count"),
            "comments_count": mblog.get("comments_count"),
        }

        if args.format == "text":
            print(_render_text(post))
        else:
            print(json.dumps(post, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
