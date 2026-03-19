#!/usr/bin/env python3
"""List groups the authenticated user has joined."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_api_response, classify_error


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
        from dotenv import load_dotenv

        load_dotenv(env_path, override=True)
    return os.environ.get("ZSXQ_COOKIE")


def main(argv=None):
    parser = argparse.ArgumentParser(description="List joined zsxq groups")
    parser.add_argument("--count", type=int, default=None)
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set ZSXQ_COOKIE or create .env")

        params = {}
        if args.count is not None:
            params["count"] = args.count

        resp = httpx.get(
            "https://api.zsxq.com/v2/groups",
            params=params if params else None,
            headers=_build_headers(cookie),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        api_err = classify_api_response(data)
        if api_err:
            print(json.dumps(api_err, ensure_ascii=False))
            sys.exit(1)

        raw_groups = data.get("resp_data", {}).get("groups", [])
        groups = []
        for group in raw_groups:
            statistics = group.get("statistics", {})
            groups.append(
                {
                    "group_id": group.get("group_id"),
                    "name": group.get("name"),
                    "type": group.get("type"),
                    "owner": group.get("owner", {}).get("name"),
                    "members_count": statistics.get("members_count"),
                    "topics_count": statistics.get("topics_count"),
                }
            )

        print(json.dumps({"count": len(groups), "groups": groups}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
