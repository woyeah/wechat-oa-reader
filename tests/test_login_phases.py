# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from wechat_oa_reader import auth
from wechat_oa_reader.models import Credentials


class _FakeResponse:
    def __init__(
        self,
        *,
        json_data: dict | None = None,
        content: bytes = b"",
        text: str = "",
    ) -> None:
        self._json_data = json_data or {}
        self.content = content
        self.text = text

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        return None


def _mock_async_client(*, ask_status: int = 1, qr_bytes: bytes = b"fake_png") -> AsyncMock:
    client = AsyncMock()
    client.cookies = {"fake_cookie": "value"}

    async def _post(url: str, *args, **kwargs):
        action = (kwargs.get("params") or {}).get("action")
        if action == "startlogin":
            return _FakeResponse(json_data={"base_resp": {"ret": 0}})
        if action == "login":
            return _FakeResponse(
                json_data={"redirect_url": "/cgi-bin/home?t=home/index&token=12345&lang=zh_CN"}
            )
        raise AssertionError(f"Unexpected POST: {url} action={action}")

    async def _get(url: str, *args, **kwargs):
        action = (kwargs.get("params") or {}).get("action")
        if "scanloginqrcode" in url and action == "getqrcode":
            return _FakeResponse(content=qr_bytes)
        if "scanloginqrcode" in url and action == "ask":
            return _FakeResponse(json_data={"status": ask_status})
        if url.endswith("/cgi-bin/home"):
            return _FakeResponse(text='var nick_name = "Test Nick";')
        if url.endswith("/cgi-bin/searchbiz"):
            return _FakeResponse(json_data={"list": [{"nickname": "Test Nick", "fakeid": "fakeid-123"}]})
        raise AssertionError(f"Unexpected GET: {url} action={action}")

    client.post.side_effect = _post
    client.get.side_effect = _get

    cm = AsyncMock()
    cm.__aenter__.return_value = client
    cm.__aexit__.return_value = None
    return cm


def _load_login_script_module():
    script_path = Path(__file__).resolve().parents[1] / "plugins" / "wechat-oa-reader" / "skills" / "wechat-oa-reader" / "scripts" / "login.py"
    module_name = f"test_login_script_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_path() -> Path:
    root = Path.cwd() / "test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.asyncio
async def test_start_qrcode_login_returns_bytes_and_session_path() -> None:
    async_client_cm = _mock_async_client(ask_status=1, qr_bytes=b"phase1_png")

    with patch("wechat_oa_reader.auth.httpx.AsyncClient", return_value=async_client_cm):
        qr_bytes, session_path = await auth.start_qrcode_login()

    session_file = Path(session_path)
    try:
        assert isinstance(qr_bytes, bytes)
        assert qr_bytes == b"phase1_png"
        assert isinstance(session_path, str)
        assert session_file.exists()
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        assert "cookies" in payload
    finally:
        if session_file.exists():
            session_file.unlink()


@pytest.mark.asyncio
async def test_complete_qrcode_login_success(tmp_path: Path) -> None:
    session_file = tmp_path / "wechat-session.json"
    session_file.write_text(json.dumps({"cookies": {"fake_cookie": "value"}}), encoding="utf-8")

    async_client_cm = _mock_async_client(ask_status=1)

    with patch("wechat_oa_reader.auth.httpx.AsyncClient", return_value=async_client_cm):
        creds = await auth.complete_qrcode_login(str(session_file))

    assert isinstance(creds, Credentials)
    assert creds.token == "12345"
    assert creds.cookie == "fake_cookie=value"
    assert creds.nickname == "Test Nick"
    assert creds.fakeid == "fakeid-123"
    assert not session_file.exists()


@pytest.mark.asyncio
async def test_complete_qrcode_login_timeout(tmp_path: Path) -> None:
    session_file = tmp_path / "wechat-session-timeout.json"
    session_file.write_text(json.dumps({"cookies": {"fake_cookie": "value"}}), encoding="utf-8")

    async_client_cm = _mock_async_client(ask_status=2)

    with patch("wechat_oa_reader.auth.httpx.AsyncClient", return_value=async_client_cm):
        with pytest.raises(TimeoutError):
            await auth.complete_qrcode_login(str(session_file))


@pytest.mark.asyncio
async def test_login_with_qrcode_still_works_with_callback() -> None:
    callback = AsyncMock()
    async_client_cm = _mock_async_client(ask_status=1, qr_bytes=b"legacy_png")

    with patch("wechat_oa_reader.auth.httpx.AsyncClient", return_value=async_client_cm):
        creds = await auth.login_with_qrcode(on_qrcode=callback)

    callback.assert_awaited_once_with(b"legacy_png")
    assert creds.token == "12345"
    assert creds.cookie == "fake_cookie=value"
    assert creds.nickname == "Test Nick"
    assert creds.fakeid == "fakeid-123"


def test_login_script_start_mode(capsys) -> None:
    mock_start = AsyncMock(return_value=(b"fake_png", "/tmp/session.json"))
    with patch("wechat_oa_reader.auth.start_qrcode_login", new=mock_start, create=True):
        module = _load_login_script_module()
        module.main(["--start"])

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["phase"] == "start"
    assert "qr_path" in data
    assert "session_path" in data

    qr_path = Path(data["qr_path"])
    if qr_path.exists():
        qr_path.unlink()


def test_login_script_complete_mode(capsys) -> None:
    creds = Credentials(
        token="token-x",
        cookie="cookie-x",
        fakeid="fakeid-x",
        nickname="nick-x",
    )
    mock_complete = AsyncMock(return_value=creds)
    mock_save = MagicMock()

    with patch("wechat_oa_reader.auth.complete_qrcode_login", new=mock_complete, create=True), patch(
        "wechat_oa_reader.auth.save_credentials", new=mock_save
    ):
        module = _load_login_script_module()
        module.main(["--complete", "--session", "/tmp/session.json"])

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["mode"] == "qrcode"


def test_login_script_default_mode_unchanged(capsys) -> None:
    creds = Credentials(
        token="token-y",
        cookie="cookie-y",
        fakeid="fakeid-y",
        nickname="nick-y",
    )
    mock_login = AsyncMock(return_value=creds)
    mock_save = MagicMock()

    with patch("wechat_oa_reader.auth.login_with_qrcode", new=mock_login), patch(
        "wechat_oa_reader.auth.save_credentials", new=mock_save
    ):
        module = _load_login_script_module()
        module.main([])

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["mode"] == "qrcode"
