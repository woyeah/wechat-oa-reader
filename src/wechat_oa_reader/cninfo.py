# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from .models import CninfoReport, CninfoReportList, CninfoStock

ReportType = Literal["annual", "semiannual", "q1", "q3"]

_CST = timezone(timedelta(hours=8))

_CATEGORY_MAP: dict[str, str] = {
    "annual": "category_ndbg_szsh",
    "semiannual": "category_bndbg_szsh",
    "q1": "category_yjdbg_szsh",
    "q3": "category_sjdbg_szsh",
}

_VALID_COLUMNS = {"szse", "sse", "bj"}

_PLATE_TO_COLUMN: dict[str, str] = {
    "szse": "szse",
    "sse": "sse",
    "bj": "bj",
}

_STATIC_HOST = "static.cninfo.com.cn"
_STATIC_BASE = f"https://{_STATIC_HOST}"

def _infer_plate_from_code(code: str) -> str:
    """Infer the exchange plate from the A-share stock code prefix when the
    API doesn't return one. Returns "" for unknown prefixes."""
    if not code or not code.isdigit():
        return ""
    if code.startswith(("60", "68", "90")):
        return "sse"
    if code.startswith(("00", "30")):
        return "szse"
    if code.startswith(("43", "83", "87", "88", "89", "92")):
        return "bj"
    return ""


_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "Origin": "http://www.cninfo.com.cn",
}


