#!/usr/bin/env python3
"""List comments on a Weibo post."""
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="List comments on a Weibo post")
    parser.add_argument("post_id", help="Post mid")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--max-id")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set WEIBO_COOKIE or create .env")

        params = {"id": args.post_id, "count": args.count}
        if args.max_id:
            params["max_id"] = args.max_id

        resp = httpx.get(
            "https://m.weibo.cn/api/comments/show",
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

        payload = data.get("data", {}) or {}
        raw_comments = payload.get("data", []) or []
        comments = []
        for c in raw_comments:
            user = c.get("user", {}) or {}
            comments.append(
                {
                    "id": str(c.get("id") or c.get("idstr") or ""),
                    "uid": str(user.get("id") or ""),
                    "nickname": user.get("screen_name"),
                    "text": _strip_html(c.get("text", "")),
                    "created_at": c.get("created_at"),
                    "likes_count": c.get("like_counts"),
                }
            )

        out = {
            "post_id": args.post_id,
            "count": len(comments),
            "total": payload.get("total_number"),
            "max_id": payload.get("max_id"),
            "comments": comments,
        }
        print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
