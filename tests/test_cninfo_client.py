# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from wechat_oa_reader.cninfo import CninfoClient
from wechat_oa_reader.models import CninfoReport, CninfoReportList, CninfoStock


def _search_payload() -> dict:
    return {
        "keyBoardList": [
            {
                "code": "000001",
                "orgId": "gssz0000001",
                "zwjc": "平安银行",
                "plate": "szse",
                "category": "A股",
                "pinyin": "payh",
                "delisted": "false",
                "type": "shj",
                "sjstsBond": "false",
            },
            {
                "code": "600519",
                "orgId": "gssh0600519",
                "zwjc": "贵州茅台",
                "plate": "sse",
                "category": "A股",
                "pinyin": "gzmt",
                "delisted": "false",
                "type": "shj",
                "sjstsBond": "false",
            },
        ],
        "classifiedAnnouncements": [],
    }


def _announcements_payload(total: int = 2) -> dict:
    return {
        "totalAnnouncement": total,
        "totalRecordNum": total,
        "totalSecurities": 0,
        "classifiedAnnouncements": None,
        "announcements": [
            {
                "secCode": "000001",
                "secName": "平安银行",
                "orgId": "gssz0000001",
                "announcementId": "1222806505",
                "announcementTitle": "2024年年度报告",
                "announcementTime": 1741968000000,
                "adjunctUrl": "finalpage/2025-03-15/1222806505.PDF",
                "adjunctSize": 1901,
                "adjunctType": "PDF",
            },
            {
                "secCode": "000001",
                "secName": "平安银行",
                "orgId": "gssz0000001",
                "announcementId": "1219306493",
                "announcementTitle": "2023年年度报告",
                "announcementTime": 1710432000000,
                "adjunctUrl": "finalpage/2024-03-15/1219306493.PDF",
                "adjunctSize": 1700,
                "adjunctType": "PDF",
            },
        ],
    }


def test_cninfo_client_init() -> None:
    client = CninfoClient()
    assert client is not None


@pytest.mark.asyncio
async def test_search_company_returns_stocks() -> None:
    client = CninfoClient()

    with patch.object(client, "_post", new=AsyncMock(return_value=_search_payload())):
        stocks = await client.search_company("平安")

    assert len(stocks) == 2
    assert all(isinstance(s, CninfoStock) for s in stocks)
    first = stocks[0]
    assert first.code == "000001"
    assert first.org_id == "gssz0000001"
    assert first.name == "平安银行"
    assert first.plate == "szse"
    assert first.listing_category == "A股"
    assert first.pinyin == "payh"
    assert first.delisted is False
    assert stocks[1].plate == "sse"
    assert stocks[1].code == "600519"


@pytest.mark.asyncio
async def test_search_company_handles_missing_keyboardlist() -> None:
    client = CninfoClient()

    with patch.object(client, "_post", new=AsyncMock(return_value={"keyBoardList": None})):
        stocks = await client.search_company("nothing")

    assert stocks == []

    with patch.object(client, "_post", new=AsyncMock(return_value={})):
        stocks = await client.search_company("nothing")

    assert stocks == []


@pytest.mark.asyncio
async def test_search_company_passes_keyword() -> None:
    client = CninfoClient()

    with patch.object(client, "_post", new=AsyncMock(return_value=_search_payload())) as mock_post:
        await client.search_company("平安")

    call = mock_post.await_args
    assert call.args[0].endswith("/new/information/topSearch/detailOfQuery")
    body = call.kwargs["data"]
    assert body["keyWord"] == "平安"


@pytest.mark.asyncio
async def test_search_company_delisted_true() -> None:
    payload = {
        "keyBoardList": [
            {
                "code": "835185",
                "orgId": "gfbj0835185",
                "zwjc": "贝特瑞",
                "plate": "bj",
                "category": "A股",
                "pinyin": "btr",
                "delisted": "true",
            }
        ]
    }
    client = CninfoClient()
    with patch.object(client, "_post", new=AsyncMock(return_value=payload)):
        stocks = await client.search_company("贝特瑞")

    assert stocks[0].delisted is True
    assert stocks[0].plate == "bj"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,expected_plate",
    [
        ("000001", "szse"),
        ("001359", "szse"),
        ("002594", "szse"),
        ("300750", "szse"),
        ("600519", "sse"),
        ("688981", "sse"),
        ("430047", "bj"),
        ("835185", "bj"),
        ("873169", "bj"),
        ("920028", "bj"),
        ("921001", "bj"),
    ],
)
async def test_search_company_infers_plate_from_code_when_missing(
    code: str, expected_plate: str
) -> None:
    """When the API omits `plate`, infer it from the stock code prefix."""
    payload = {
        "keyBoardList": [
            {
                "code": code,
                "orgId": "x",
                "zwjc": "test",
                "category": "A股",
                # plate intentionally absent
            }
        ]
    }
    client = CninfoClient()
    with patch.object(client, "_post", new=AsyncMock(return_value=payload)):
        stocks = await client.search_company(code)

    assert stocks[0].plate == expected_plate


