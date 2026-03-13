#!/usr/bin/env python3
"""List articles from a WeChat Official Account."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
import os
sys.path.insert(0, os.path.dirname(__file__))
from _errors import classify_error

from wechat_oa_reader.auth import load_credentials
from wechat_oa_reader.client import WeChatClient


def _ts_to_date(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return ""


def main():
    parser = argparse.ArgumentParser(description="List articles")
    parser.add_argument("fakeid", help="Account fakeid")
    parser.add_argument("--count", type=int, default=10, help="Number of articles")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    parser.add_argument("--keyword", default=None, help="Search keyword")
    args = parser.parse_args()

    creds = load_credentials()
    if not creds:
        print(json.dumps({"error": "Not authenticated. Run login first.", "error_code": "auth_missing"}))
        sys.exit(1)

    client = WeChatClient(token=creds.token, cookie=creds.cookie)

    try:
        result = asyncio.run(client.get_articles(
            fakeid=args.fakeid,
            count=args.count,
            offset=args.offset,
            keyword=args.keyword,
        ))
    except Exception as e:
        print(json.dumps(classify_error(e)))
        sys.exit(1)

    articles = []
    for a in result.items:
        articles.append({
            "title": a.title,
            "date": _ts_to_date(a.update_time),
            "link": a.link,
        })

    print(json.dumps({
        "total": result.total,
        "offset": result.offset,
        "count": len(articles),
        "articles": articles,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
