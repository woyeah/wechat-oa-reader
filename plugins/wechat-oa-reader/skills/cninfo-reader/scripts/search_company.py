#!/usr/bin/env python3
"""Search listed companies on 巨潮资讯网 by code or name."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os

import httpx

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_error


SEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/detailOfQuery"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "Origin": "http://www.cninfo.com.cn",
}


def _infer_plate(code: str) -> str:
    if not code or not code.isdigit():
        return ""
    if code.startswith(("60", "68", "90")):
        return "sse"
    if code.startswith(("00", "30")):
        return "szse"
    if code.startswith(("43", "83", "87", "88", "89", "92")):
        return "bj"
    return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search listed companies on cninfo")
    parser.add_argument("query")
    parser.add_argument("-n", "--max-results", type=int, default=10)
    args = parser.parse_args(argv)

    try:
        resp = httpx.post(
            SEARCH_URL,
            data={"keyWord": args.query, "maxSecNum": args.max_results, "maxListCount": 5},
            headers=HEADERS,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        stocks = []
        for item in data.get("keyBoardList") or []:
            code = str(item.get("code") or "")
            plate = str(item.get("plate") or "") or _infer_plate(code)
            stocks.append(
                {
                    "code": code,
                    "org_id": str(item.get("orgId") or ""),
                    "name": item.get("zwjc") or "",
                    "plate": plate,
                    "listing_category": item.get("category"),
                    "pinyin": item.get("pinyin"),
                    "delisted": str(item.get("delisted")).lower() == "true",
                }
            )
        print(json.dumps(stocks, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