@pytest.mark.asyncio
async def test_list_reports_annual_basic() -> None:
    client = CninfoClient()

    with patch.object(
        client, "_post", new=AsyncMock(return_value=_announcements_payload(total=2))
    ) as mock_post:
        result = await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
        )

    assert isinstance(result, CninfoReportList)
    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 30
    assert result.has_more is False
    assert len(result.items) == 2

    first = result.items[0]
    assert isinstance(first, CninfoReport)
    assert first.code == "000001"
    assert first.name == "平安银行"
    assert first.org_id == "gssz0000001"
    assert first.announcement_id == "1222806505"
    assert first.title == "2024年年度报告"
    assert first.adjunct_url == "finalpage/2025-03-15/1222806505.PDF"
    assert first.adjunct_size == 1901
    assert first.adjunct_type == "PDF"
    assert isinstance(first.time, datetime)
    cst = timezone(timedelta(hours=8))
    expected = datetime.fromtimestamp(1741968000, tz=cst)
    assert first.time == expected
    assert first.time.utcoffset() == timedelta(hours=8)
    # Smoke check: in CST the date should be 2025-03-15, not 2025-03-14 (UTC)
    assert first.time.date().isoformat() == "2025-03-15"

    call_body = mock_post.await_args.kwargs["data"]
    assert call_body["category"] == "category_ndbg_szsh"
    assert call_body["column"] == "szse"
    assert call_body["stock"] == "000001,gssz0000001"
    assert call_body["tabName"] == "fulltext"
    assert call_body["pageNum"] == 1
    assert call_body["pageSize"] == 30
    assert call_body["isHLtitle"] == "true"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_type,expected_category",
    [
        ("annual", "category_ndbg_szsh"),
        ("semiannual", "category_bndbg_szsh"),
        ("q1", "category_yjdbg_szsh"),
        ("q3", "category_sjdbg_szsh"),
    ],
)
async def test_list_reports_category_mapping(
    report_type: str, expected_category: str
) -> None:
    client = CninfoClient()
    with patch.object(
        client, "_post", new=AsyncMock(return_value=_announcements_payload(0))
    ) as mock_post:
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type=report_type,
            plate="szse",
        )

    assert mock_post.await_args.kwargs["data"]["category"] == expected_category


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plate,expected_column",
    [("szse", "szse"), ("sse", "sse"), ("bj", "bj")],
)
async def test_list_reports_plate_to_column_mapping(
    plate: str, expected_column: str
) -> None:
    client = CninfoClient()
    with patch.object(
        client, "_post", new=AsyncMock(return_value=_announcements_payload(0))
    ) as mock_post:
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate=plate,
        )

    assert mock_post.await_args.kwargs["data"]["column"] == expected_column


@pytest.mark.asyncio
async def test_list_reports_explicit_column_overrides_plate() -> None:
    client = CninfoClient()
    with patch.object(
        client, "_post", new=AsyncMock(return_value=_announcements_payload(0))
    ) as mock_post:
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            column="sse",
        )

    assert mock_post.await_args.kwargs["data"]["column"] == "sse"


@pytest.mark.asyncio
async def test_list_reports_with_date_range() -> None:
    client = CninfoClient()
    with patch.object(
        client, "_post", new=AsyncMock(return_value=_announcements_payload(0))
    ) as mock_post:
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            start_date="2023-01-01",
            end_date="2025-12-31",
        )

    assert mock_post.await_args.kwargs["data"]["seDate"] == "2023-01-01~2025-12-31"


@pytest.mark.asyncio
async def test_list_reports_pagination_and_has_more() -> None:
    client = CninfoClient()
    payload = _announcements_payload(total=25)
    with patch.object(
        client, "_post", new=AsyncMock(return_value=payload)
    ) as mock_post:
        result = await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            page=2,
            page_size=10,
        )

    body = mock_post.await_args.kwargs["data"]
    assert body["pageNum"] == 2
    assert body["pageSize"] == 10
    assert result.page == 2
    assert result.page_size == 10
    assert result.total == 25
    assert result.has_more is True

    with patch.object(
        client, "_post", new=AsyncMock(return_value=payload)
    ):
        result = await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            page=3,
            page_size=10,
        )
    assert result.has_more is False


@pytest.mark.asyncio
async def test_list_reports_handles_null_announcements() -> None:
    client = CninfoClient()
    payload = {"announcements": None, "totalAnnouncement": 0}
    with patch.object(client, "_post", new=AsyncMock(return_value=payload)):
        result = await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
        )

    assert result.items == []
    assert result.total == 0
    assert result.has_more is False


@pytest.mark.asyncio
async def test_list_reports_invalid_report_type_raises() -> None:
    client = CninfoClient()
    with pytest.raises(ValueError, match="report_type"):
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="weekly",  # type: ignore[arg-type]
            plate="szse",
        )


