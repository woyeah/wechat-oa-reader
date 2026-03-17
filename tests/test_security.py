# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for security hardening fixes."""
from __future__ import annotations

import os
import shutil
import stat
import sys
import threading
import warnings
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from wechat_oa_reader.proxy import ProxyPool


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    root = Path.cwd() / "test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# === 1. auth.py: temp file permissions + QR poll timeout ===


class TestAuthTempFilePermissions:
    """Temp session file should have restrictive permissions (owner-only)."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions not applicable on Windows")
    @pytest.mark.asyncio
    async def test_session_file_permissions(self):
        """Session file created by start_qrcode_login should be mode 0o600."""
        from wechat_oa_reader.auth import start_qrcode_login

        fake_qr = b"\x89PNG\r\n\x1a\n"  # fake PNG header
        fake_cookies = {"uuid": "abc", "slave_sid": "xyz"}

        mock_response_qr = AsyncMock()
        mock_response_qr.content = fake_qr
        mock_response_qr.raise_for_status = lambda: None

        mock_response_login = AsyncMock()
        mock_response_login.raise_for_status = lambda: None

        with patch("wechat_oa_reader.auth.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.cookies = fake_cookies
            mock_client.post = AsyncMock(return_value=mock_response_login)
            mock_client.get = AsyncMock(return_value=mock_response_qr)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            _, session_path = await start_qrcode_login()
            try:
                mode = stat.S_IMODE(os.stat(session_path).st_mode)
                assert mode & stat.S_IROTH == 0, "Session file should not be world-readable"
                assert mode & stat.S_IWOTH == 0, "Session file should not be world-writable"
                assert mode & stat.S_IRGRP == 0, "Session file should not be group-readable"
            finally:
                Path(session_path).unlink(missing_ok=True)


class TestQrPollTimeout:
    """QR polling loop should have a total timeout."""

    @pytest.mark.asyncio
    async def test_qr_poll_total_timeout(self, tmp_path):
        """complete_qrcode_login should raise TimeoutError if total timeout exceeded."""
        import json

        from wechat_oa_reader.auth import complete_qrcode_login

        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"cookies": {"uuid": "test"}}), encoding="utf-8")

        # Always return status=0 (waiting) so the loop never finishes
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"status": 0}

        with patch("wechat_oa_reader.auth.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch("wechat_oa_reader.auth.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(TimeoutError, match="[Tt]imeout|[Ee]xpir"):
                    await complete_qrcode_login(str(session_path), timeout=0.1)


# === 2. store.py: thread-safe SQLite ===


class TestStoreThreadSafety:
    """ArticleStore should use thread-safe SQLite access."""

    def test_concurrent_writes(self, tmp_path):
        """Concurrent writes from multiple threads should not corrupt data."""
        from wechat_oa_reader.models import Account
        from wechat_oa_reader.store import ArticleStore

        store = ArticleStore(str(tmp_path / "test.db"))
        account = Account(fakeid="thread-test", nickname="ThreadTest")
        store.save_account(account)

        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(20):
                    store.save_articles(
                        "thread-test",
                        [{"aid": f"t{thread_id}-{i}", "title": f"T{i}",
                          "link": f"https://example.com/{thread_id}/{i}", "publish_time": i}],
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        articles = store.get_articles("thread-test", limit=1000)
        assert len(articles) == 80  # 4 threads * 20 articles each


# === 3. fetcher.py: specific exceptions + SSL warning ===


class TestFetcherExceptions:
    """Fetcher should catch specific exceptions, not bare Exception."""

    @pytest.mark.asyncio
    async def test_proxy_failure_catches_network_errors(self):
        """Proxy retry should handle network errors specifically."""
        from wechat_oa_reader.fetcher import Fetcher
        from wechat_oa_reader.proxy import ProxyPool

        pool = ProxyPool(["http://bad-proxy:1234"])
        fetcher = Fetcher(proxy_pool=pool)

        # Should handle httpx errors gracefully and fall through to direct fetch
        with patch.object(fetcher, "_do_fetch", side_effect=[
            httpx.ConnectError("connection refused"),  # proxy fails
            "<div id='js_content'>ok</div>",  # direct succeeds
        ]):
            result = await fetcher.fetch_page("https://example.com")
            assert result == "<div id='js_content'>ok</div>"

    @pytest.mark.asyncio
    async def test_fetch_article_catches_network_errors(self):
        """fetch_article should return None on network errors, not swallow all exceptions."""
        from wechat_oa_reader.fetcher import Fetcher

        fetcher = Fetcher()

        with patch.object(fetcher, "_do_fetch", side_effect=httpx.ConnectError("fail")):
            result = await fetcher.fetch_article("https://example.com/article")
            assert result is None


class TestFetcherSslWarning:
    """Fetcher should warn when SSL verification is disabled."""

    def test_ssl_disabled_warns(self):
        """Creating Fetcher with verify_ssl=False should emit a warning."""
        from wechat_oa_reader.fetcher import Fetcher

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Fetcher(verify_ssl=False)
            ssl_warnings = [x for x in w if "SSL" in str(x.message) or "ssl" in str(x.message)]
            assert len(ssl_warnings) >= 1, "Should warn when SSL verification is disabled"

    def test_ssl_enabled_no_warning(self):
        """Creating Fetcher with verify_ssl=True should not warn."""
        from wechat_oa_reader.fetcher import Fetcher

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Fetcher(verify_ssl=True)
            ssl_warnings = [x for x in w if "SSL" in str(x.message) or "ssl" in str(x.message)]
            assert len(ssl_warnings) == 0


# === 4. cli.py: batch URL validation ===


class TestBatchUrlValidation:
    """Batch file URLs should be validated."""

    def test_invalid_url_scheme_rejected(self):
        """URLs with non-http(s) schemes should be rejected."""
        from wechat_oa_reader.cli import _validate_urls

        with pytest.raises(click.BadParameter):
            _validate_urls(["ftp://evil.com/file", "https://mp.weixin.qq.com/s?a=1"])

    def test_valid_urls_accepted(self):
        from wechat_oa_reader.cli import _validate_urls

        # Should not raise
        result = _validate_urls([
            "https://mp.weixin.qq.com/s?a=1",
            "http://mp.weixin.qq.com/s?a=2",
        ])
        assert len(result) == 2

    def test_empty_urls_filtered(self):
        from wechat_oa_reader.cli import _validate_urls

        result = _validate_urls(["https://example.com", "", "  "])
        assert len(result) == 1

    def test_javascript_scheme_rejected(self):
        from wechat_oa_reader.cli import _validate_urls

        with pytest.raises(click.BadParameter):
            _validate_urls(["javascript:alert(1)"])

    def test_file_scheme_rejected(self):
        from wechat_oa_reader.cli import _validate_urls

        with pytest.raises(click.BadParameter):
            _validate_urls(["file:///etc/passwd"])


# === 5. proxy.py: URL validation ===


class TestProxyValidation:
    """ProxyPool should validate proxy URL formats."""

    def test_valid_http_proxy(self):
        pool = ProxyPool(["http://proxy:8080"])
        assert pool.count == 1

    def test_valid_https_proxy(self):
        pool = ProxyPool(["https://proxy:8443"])
        assert pool.count == 1

    def test_valid_socks5_proxy(self):
        pool = ProxyPool(["socks5://proxy:1080"])
        assert pool.count == 1

    def test_invalid_scheme_rejected(self):
        with pytest.raises(ValueError, match="[Ss]cheme|[Pp]roxy"):
            ProxyPool(["ftp://proxy:21"])

    def test_no_scheme_rejected(self):
        with pytest.raises(ValueError, match="[Ss]cheme|[Pp]roxy"):
            ProxyPool(["just-a-hostname:8080"])

    def test_empty_list_ok(self):
        pool = ProxyPool([])
        assert pool.count == 0

    def test_none_ok(self):
        pool = ProxyPool(None)
        assert pool.count == 0


# Need click import for the CLI test
import click