class CninfoClient:
    """Async client for 巨潮资讯网 (cninfo.com.cn) public disclosure APIs.

    No authentication required — endpoints serve public announcements.
    """

    _BASE_URL = "http://www.cninfo.com.cn"
    _SEARCH_PATH = "/new/information/topSearch/detailOfQuery"
    _QUERY_PATH = "/new/hisAnnouncement/query"

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def _post(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, data=data, headers=_DEFAULT_HEADERS)
            response.raise_for_status()
            return response.json()

    async def _download(self, url: str, target: Path) -> int:
        # Redirects are disabled to prevent SSRF via 3xx redirects to other
        # hosts. The caller is expected to pass the final static.cninfo.com.cn
        # URL directly; if cninfo ever issues a 3xx we raise instead of
        # silently following it.
        total = 0
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            async with client.stream(
                "GET",
                url,
                headers={"User-Agent": _DEFAULT_HEADERS["User-Agent"]},
            ) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location", "")
                    raise ValueError(
                        f"Refusing to follow redirect during download "
                        f"(HTTP {response.status_code} → {location!r})"
                    )
                response.raise_for_status()
                with open(target, "wb") as fh:
                    async for chunk in response.aiter_bytes():
                        fh.write(chunk)
                        total += len(chunk)
        return total

    async def search_company(self, keyword: str, *, max_results: int = 10) -> list[CninfoStock]:
        """Search for listed companies by code, name pinyin, or Chinese name."""
        payload = await self._post(
            self._SEARCH_PATH,
            data={
                "keyWord": keyword,
                "maxSecNum": max_results,
                "maxListCount": 5,
            },
        )
        items = payload.get("keyBoardList") or []
        return [self._parse_stock(item) for item in items]

    async def list_reports(
        self,
        *,
        code: str,
        org_id: str,
        report_type: ReportType,
        plate: str | None = None,
        column: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 30,
    ) -> CninfoReportList:
        """List periodic reports (年报/半年报/一季报/三季报) for a stock.

        Either `plate` (from search result) or `column` must be provided.
        """
        category = _CATEGORY_MAP.get(report_type)
        if not category:
            raise ValueError(
                f"Invalid report_type {report_type!r}. "
                f"Allowed: {sorted(_CATEGORY_MAP)}"
            )
        if page < 1:
            raise ValueError(f"page must be >= 1, got {page}")
        if page_size < 1:
            raise ValueError(f"page_size must be >= 1, got {page_size}")

        resolved_column = self._resolve_column(column=column, plate=plate)

        # cninfo's API rejects single-sided ranges like "2023-01-01~" (returns
        # 0 hits). When only one bound is given, fill the other with a sane
        # default so the user's intent ("since X" / "until Y") is preserved.
        se_date = ""
        if start_date or end_date:
            effective_start = start_date or "1990-01-01"
            effective_end = end_date or datetime.now(_CST).strftime("%Y-%m-%d")
            se_date = f"{effective_start}~{effective_end}"

        body: dict[str, Any] = {
            "pageNum": page,
            "pageSize": page_size,
            "column": resolved_column,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": category,
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }

        data = await self._post(self._QUERY_PATH, data=body)
        announcements = data.get("announcements") or []
        items = [self._parse_report(item) for item in announcements]
        total = int(data.get("totalAnnouncement") or 0)
        has_more = page * page_size < total

        return CninfoReportList(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    async def download_report(self, adjunct_url_or_full: str, out_path: Path | str) -> int:
        """Download a report PDF. Accepts either the relative `adjunctUrl`
        (e.g. `finalpage/2025-03-15/X.PDF`) or a full URL on
        `static.cninfo.com.cn`. Returns bytes written.

        SSRF guard: any other host is rejected.
        """
        url = self._build_static_url(adjunct_url_or_full)
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        return await self._download(url, target)

    @staticmethod
    def _resolve_column(*, column: str | None, plate: str | None) -> str:
        if column:
            if column not in _VALID_COLUMNS:
                raise ValueError(
                    f"Invalid column {column!r}. Allowed: {sorted(_VALID_COLUMNS)}"
                )
            return column
        if not plate:
            raise ValueError("Either plate or column must be provided")
        mapped = _PLATE_TO_COLUMN.get(plate)
        if not mapped:
            raise ValueError(
                f"Unknown plate {plate!r}. Expected one of {sorted(_PLATE_TO_COLUMN)}"
            )
        return mapped

    @staticmethod
    def _build_static_url(adjunct_url_or_full: str) -> str:
        if adjunct_url_or_full.startswith(("http://", "https://")):
            parsed = urlparse(adjunct_url_or_full)
            if parsed.hostname != _STATIC_HOST:
                raise ValueError(
                    f"Downloads only allowed from {_STATIC_HOST}, "
                    f"got: {parsed.hostname!r}"
                )
            if parsed.scheme == "http":
                # Force HTTPS to avoid MITM on the response body.
                return "https://" + adjunct_url_or_full[len("http://"):]
            return adjunct_url_or_full
        return f"{_STATIC_BASE}/{adjunct_url_or_full.lstrip('/')}"

    @staticmethod
    def _parse_stock(item: dict[str, Any]) -> CninfoStock:
        raw_delisted = item.get("delisted")
        delisted = (
            raw_delisted.lower() == "true"
            if isinstance(raw_delisted, str)
            else bool(raw_delisted)
        )
        code = str(item.get("code") or "")
        plate = str(item.get("plate") or "") or _infer_plate_from_code(code)
        return CninfoStock(
            code=code,
            org_id=str(item.get("orgId") or ""),
            name=str(item.get("zwjc") or ""),
            plate=plate,
            listing_category=item.get("category") or None,
            pinyin=item.get("pinyin") or None,
            delisted=delisted,
        )

    @staticmethod
    def _parse_report(item: dict[str, Any]) -> CninfoReport:
        # cninfo announcementTime is epoch ms in UTC, but disclosures are
        # filed in Beijing time — present them as Asia/Shanghai (UTC+8) so the
        # date displays match what users see on cninfo.com.cn.
        ts_ms = item.get("announcementTime") or 0
        time_value = datetime.fromtimestamp(int(ts_ms) / 1000, tz=_CST)
        return CninfoReport(
            code=str(item.get("secCode") or ""),
            name=str(item.get("secName") or ""),
            org_id=str(item.get("orgId") or ""),
            announcement_id=str(item.get("announcementId") or ""),
            title=str(item.get("announcementTitle") or ""),
            time=time_value,
            adjunct_url=str(item.get("adjunctUrl") or ""),
            adjunct_size=item.get("adjunctSize"),
            adjunct_type=item.get("adjunctType"),
        )
