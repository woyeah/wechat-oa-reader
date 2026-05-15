#!/usr/bin/env python3
"""List periodic reports (年报/半年报/一季报/三季报) for a listed company."""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import httpx

_CST = timezone(timedelta(hours=8))

sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)
from _errors import classify_error


QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
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

CATEGORY_MAP = {
    "annual": "category_ndbg_szsh",
    "semiannual": "category_bndbg_szsh",
    "q1": "category_yjdbg_szsh",
    "q3": "category_sjdbg_szsh",
}

PLATE_TO_COLUMN = {"szse": "szse", "sse": "sse", "bj": "bj"}


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


def _resolve(code: str, org_id: str | None, plate: str | None) -> tuple[str, str]:
    if org_id and plate:
        return org_id, plate
    resp = httpx.post(
        SEARCH_URL,
        data={"keyWord": code, "maxSecNum": 10, "maxListCount": 1},
        headers=HEADERS,
        timeout=30.0,
    )
    resp.raise_for_status()
    items = resp.json().get("keyBoardList") or []
    for item in items:
        if str(item.get("code") or "") == code:
            inferred_plate = str(item.get("plate") or "") or _infer_plate(code)
            return (
                org_id or str(item.get("orgId") or ""),
                plate or inferred_plate,
            )
    raise ValueError(f"Stock {code!r} not found via search")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List periodic reports for a stock from cninfo"
    )
    parser.add_argument("code", help="Stock code, e.g. 000001 / 600519 / 873169")
    parser.add_argument(
        "--type",
        dest="report_type",
        required=True,
        choices=sorted(CATEGORY_MAP),
        help="Report period",
    )
    parser.add_argument("--org-id", default=None, help="Org ID (auto-resolved if omitted)")
    parser.add_argument("--plate", default=None, choices=["szse", "sse", "bj"], help="Exchange plate")
    parser.add_argument("--since", dest="start_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--until", dest="end_date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("-n", "--page-size", type=int, default=30)
    args = parser.parse_args(argv)

    try:
        if args.page < 1:
            raise ValueError(f"page must be >= 1, got {args.page}")
        if args.page_size < 1:
            raise ValueError(f"page-size must be >= 1, got {args.page_size}")
        org_id, plate = _resolve(args.code, args.org_id, args.plate)
        if not plate:
            raise ValueError(
                f"Cannot determine plate for code {args.code!r}. Pass --plate explicitly."
            )
        column = PLATE_TO_COLUMN.get(plate)
        if not column:
            raise ValueError(f"Unknown plate {plate!r}")

        se_date = ""
        if args.start_date and args.end_date:
            se_date = f"{args.start_date}~{args.end_date}"
        elif args.start_date or args.end_date:
            se_date = f"{args.start_date or ''}~{args.end_date or ''}"

        body = {
            "pageNum": args.page,
            "pageSize": args.page_size,
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{args.code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": CATEGORY_MAP[args.report_type],
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        resp = httpx.post(QUERY_URL, data=body, headers=HEADERS, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        items = []
        for item in data.get("announcements") or []:
            ts_ms = item.get("announcementTime") or 0
            iso = datetime.fromtimestamp(int(ts_ms) / 1000, tz=_CST).isoformat()
            items.append(
                {
                    "code": item.get("secCode") or "",
                    "name": item.get("secName") or "",
                    "org_id": item.get("orgId") or "",
                    "announcement_id": str(item.get("announcementId") or ""),
                    "title": item.get("announcementTitle") or "",
                    "time": iso,
                    "adjunct_url": item.get("adjunctUrl") or "",
                    "adjunct_size": item.get("adjunctSize"),
                    "adjunct_type": item.get("adjunctType"),
                }
            )

        total = int(data.get("totalAnnouncement") or 0)
        has_more = args.page * args.page_size < total
        print(
            json.dumps(
                {
                    "items": items,
                    "total": total,
                    "page": args.page,
                    "page_size": args.page_size,
                    "has_more": has_more,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
