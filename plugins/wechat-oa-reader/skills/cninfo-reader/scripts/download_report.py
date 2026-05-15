#!/usr/bin/env python3
"""Download a report PDF from cninfo. Accepts adjunctUrl or full static URL."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_error


STATIC_HOST = "static.cninfo.com.cn"
STATIC_BASE = f"https://{STATIC_HOST}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


def _build_url(adjunct_url_or_full: str) -> str:
    if adjunct_url_or_full.startswith(("http://", "https://")):
        parsed = urlparse(adjunct_url_or_full)
        if parsed.hostname != STATIC_HOST:
            raise ValueError(
                f"Downloads only allowed from {STATIC_HOST}, got: {parsed.hostname!r}"
            )
        if parsed.scheme == "http":
            return "https://" + adjunct_url_or_full[len("http://"):]
        return adjunct_url_or_full
    return f"{STATIC_BASE}/{adjunct_url_or_full.lstrip('/')}"


def _default_filename(url: str) -> str:
    basename = url.rstrip("/").split("/")[-1]
    return basename or "report.pdf"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download a cninfo report PDF")
    parser.add_argument("adjunct_url", help="The adjunctUrl from list_reports, or full static URL")
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    args = parser.parse_args(argv)

    try:
        url = _build_url(args.adjunct_url)
        out_path = Path(args.output) if args.output else Path(_default_filename(args.adjunct_url))
        out_path.parent.mkdir(parents=True, exist_ok=True)

        total = 0
        # follow_redirects=False to prevent SSRF via 3xx to other hosts after
        # the URL host has been validated.
        with httpx.stream("GET", url, headers=HEADERS, timeout=60.0, follow_redirects=False) as resp:
            if 300 <= resp.status_code < 400:
                raise ValueError(
                    f"Refusing redirect during download (HTTP {resp.status_code} → {resp.headers.get('location', '')!r})"
                )
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
                    total += len(chunk)

        print(json.dumps({"saved": str(out_path), "size": total}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
