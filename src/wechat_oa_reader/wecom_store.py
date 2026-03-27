# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from .models import WeComMessage, WeComUser


class WeComStore:
    def __init__(self, db_path: str = "wecom.db"):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS wecom_users (
                userid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                avatar TEXT,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wecom_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT NOT NULL DEFAULT '',
                msg_type TEXT NOT NULL DEFAULT 'text',
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                direction TEXT NOT NULL CHECK(direction IN ('sent', 'received')),
                created_at INTEGER NOT NULL,
                stored_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_wecom_messages_from_user
                ON wecom_messages(from_user, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_wecom_messages_direction
                ON wecom_messages(direction, created_at DESC);
            """
        )
        conn.commit()
        conn.close()

    def save_user(self, user: WeComUser) -> None:
        conn = self._get_conn()
        try:
            with self._lock:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO wecom_users (userid, name, department, avatar, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user.userid, user.name, user.department, user.avatar, int(time.time())),
                )
                conn.commit()
        finally:
            conn.close()

    def find_user_by_name(self, name: str) -> WeComUser | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT userid, name, department, avatar FROM wecom_users WHERE name = ? LIMIT 1",
                (name,),
            ).fetchone()
            if row is None:
                return None
            return WeComUser(userid=row["userid"], name=row["name"], department=row["department"], avatar=row["avatar"])
        finally:
            conn.close()

    def list_users(self) -> list[WeComUser]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT userid, name, department, avatar FROM wecom_users ORDER BY updated_at DESC"
            ).fetchall()
            return [
                WeComUser(userid=row["userid"], name=row["name"], department=row["department"], avatar=row["avatar"])
                for row in rows
            ]
        finally:
            conn.close()

    def save_message(self, msg: WeComMessage) -> None:
        conn = self._get_conn()
        try:
            with self._lock:
                conn.execute(
                    """
                    INSERT INTO wecom_messages
                    (msg_id, msg_type, from_user, to_user, content, direction, created_at, stored_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.msg_id,
                        msg.msg_type,
                        msg.from_user,
                        msg.to_user,
                        msg.content,
                        msg.direction,
                        msg.create_time,
                        int(time.time()),
                    ),
                )
                conn.commit()
        finally:
            conn.close()

    def get_messages(
        self,
        *,
        from_user: str | None = None,
        direction: str | None = None,
        since: int | None = None,
        limit: int = 20,
    ) -> list[WeComMessage]:
        clauses: list[str] = []
        params: list[str | int] = []
        if from_user is not None:
            clauses.append("from_user = ?")
            params.append(from_user)
        if direction is not None:
            clauses.append("direction = ?")
            params.append(direction)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since)

        sql = "SELECT msg_id, msg_type, from_user, to_user, content, direction, created_at FROM wecom_messages"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                WeComMessage(
                    msg_id=row["msg_id"],
                    msg_type=row["msg_type"],
                    from_user=row["from_user"],
                    to_user=row["to_user"],
                    content=row["content"],
                    create_time=row["created_at"],
                    direction=row["direction"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_replies(self, since: int | None = None, limit: int = 50) -> list[WeComMessage]:
        clauses = ["direction = 'received'"]
        params: list[int] = []
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since)

        sql = (
            "SELECT msg_id, msg_type, from_user, to_user, content, direction, created_at "
            "FROM wecom_messages WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)

        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                WeComMessage(
                    msg_id=row["msg_id"],
                    msg_type=row["msg_type"],
                    from_user=row["from_user"],
                    to_user=row["to_user"],
                    content=row["content"],
                    create_time=row["created_at"],
                    direction=row["direction"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_conversation(self, userid: str, limit: int = 20) -> list[WeComMessage]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT msg_id, msg_type, from_user, to_user, content, direction, created_at
                FROM wecom_messages
                WHERE from_user = ? OR to_user = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (userid, userid, limit),
            ).fetchall()
            return [
                WeComMessage(
                    msg_id=row["msg_id"],
                    msg_type=row["msg_type"],
                    from_user=row["from_user"],
                    to_user=row["to_user"],
                    content=row["content"],
                    create_time=row["created_at"],
                    direction=row["direction"],
                )
                for row in rows
            ]
        finally:
            conn.close()
