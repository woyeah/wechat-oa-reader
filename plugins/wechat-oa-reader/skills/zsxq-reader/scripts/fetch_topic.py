#!/usr/bin/env python3
"""Fetch a single zsxq topic with comments."""
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


def _topic_parts(topic: dict) -> tuple[str, str, str, list, list]:
    talk = topic.get("talk", {})
    question = topic.get("question", {})
    answer = topic.get("answer", {})

    if talk:
        author = talk.get("owner", {}).get("name", "")
        body = talk.get("text", "")
        images = talk.get("images", []) or []
        files = talk.get("files", []) or []
        return author, body, topic.get("create_time", ""), images, files

    author = question.get("owner", {}).get("name", "") or answer.get("owner", {}).get("name", "")
    body_parts = []
    q_text = question.get("text", "")
    a_text = answer.get("text", "")
    if q_text:
        body_parts.append(q_text)
    if a_text:
        body_parts.append(a_text)
    body = "\n\n".join(body_parts)
    images = (question.get("images", []) or []) + (answer.get("images", []) or [])
    files = (question.get("files", []) or []) + (answer.get("files", []) or [])
    return author, body, topic.get("create_time", ""), images, files


def _render_text(topic: dict, comments: list) -> str:
    author, body, create_time, images, files = _topic_parts(topic)
    lines = [f"# {author or 'Unknown'}", create_time or "", "", body or ""]

    if images:
        lines.extend(["", "## Images"])
        for img in images:
            url = img.get("large", {}).get("url") or img.get("original", {}).get("url") or img.get("url")
            if url:
                lines.append(url)

    if files:
        lines.extend(["", "## Files"])
        for file_item in files:
            name = file_item.get("name", "unknown")
            url = file_item.get("download_url", "")
            lines.append(f"- {name}: {url}")

    if comments:
        lines.extend(["", "## Comments"])
        for c in comments:
            owner = c.get("owner", {}).get("name", "Unknown")
            text = c.get("text", "")
            lines.append(f"- **{owner}**: {text}")

    return "\n".join(lines).strip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch zsxq topic details")
    parser.add_argument("topic_id")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("-o", dest="output")
    args = parser.parse_args(argv)

    try:
        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set ZSXQ_COOKIE or create .env")

        headers = _build_headers(cookie)
        topic_resp = httpx.get(f"https://api.zsxq.com/v2/topics/{args.topic_id}", headers=headers, timeout=30.0)
        topic_resp.raise_for_status()
        topic_data = topic_resp.json()

        topic_err = classify_api_response(topic_data)
        if topic_err:
            print(json.dumps(topic_err, ensure_ascii=False))
            sys.exit(1)

        comments_resp = httpx.get(
            f"https://api.zsxq.com/v2/topics/{args.topic_id}/comments?sort=asc&count=30",
            headers=headers,
            timeout=30.0,
        )
        comments_resp.raise_for_status()
        comments_data = comments_resp.json()

        comments_err = classify_api_response(comments_data)
        if comments_err:
            print(json.dumps(comments_err, ensure_ascii=False))
            sys.exit(1)

        topic = topic_data.get("resp_data", {}).get("topic", {})
        comments = comments_data.get("resp_data", {}).get("comments", [])

        if args.format == "json":
            output = json.dumps({"topic": topic, "comments": comments}, ensure_ascii=False)
        else:
            output = _render_text(topic, comments)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(json.dumps({"saved": args.output}, ensure_ascii=False))
        else:
            print(output)
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
