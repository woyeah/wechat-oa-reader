# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from wechat_oa_reader.auth import load_credentials, save_credentials
from wechat_oa_reader.models import Credentials


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


def test_save_and_load_credentials(tmp_path) -> None:
    env_path = tmp_path / ".env"
    creds = Credentials(
        token="token-x",
        cookie="cookie-x",
        fakeid="fakeid-x",
        nickname="nick-x",
        expire_time=123456,
    )
    save_credentials(creds, path=env_path)
    loaded = load_credentials(path=env_path)
    assert loaded is not None
    assert loaded.model_dump() == creds.model_dump()


def test_load_credentials_no_file(tmp_path) -> None:
    assert load_credentials(path=tmp_path / ".env") is None


def test_load_credentials_empty_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_TOKEN", raising=False)
    monkeypatch.delenv("WECHAT_COOKIE", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("WECHAT_TOKEN=\nWECHAT_COOKIE=cookie\n", encoding="utf-8")
    assert load_credentials(path=env_path) is None


def test_save_credentials_creates_file(tmp_path) -> None:
    env_path = tmp_path / ".env"
    assert not env_path.exists()
    save_credentials(Credentials(token="t", cookie="c"), path=env_path)
    assert env_path.exists()
    content = Path(env_path).read_text(encoding="utf-8")
    assert "WECHAT_TOKEN='t'" in content
