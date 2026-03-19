#!/usr/bin/env python3
"""Check or save zsxq authentication cookie."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_error


def _build_headers(cookie: str) -> dict:
    return {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://wx.zsxq.com",
        "Referer": "https://wx.zsxq.com/",
        "X-Timestamp": str(int(time.time())),
        "X-Request-Id": str(uuid.uuid4()),
        "X-Signature": "733fd672ddf6d4e367730d9622cdd1e28a4b6203",
        "X-Version": "2.77.0",
    }


def _load_cookie() -> str | None:
    """Load cookie from .env file or ZSXQ_COOKIE env var."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path, override=True)
    return os.environ.get("ZSXQ_COOKIE")


def _check_cookie(cookie: str) -> tuple[bool, str | None]:
    resp = httpx.get(
        "https://api.zsxq.com/v2/users/self",
        headers=_build_headers(cookie),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("succeeded"):
        return True, data.get("resp_data", {}).get("user", {}).get("name")
    return False, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check or save zsxq auth cookie")
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

        ok, user_name = _check_cookie(cookie)
        if not ok:
            print(json.dumps({"status": "expired"}, ensure_ascii=False))
            return

        if args.save:
            env_path = Path(".env")
            if not env_path.exists():
                env_path.touch()
            set_key(str(env_path), "ZSXQ_COOKIE", cookie)

        print(json.dumps({"status": "valid", "user_name": user_name}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
