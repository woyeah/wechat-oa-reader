#!/usr/bin/env python3
"""Search WeChat Official Accounts."""
import argparse
import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
import os
sys.path.insert(0, os.path.dirname(__file__))
from _errors import classify_error

from wechat_oa_reader.auth import load_credentials
from wechat_oa_reader.client import WeChatClient


def main():
    parser = argparse.ArgumentParser(description="Search WeChat OA")
    parser.add_argument("query", help="Search keyword")
    parser.add_argument("--count", type=int, default=5, help="Max results")
    args = parser.parse_args()

    creds = load_credentials()
    if not creds:
        print(json.dumps({"error": "Not authenticated. Run login first.", "error_code": "auth_missing"}))
        sys.exit(1)

    client = WeChatClient(token=creds.token, cookie=creds.cookie)

    try:
        accounts = asyncio.run(client.search_accounts(args.query, count=args.count))
    except Exception as e:
        print(json.dumps(classify_error(e)))
        sys.exit(1)

    results = []
    for a in accounts:
        results.append({
            "nickname": a.nickname,
            "fakeid": a.fakeid,
            "alias": a.alias,
        })

    print(json.dumps({"total": len(results), "accounts": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
