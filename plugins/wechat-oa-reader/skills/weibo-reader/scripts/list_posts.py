#!/usr/bin/env python3
"""List posts from a Weibo user."""
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


def _extract_images(mblog: dict) -> list[str]:
    out = []
    for pic in mblog.get("pics", []) or []:
        large = pic.get("large", {}) or {}
        out.append(large.get("url") or pic.get("url") or "")
    return [u for u in out if u]


def _discover_weibo_containerid(cookie: str, uid: str) -> str:
    resp = httpx.get(
        "https://m.weibo.cn/api/container/getIndex",
        params={"type": "uid", "value": uid},
        headers=_build_headers(cookie),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()

    api_err = classify_api_response(data)
    if api_err:
        raise ValueError(api_err["error"])

    tabs = data.get("data", {}).get("tabsInfo", {}).get("tabs", []) or []
    for tab in tabs:
        tab_type = str(tab.get("tab_type", "")).lower()
        title = str(tab.get("title", "")).lower()
        cid = tab.get("containerid")
        if not cid:
            continue
        if tab_type == "weibo" or "weibo" in title or cid.startswith("107603"):
            return cid

    raise ValueError("Failed to discover Weibo posts containerid")


def main(argv=None):
    parser = argparse.ArgumentParser(description="List posts from a Weibo user")
    parser.add_argument("uid")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--since-id")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set WEIBO_COOKIE or create .env")

        containerid = _discover_weibo_containerid(cookie, args.uid)

        params = {"containerid": containerid, "count": args.count}
        if args.since_id:
            params["since_id"] = args.since_id

        resp = httpx.get(
            "https://m.weibo.cn/api/container/getIndex",
            params=params,
            headers=_build_headers(cookie),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        api_err = classify_api_response(data)
        if api_err:
            print(json.dumps(api_err, ensure_ascii=False))
            sys.exit(1)

        posts = []
        cards = data.get("data", {}).get("cards", []) or []
        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog", {}) or {}
            posts.append(
                {
                    "bid": mblog.get("bid"),
                    "mid": str(mblog.get("mid") or mblog.get("id") or ""),
                    "text": _strip_html(mblog.get("text", "")),
                    "images": _extract_images(mblog),
                    "video_url": _pick_video_url(mblog),
                    "is_long_text": bool(mblog.get("isLongText")),
                    "created_at": mblog.get("created_at"),
                    "likes_count": mblog.get("attitudes_count"),
                    "reposts_count": mblog.get("reposts_count"),
                    "comments_count": mblog.get("comments_count"),
                }
            )

        since_id = data.get("data", {}).get("cardlistInfo", {}).get("since_id")
        out = {"uid": args.uid, "count": len(posts), "since_id": since_id, "posts": posts}
        print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