@pytest.mark.asyncio
async def test_list_reports_requires_column_or_plate() -> None:
    client = CninfoClient()
    with pytest.raises(ValueError, match="plate|column"):
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
        )


@pytest.mark.asyncio
async def test_list_reports_rejects_zero_or_negative_page() -> None:
    client = CninfoClient()
    with pytest.raises(ValueError, match="page must be"):
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            page=0,
        )
    with pytest.raises(ValueError, match="page must be"):
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            page=-1,
        )


@pytest.mark.asyncio
async def test_list_reports_rejects_zero_or_negative_page_size() -> None:
    client = CninfoClient()
    with pytest.raises(ValueError, match="page_size must be"):
        await client.list_reports(
            code="000001",
            org_id="gssz0000001",
            report_type="annual",
            plate="szse",
            page_size=0,
        )


@pytest.mark.asyncio
async def test_download_uses_https_for_relative_url(tmp_path: Path) -> None:
    """Static cninfo URLs must be built over HTTPS to avoid MITM."""
    client = CninfoClient()
    captured: dict[str, str] = {}

    async def fake_download(url: str, target: Path) -> int:
        captured["url"] = url
        target.write_bytes(b"x")
        return 1

    with patch.object(client, "_download", new=AsyncMock(side_effect=fake_download)):
        await client.download_report("finalpage/2025-03-15/X.PDF", tmp_path / "out.pdf")

    assert captured["url"].startswith("https://static.cninfo.com.cn/")


@pytest.mark.asyncio
async def test_download_aborts_on_redirect(tmp_path: Path) -> None:
    """`_download` must refuse 3xx redirects to prevent SSRF via redirect."""
    client = CninfoClient()
    out = tmp_path / "out.pdf"

    class _StreamCtx:
        def __init__(self) -> None:
            self.status_code = 302
            self.headers = {"location": "http://evil.example.com/x"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def aiter_bytes(self):
            if False:
                yield b""

        def raise_for_status(self) -> None:
            pass

    class _ClientCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, headers=None):
            return _StreamCtx()

    with patch("wechat_oa_reader.cninfo.httpx.AsyncClient", return_value=_ClientCtx()):
        with pytest.raises(ValueError, match="redirect"):
            await client._download("https://static.cninfo.com.cn/finalpage/X.PDF", out)


@pytest.mark.asyncio
async def test_download_report_writes_file(tmp_path: Path) -> None:
    client = CninfoClient()
    out = tmp_path / "report.pdf"

    captured_url: dict[str, str] = {}

    async def fake_download(url: str, target: Path) -> int:
        captured_url["url"] = url
        target.write_bytes(b"%PDF-1.4 fake pdf content")
        return target.stat().st_size

    with patch.object(client, "_download", new=AsyncMock(side_effect=fake_download)):
        size = await client.download_report("finalpage/2025-03-15/X.PDF", out)

    assert out.exists()
    assert size == out.stat().st_size
    assert captured_url["url"] == "https://static.cninfo.com.cn/finalpage/2025-03-15/X.PDF"


@pytest.mark.asyncio
async def test_download_report_accepts_absolute_https_url(tmp_path: Path) -> None:
    client = CninfoClient()
    out = tmp_path / "report.pdf"

    captured_url: dict[str, str] = {}

    async def fake_download(url: str, target: Path) -> int:
        captured_url["url"] = url
        target.write_bytes(b"ok")
        return target.stat().st_size

    full = "https://static.cninfo.com.cn/finalpage/2025-03-15/X.PDF"
    with patch.object(client, "_download", new=AsyncMock(side_effect=fake_download)):
        await client.download_report(full, out)

    assert captured_url["url"] == full


@pytest.mark.asyncio
async def test_download_report_upgrades_http_to_https(tmp_path: Path) -> None:
    """An http:// URL on the allowed host gets transparently upgraded to https://."""
    client = CninfoClient()
    out = tmp_path / "report.pdf"

    captured_url: dict[str, str] = {}

    async def fake_download(url: str, target: Path) -> int:
        captured_url["url"] = url
        target.write_bytes(b"ok")
        return 2

    full_http = "http://static.cninfo.com.cn/finalpage/2025-03-15/X.PDF"
    with patch.object(client, "_download", new=AsyncMock(side_effect=fake_download)):
        await client.download_report(full_http, out)

    assert captured_url["url"] == "https://static.cninfo.com.cn/finalpage/2025-03-15/X.PDF"


@pytest.mark.asyncio
async def test_download_report_rejects_foreign_host(tmp_path: Path) -> None:
    client = CninfoClient()
    out = tmp_path / "report.pdf"

    with patch.object(client, "_download", new=AsyncMock()) as mock_dl:
        with pytest.raises(ValueError, match="static.cninfo.com.cn"):
            await client.download_report("http://evil.example.com/x.pdf", out)
        mock_dl.assert_not_awaited()
