# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sqlite3
import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from wechat_oa_reader.models import Account
from wechat_oa_reader.store import ArticleStore


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


def _make_store(tmp_path) -> ArticleStore:
    return ArticleStore(str(tmp_path / "articles.db"))


def _make_account() -> Account:
    return Account(fakeid="fakeid-1", nickname="Nick", alias="alias-1", head_img="img", service_type=2)


def _save_base_account(store: ArticleStore) -> None:
    store.save_account(_make_account())


def _sample_articles() -> list[dict]:
    return [
        {"aid": "a1", "title": "T1", "link": "https://mp.weixin.qq.com/s?a=1", "publish_time": 100},
        {"aid": "a2", "title": "T2", "link": "https://mp.weixin.qq.com/s?a=2", "publish_time": 200},
    ]


def test_init_db(tmp_path) -> None:
    store = _make_store(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "articles.db"))
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        conn.close()
    assert "accounts" in tables
    assert "articles" in tables
    assert store is not None


def test_save_and_list_accounts(tmp_path) -> None:
    store = _make_store(tmp_path)
    account = _make_account()
    assert store.save_account(account) is True
    rows = store.list_accounts()
    assert len(rows) == 1
    assert rows[0]["fakeid"] == account.fakeid
    assert rows[0]["nickname"] == account.nickname


def test_save_account_upsert(tmp_path) -> None:
    store = _make_store(tmp_path)
    account = _make_account()
    store.save_account(account)

    conn = store._get_conn()
    try:
        conn.execute("UPDATE accounts SET last_poll = ? WHERE fakeid = ?", (123, account.fakeid))
        conn.commit()
    finally:
        conn.close()

    store.save_account(
        Account(
            fakeid=account.fakeid,
            nickname="Nick-New",
            alias="alias-2",
            head_img="img-2",
            service_type=1,
        )
    )
    updated = store.list_accounts()[0]
    assert updated["nickname"] == "Nick-New"
    assert updated["last_poll"] == 123


def test_remove_account(tmp_path) -> None:
    store = _make_store(tmp_path)
    _save_base_account(store)
    assert store.remove_account("fakeid-1") is True
    assert store.list_accounts() == []


def test_save_articles(tmp_path) -> None:
    store = _make_store(tmp_path)
    _save_base_account(store)
    inserted = store.save_articles("fakeid-1", _sample_articles())
    rows = store.get_articles("fakeid-1", limit=10)
    assert inserted == 2
    assert len(rows) == 2


def test_save_articles_dedup(tmp_path) -> None:
    store = _make_store(tmp_path)
    _save_base_account(store)
    first = store.save_articles("fakeid-1", [_sample_articles()[0]])
    second = store.save_articles("fakeid-1", [_sample_articles()[0]])
    assert first == 1
    assert second == 0


def test_get_articles_limit(tmp_path) -> None:
    store = _make_store(tmp_path)
    _save_base_account(store)
    articles = [
        {"aid": f"a{i}", "title": f"T{i}", "link": f"https://mp.weixin.qq.com/s?a={i}", "publish_time": i}
        for i in range(5)
    ]
    store.save_articles("fakeid-1", articles)
    rows = store.get_articles("fakeid-1", limit=2)
    assert len(rows) == 2
    assert rows[0]["publish_time"] >= rows[1]["publish_time"]


def test_foreign_key_cascade(tmp_path) -> None:
    store = _make_store(tmp_path)
    _save_base_account(store)
    store.save_articles("fakeid-1", _sample_articles())
    assert len(store.get_articles("fakeid-1", limit=10)) == 2
    assert store.remove_account("fakeid-1") is True
    assert store.get_articles("fakeid-1", limit=10) == []
