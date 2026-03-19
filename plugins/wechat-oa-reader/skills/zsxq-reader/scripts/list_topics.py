#!/usr/bin/env python3
"""List topics from a zsxq group."""
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


def _topic_type(topic: dict) -> str:
    if "talk" in topic:
        return "talk"
    if "question" in topic:
        return "q_and_a"
    if "answer" in topic:
        return "answer"
    return "unknown"


def _extract_preview(topic: dict) -> str:
    text = ""
    if "talk" in topic:
        text = topic.get("talk", {}).get("text", "")
    elif "question" in topic:
        text = topic.get("question", {}).get("text", "")
    elif "answer" in topic:
        text = topic.get("answer", {}).get("text", "")
    return text[:200]


def _extract_author(topic: dict) -> str:
    if "talk" in topic:
        return topic.get("talk", {}).get("owner", {}).get("name", "")
    if "question" in topic:
        return topic.get("question", {}).get("owner", {}).get("name", "")
    if "answer" in topic:
        return topic.get("answer", {}).get("owner", {}).get("name", "")
    return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="List zsxq group topics")
    parser.add_argument("group_id")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--scope", choices=["all", "digests"], default="all")
    parser.add_argument("--before", help="Pagination time (datetime string)")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set ZSXQ_COOKIE or create .env")

        url = f"https://api.zsxq.com/v2/groups/{args.group_id}/topics"
        params = {"scope": args.scope, "count": args.count}
        if args.before:
            params["end_time"] = args.before

        resp = httpx.get(url, params=params, headers=_build_headers(cookie), timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        api_err = classify_api_response(data)
        if api_err:
            print(json.dumps(api_err, ensure_ascii=False))
            sys.exit(1)

        resp_data = data.get("resp_data", {})
        raw_topics = resp_data.get("topics", [])
        topics = []
        for topic in raw_topics:
            topics.append(
                {
                    "topic_id": topic.get("topic_id"),
                    "type": _topic_type(topic),
                    "author": _extract_author(topic),
                    "create_time": topic.get("create_time"),
                    "preview": _extract_preview(topic),
                }
            )

        earliest_time = raw_topics[-1].get("create_time") if raw_topics else None
        out = {
            "group_id": args.group_id,
            "count": len(raw_topics),
            "has_more": resp_data.get("has_more", False),
            "earliest_time": earliest_time,
            "topics": topics,
        }
        print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
