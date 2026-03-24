#!/usr/bin/env python3
"""Check or save Weibo authentication cookie."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key

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
        load_dotenv(env_path, override=True)
    return os.environ.get("WEIBO_COOKIE")


def _check_cookie(cookie: str) -> tuple[bool, str | None, str | None]:
    resp = httpx.get(
        "https://m.weibo.cn/api/config",
        headers=_build_headers(cookie),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()

    api_err = classify_api_response(data)
    if api_err:
        return False, None, None

    cfg = data.get("data", {}) or {}
    uid = cfg.get("uid") or cfg.get("user", {}).get("id") or cfg.get("user", {}).get("idstr")
    screen_name = cfg.get("screen_name") or cfg.get("nick") or cfg.get("user", {}).get("screen_name")
    return True, str(uid) if uid is not None else None, screen_name


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check or save Weibo auth cookie")
    parser.add_argument("--save", action="store_true", help="Verify and save cookie to .env")
    parser.add_argument("--cookie", help="Cookie string (used with --save)")
    args = parser.parse_args(argv)

    try:
        if args.save and args.cookie:
            cookie = args.cookie
        elif args.save and not args.cookie:
            cookie = sys.stdin.read().strip()
        else:
            cookie = _load_cookie()

        if not cookie:
            print(json.dumps({"status": "missing"}, ensure_ascii=False))
            sys.exit(1)

        ok, uid, screen_name = _check_cookie(cookie)
        if not ok:
            print(json.dumps({"status": "expired"}, ensure_ascii=False))
            return

        if args.save:
            env_path = Path(".env")
            if not env_path.exists():
                env_path.touch()
            set_key(str(env_path), "WEIBO_COOKIE", cookie)

        print(json.dumps({"status": "valid", "uid": uid, "screen_name": screen_name}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
