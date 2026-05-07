# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from click.testing import CliRunner

from wechat_oa_reader import __version__
from wechat_oa_reader.cli import cli
from wechat_oa_reader.models import ArticleContent, Credentials


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


def test_fetch_single_url_docx_inferred_from_output(monkeypatch, tmp_path) -> None:
    article = ArticleContent(
        url="https://mp.weixin.qq.com/s/one",
        title="One",
        author="Author",
        publish_time=0,
        html="<p><img data-src='https://img.example.com/1.png' /></p>",
        plain_text="",
        images=["https://img.example.com/1.png"],
    )

    class _Client:
        async def fetch_article(self, url: str):
            assert url == "https://mp.weixin.qq.com/s/one"
            return article

    captured: dict[str, object] = {}

    async def _fake_article_to_docx(
        payload: ArticleContent,
        output_path,
        *,
        http_client=None,
    ):
        captured["article"] = payload
        captured["output_path"] = output_path
        captured["http_client"] = http_client
        output_path.write_bytes(b"docx")
        return output_path

    monkeypatch.setattr("wechat_oa_reader.cli._load_client_or_exit", lambda: _Client())
    monkeypatch.setattr("wechat_oa_reader.cli.article_to_docx", _fake_article_to_docx)

    runner = CliRunner()
    output_path = tmp_path / "single.docx"
    result = runner.invoke(cli, ["fetch", "https://mp.weixin.qq.com/s/one", "-o", str(output_path)])

    assert result.exit_code == 0
    assert output_path.exists()
    assert captured["article"] is article
    assert captured["output_path"] == output_path
    assert captured["http_client"] is None


def test_fetch_batch_docx_writes_one_file_per_url(monkeypatch, tmp_path) -> None:
    urls = [
        "https://mp.weixin.qq.com/s/a",
        "https://mp.weixin.qq.com/s/b",
    ]
    batch_file = tmp_path / "urls.txt"
    batch_file.write_text("\n".join(urls), encoding="utf-8")

    articles = [
        ArticleContent(
            url=urls[0],
            title='A<>:"/\\|?*B',
            author=None,
            publish_time=0,
            html="<p>one</p>",
            plain_text="one",
            images=[],
        ),
        ArticleContent(
            url=urls[1],
            title=" ",
            author=None,
            publish_time=0,
            html="<p>two</p>",
            plain_text="two",
            images=[],
        ),
    ]

    class _Client:
        async def fetch_articles(self, value: list[str]):
            assert value == urls
            return articles

    written_paths = []

    async def _fake_article_to_docx(
        payload: ArticleContent,
        output_path,
        *,
        http_client=None,
    ):
        written_paths.append((payload.url, output_path))
        output_path.write_bytes(b"docx")
        return output_path

    monkeypatch.setattr("wechat_oa_reader.cli._load_client_or_exit", lambda: _Client())
    monkeypatch.setattr("wechat_oa_reader.cli.article_to_docx", _fake_article_to_docx)

    output_dir = tmp_path / "docx-outputs"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["fetch", "--batch", str(batch_file), "-o", str(output_dir), "--format", "docx"],
    )

    assert result.exit_code == 0
    assert output_dir.is_dir()
    assert len(written_paths) == 2
    assert {path.name for _, path in written_paths} == {"AB.docx", "article_2.docx"}
    assert all(path.exists() for _, path in written_paths)
