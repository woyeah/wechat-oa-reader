#!/usr/bin/env python3
"""Fetch WeChat article content."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import os
sys.path.insert(0, os.path.dirname(__file__))
from _errors import classify_error

from wechat_oa_reader.auth import load_credentials
from wechat_oa_reader.client import WeChatClient


def main():
    parser = argparse.ArgumentParser(description="Fetch article content")
    parser.add_argument("url", nargs="?", default=None, help="Article URL")
    parser.add_argument("--batch", type=str, default=None, help="File with URLs (one per line)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    if not args.url and not args.batch:
        print(json.dumps({"error": "Provide a URL or --batch file", "error_code": "invalid_input"}))
        sys.exit(1)

    creds = load_credentials()
    if not creds:
        print(json.dumps({"error": "Not authenticated. Run login first.", "error_code": "auth_missing"}))
        sys.exit(1)

    client = WeChatClient(token=creds.token, cookie=creds.cookie)

    try:
        if args.batch:
            urls = [line.strip() for line in Path(args.batch).read_text(encoding="utf-8").splitlines() if line.strip()]
            articles = asyncio.run(client.fetch_articles(urls))
            if args.format == "text":
                content = "\n\n---\n\n".join(
                    f"# {a.title or 'Untitled'}\n\n{a.plain_text}" for a in articles
                )
            else:
                content = json.dumps(
                    [a.model_dump() for a in articles],
                    ensure_ascii=False, indent=2,
                )
        else:
            article = asyncio.run(client.fetch_article(args.url))
            if not article:
                print(json.dumps({
                    "error": "Failed to fetch article. The page may require authentication or the URL may be invalid.",
                    "error_code": "fetch_failed",
                }))
                sys.exit(1)
            if args.format == "text":
                content = f"# {article.title or 'Untitled'}\n\n{article.plain_text}"
            else:
                content = json.dumps(article.model_dump(), ensure_ascii=False, indent=2)
    except Exception as e:
        print(json.dumps(classify_error(e)))
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(json.dumps({"saved": args.output}))
    else:
        print(content)


if __name__ == "__main__":
    main()
