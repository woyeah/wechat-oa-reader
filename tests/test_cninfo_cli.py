# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from wechat_oa_reader.cli import cli
from wechat_oa_reader.cninfo import CninfoClient
from wechat_oa_reader.models import CninfoReport, CninfoReportList, CninfoStock


def _stock() -> CninfoStock:
    return CninfoStock(
        code="000001",
        org_id="gssz0000001",
        name="平安银行",
        plate="szse",
        listing_category="A股",
    )


def _report_list(total: int = 2) -> CninfoReportList:
    return CninfoReportList(
        items=[
            CninfoReport(
                code="000001",
                name="平安银行",
                org_id="gssz0000001",
                announcement_id="1222806505",
                title="2024年年度报告",
                time=datetime(2025, 3, 15, 0, 0, 0, tzinfo=timezone.utc),
                adjunct_url="finalpage/2025-03-15/1222806505.PDF",
                adjunct_size=1901,
                adjunct_type="PDF",
            )
        ],
        total=total,
        page=1,
        page_size=30,
        has_more=False,
    )


def test_cninfo_search(monkeypatch) -> None:
    async def _search(self, query, max_results=10):
        return [_stock()]

    monkeypatch.setattr(CninfoClient, "search_company", _search)
    runner = CliRunner()
    result = runner.invoke(cli, ["cninfo", "search", "平安"])
    assert result.exit_code == 0
    assert '"code": "000001"' in result.output
    assert '"plate": "szse"' in result.output


def test_cninfo_reports_with_org_id(monkeypatch) -> None:
    async def _list(self, **kwargs):
        assert kwargs["code"] == "000001"
        assert kwargs["org_id"] == "gssz0000001"
        assert kwargs["report_type"] == "annual"
        assert kwargs["plate"] == "szse"
        return _report_list()

    monkeypatch.setattr(CninfoClient, "list_reports", _list)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "cninfo",
            "reports",
            "000001",
            "--org-id",
            "gssz0000001",
            "--plate",
            "szse",
            "--type",
            "annual",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"announcement_id": "1222806505"' in result.output
    assert '"total": 2' in result.output


def test_cninfo_reports_auto_resolve_org_id(monkeypatch) -> None:
    """When --org-id is not given, run search_company first to resolve it."""

    async def _search(self, query, max_results=10):
        assert query == "000001"
        return [_stock()]

    async def _list(self, **kwargs):
        assert kwargs["code"] == "000001"
        assert kwargs["org_id"] == "gssz0000001"
        assert kwargs["plate"] == "szse"
        return _report_list()

    monkeypatch.setattr(CninfoClient, "search_company", _search)
    monkeypatch.setattr(CninfoClient, "list_reports", _list)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["cninfo", "reports", "000001", "--type", "semiannual"]
    )
    assert result.exit_code == 0, result.output


def test_cninfo_reports_auto_resolve_no_match(monkeypatch) -> None:
    async def _search(self, query, max_results=10):
        return []

    monkeypatch.setattr(CninfoClient, "search_company", _search)
    runner = CliRunner()
    result = runner.invoke(cli, ["cninfo", "reports", "999999", "--type", "annual"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no match" in result.output.lower()


def test_cninfo_reports_date_range(monkeypatch) -> None:
    captured = {}

    async def _list(self, **kwargs):
        captured.update(kwargs)
        return _report_list()

    monkeypatch.setattr(CninfoClient, "list_reports", _list)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "cninfo",
            "reports",
            "000001",
            "--org-id",
            "gssz0000001",
            "--plate",
            "szse",
            "--type",
            "annual",
            "--since",
            "2020-01-01",
            "--until",
            "2025-12-31",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["start_date"] == "2020-01-01"
    assert captured["end_date"] == "2025-12-31"


def test_cninfo_download(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "report.pdf"

    async def _download(self, url, out_path):
        Path(out_path).write_bytes(b"ok-pdf")
        return 6

    monkeypatch.setattr(CninfoClient, "download_report", _download)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "cninfo",
            "download",
            "finalpage/2025-03-15/X.PDF",
            "-o",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    assert target.exists()
    assert '"size": 6' in result.output or '"saved"' in result.output


def test_cninfo_download_default_filename(monkeypatch, tmp_path: Path) -> None:
    """Without -o, derive filename from the adjunct_url basename."""
    monkeypatch.chdir(tmp_path)

    async def _download(self, url, out_path):
        Path(out_path).write_bytes(b"data")
        return 4

    monkeypatch.setattr(CninfoClient, "download_report", _download)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["cninfo", "download", "finalpage/2025-03-15/REPORT.PDF"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "REPORT.PDF").exists()
