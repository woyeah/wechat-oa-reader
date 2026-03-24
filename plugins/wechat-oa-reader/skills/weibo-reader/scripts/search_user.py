#!/usr/bin/env python3
"""Search Weibo users by keyword."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

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


def _extract_user(item: dict) -> dict:
    user = item.get("user", {}) if isinstance(item, dict) else {}
    return {
        "uid": str(user.get("id") or user.get("idstr") or ""),
        "nickname": user.get("screen_name"),
        "avatar": user.get("profile_image_url"),
        "description": user.get("description"),
        "followers_count": user.get("followers_count"),
        "following_count": user.get("follow_count"),
        "verified": bool(user.get("verified")),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search Weibo users by keyword")
    parser.add_argument("query")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set WEIBO_COOKIE or create .env")

        url = f"https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D3%26q%3D{quote(args.query)}"
        resp = httpx.get(url, headers=_build_headers(cookie), timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        api_err = classify_api_response(data)
        if api_err:
            print(json.dumps(api_err, ensure_ascii=False))
            sys.exit(1)

        users = []
        cards = data.get("data", {}).get("cards", []) or []
        for card in cards:
            if card.get("card_type") != 11:
                continue
            for group_item in card.get("card_group", []) or []:
                if group_item.get("card_type") != 10:
                    continue
                user = _extract_user(group_item)
                if user.get("uid"):
                    users.append(user)

        print(json.dumps(users, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
