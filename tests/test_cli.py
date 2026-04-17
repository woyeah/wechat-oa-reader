# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from click.testing import CliRunner

from wechat_oa_reader import __version__
from wechat_oa_reader.cli import cli
from wechat_oa_reader.models import Credentials


def test_status_no_credentials(monkeypatch) -> None:
    monkeypatch.setattr("wechat_oa_reader.cli.load_credentials", lambda: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "Not authenticated" in result.output


def test_status_with_credentials(monkeypatch) -> None:
    async def _check_auth(self) -> bool:
        return True

    creds = Credentials(token="t", cookie="c", nickname="nick", fakeid="f", expire_time=123)
    monkeypatch.setattr("wechat_oa_reader.cli.load_credentials", lambda: creds)
    monkeypatch.setattr("wechat_oa_reader.cli.WeChatClient.check_auth", _check_auth)
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert '"nickname": "nick"' in result.output
    assert '"live_check": "valid"' in result.output


def test_status_with_credentials_no_live(monkeypatch) -> None:
    class _UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("WeChatClient should not be instantiated when --no-live is set")

    creds = Credentials(token="t", cookie="c", nickname="nick", fakeid="f", expire_time=123)
    monkeypatch.setattr("wechat_oa_reader.cli.load_credentials", lambda: creds)
    monkeypatch.setattr("wechat_oa_reader.cli.WeChatClient", _UnexpectedClient)

    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--no-live"])
    assert result.exit_code == 0
    assert '"nickname": "nick"' in result.output
    assert '"live_check"' not in result.output


def test_status_with_credentials_live_expired(monkeypatch) -> None:
    async def _check_auth(self) -> bool:
        return False

    creds = Credentials(token="t", cookie="c", nickname="nick", fakeid="f", expire_time=123)
    monkeypatch.setattr("wechat_oa_reader.cli.load_credentials", lambda: creds)
    monkeypatch.setattr("wechat_oa_reader.cli.WeChatClient.check_auth", _check_auth)

    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert '"live_check": "expired"' in result.output


def test_login_manual(monkeypatch) -> None:
    captured: dict[str, Credentials] = {}

    def _save(creds: Credentials) -> None:
        captured["creds"] = creds

    monkeypatch.setattr("wechat_oa_reader.cli.save_credentials", _save)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["login", "--manual", "--token", "token-x", "--cookie", "cookie-x", "--fakeid", "f1", "--nickname", "n1"],
    )
    assert result.exit_code == 0
    assert "Credentials saved to .env" in result.output
    assert captured["creds"].token == "token-x"
    assert captured["creds"].cookie == "cookie-x"
    assert captured["creds"].fakeid == "f1"
    assert captured["creds"].nickname == "n1"


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
