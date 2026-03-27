# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from wechat_oa_reader.models import WeComMessage, WeComUser
from wechat_oa_reader.wecom_store import WeComStore


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


def _make_store(tmp_path: Path) -> WeComStore:
    return WeComStore(str(tmp_path / "wecom.db"))


def _make_user(*, userid: str, name: str, department: str | None = None, avatar: str | None = None) -> WeComUser:
    return WeComUser(userid=userid, name=name, department=department, avatar=avatar)


def _make_message(
    *,
    msg_id: str,
    from_user: str,
    to_user: str,
    create_time: int,
    direction: Literal["sent", "received"],
    content: str = "hello",
    msg_type: str = "text",
) -> WeComMessage:
    return WeComMessage(
        msg_id=msg_id,
        msg_type=msg_type,
        from_user=from_user,
        to_user=to_user,
        content=content,
        create_time=create_time,
        direction=direction,
    )


class TestWeComStoreInit:
    def test_init_creates_tables(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        conn = sqlite3.connect(str(tmp_path / "wecom.db"))
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        finally:
            conn.close()
        assert "wecom_users" in tables
        assert "wecom_messages" in tables


class TestWeComStoreUsers:
    def test_save_and_find_user(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        user = _make_user(userid="u1", name="Alice", department="Tech", avatar="https://example.com/a.png")
        store.save_user(user)

        found = store.find_user_by_name("Alice")
        assert found is not None
        assert found.userid == "u1"
        assert found.name == "Alice"
        assert found.department == "Tech"
        assert found.avatar == "https://example.com/a.png"

    def test_save_user_upsert(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_user(_make_user(userid="u1", name="Alice"))
        store.save_user(_make_user(userid="u1", name="Alice Updated", department="Ops"))

        found = store.find_user_by_name("Alice Updated")
        assert found is not None
        assert found.userid == "u1"
        assert found.name == "Alice Updated"
        assert found.department == "Ops"
        assert len(store.list_users()) == 1

    def test_find_user_not_found(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        assert store.find_user_by_name("No Such User") is None

    def test_list_users(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_user(_make_user(userid="u1", name="Alice"))
        store.save_user(_make_user(userid="u2", name="Bob"))

        users = store.list_users()
        assert len(users) == 2
        assert {user.userid for user in users} == {"u1", "u2"}


class TestWeComStoreMessages:
    def test_save_and_get_messages(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="u1", to_user="u2", create_time=100, direction="sent"))
        store.save_message(_make_message(msg_id="m2", from_user="u2", to_user="u1", create_time=300, direction="received"))
        store.save_message(_make_message(msg_id="m3", from_user="u1", to_user="u3", create_time=200, direction="sent"))

        rows = store.get_messages(limit=10)
        assert [msg.msg_id for msg in rows] == ["m2", "m3", "m1"]

    def test_get_messages_with_from_user(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="u1", to_user="u2", create_time=100, direction="sent"))
        store.save_message(_make_message(msg_id="m2", from_user="u2", to_user="u1", create_time=200, direction="received"))
        store.save_message(_make_message(msg_id="m3", from_user="u1", to_user="u3", create_time=300, direction="sent"))

        rows = store.get_messages(from_user="u1", limit=10)
        assert len(rows) == 2
        assert {msg.msg_id for msg in rows} == {"m1", "m3"}
        assert all(msg.from_user == "u1" for msg in rows)

    def test_get_messages_with_direction(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="u1", to_user="u2", create_time=100, direction="sent"))
        store.save_message(_make_message(msg_id="m2", from_user="u2", to_user="u1", create_time=200, direction="received"))
        store.save_message(_make_message(msg_id="m3", from_user="u3", to_user="u1", create_time=300, direction="received"))

        rows = store.get_messages(direction="received", limit=10)
        assert len(rows) == 2
        assert {msg.msg_id for msg in rows} == {"m2", "m3"}
        assert all(msg.direction == "received" for msg in rows)

    def test_get_messages_limit(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        for i in range(5):
            store.save_message(
                _make_message(
                    msg_id=f"m{i}",
                    from_user="u1",
                    to_user="u2",
                    create_time=100 + i,
                    direction="sent",
                )
            )

        rows = store.get_messages(limit=2)
        assert len(rows) == 2
        assert rows[0].create_time >= rows[1].create_time


class TestWeComStoreReplies:
    def test_get_replies(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="u1", to_user="u2", create_time=100, direction="sent"))
        store.save_message(_make_message(msg_id="m2", from_user="u2", to_user="u1", create_time=200, direction="received"))
        store.save_message(_make_message(msg_id="m3", from_user="u1", to_user="u3", create_time=300, direction="sent"))
        store.save_message(_make_message(msg_id="m4", from_user="u3", to_user="u1", create_time=400, direction="received"))

        replies = store.get_replies(limit=10)
        assert [msg.msg_id for msg in replies] == ["m4", "m2"]
        assert all(msg.direction == "received" for msg in replies)

    def test_get_replies_since(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="u2", to_user="u1", create_time=100, direction="received"))
        store.save_message(_make_message(msg_id="m2", from_user="u3", to_user="u1", create_time=200, direction="received"))
        store.save_message(_make_message(msg_id="m3", from_user="u1", to_user="u2", create_time=300, direction="sent"))

        replies = store.get_replies(since=150, limit=10)
        assert [msg.msg_id for msg in replies] == ["m2"]


class TestWeComStoreConversation:
    def test_get_conversation(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.save_message(_make_message(msg_id="m1", from_user="alice", to_user="me", create_time=100, direction="received"))
        store.save_message(_make_message(msg_id="m2", from_user="me", to_user="alice", create_time=300, direction="sent"))
        store.save_message(_make_message(msg_id="m3", from_user="alice", to_user="me", create_time=200, direction="received"))
        store.save_message(_make_message(msg_id="m4", from_user="bob", to_user="charlie", create_time=400, direction="sent"))

        rows = store.get_conversation("alice", limit=10)
        assert [msg.msg_id for msg in rows] == ["m2", "m3", "m1"]
        assert {msg.msg_id for msg in rows} == {"m1", "m2", "m3"}
