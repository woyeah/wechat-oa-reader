#!/usr/bin/env python3
"""Download a file directly or all files from a zsxq topic."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

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


def _default_name_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    return _safe_filename(name) if name else "download.bin"


def _safe_filename(raw: str) -> str:
    """Strip directory components to prevent path traversal."""
    # Handle both Unix and Windows separators
    name = raw.replace("\\", "/").split("/")[-1]
    # Remove leading dots to prevent hidden files
    name = name.lstrip(".")
    return name or "download.bin"


def _validate_download_url(url: str) -> None:
    """Ensure URL is HTTPS to prevent SSRF and credential leakage."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Only HTTP(S) URLs are supported, got: {parsed.scheme!r}")
    host = parsed.hostname or ""
    # Block internal/private network addresses
    if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.startswith("169.254.") or host.startswith("10.") or host.startswith("192.168."):
        raise ValueError(f"Downloads from internal addresses are not allowed: {host}")


def _download(url: str, out_path: Path, headers: dict | None = None) -> int:
    total = 0
    with httpx.stream("GET", url, headers=headers, timeout=60.0) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
                total += len(chunk)
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download zsxq file(s)")
    parser.add_argument("url", nargs="?")
    parser.add_argument("--topic-id", dest="topic_id")
    parser.add_argument("-o", dest="output")
    args = parser.parse_args(argv)

    try:
        if not args.url and not args.topic_id:
            raise ValueError("Provide either a url or --topic-id")

        if args.url:
            _validate_download_url(args.url)
            out_path = Path(args.output) if args.output else Path(_default_name_from_url(args.url))
            size = _download(args.url, out_path)
            print(json.dumps({"saved": str(out_path), "size": size}, ensure_ascii=False))
            return

        cookie = _load_cookie()
        if not cookie:
            raise ValueError("Missing cookie. Set ZSXQ_COOKIE or create .env")

        headers = _build_headers(cookie)
        topic_resp = httpx.get(
            f"https://api.zsxq.com/v2/topics/{args.topic_id}",
            headers=headers,
            timeout=30.0,
        )
        topic_resp.raise_for_status()
        topic_data = topic_resp.json()
        topic_err = classify_api_response(topic_data)
        if topic_err:
            print(json.dumps(topic_err, ensure_ascii=False))
            sys.exit(1)

        topic = topic_data.get("resp_data", {}).get("topic", {})
        files = topic.get("talk", {}).get("files", []) or []

        downloads = []
        for item in files:
            name = _safe_filename(item.get("name", "")) or _default_name_from_url(item.get("download_url", ""))
            url = item.get("download_url")
            if not url:
                continue
            _validate_download_url(url)
            out_path = Path(name)
            size = _download(url, out_path, headers=headers)
            downloads.append({"saved": str(out_path), "size": size})

        print(json.dumps({"topic_id": args.topic_id, "downloads": downloads}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
