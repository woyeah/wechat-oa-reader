# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .models import Account


class ArticleStore:
    def __init__(self, db_path: str = "wechat_articles.db"):
        self._db_path = Path(db_path)
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                fakeid      TEXT PRIMARY KEY,
                nickname    TEXT NOT NULL DEFAULT '',
                alias       TEXT NOT NULL DEFAULT '',
                head_img    TEXT NOT NULL DEFAULT '',
                service_type INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL,
                last_poll   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fakeid      TEXT NOT NULL,
                aid         TEXT NOT NULL DEFAULT '',
                title       TEXT NOT NULL DEFAULT '',
                link        TEXT NOT NULL DEFAULT '',
                digest      TEXT NOT NULL DEFAULT '',
                cover       TEXT NOT NULL DEFAULT '',
                author      TEXT NOT NULL DEFAULT '',
                content     TEXT NOT NULL DEFAULT '',
                plain_content TEXT NOT NULL DEFAULT '',
                publish_time INTEGER NOT NULL DEFAULT 0,
                fetched_at  INTEGER NOT NULL,
                UNIQUE(fakeid, link),
                FOREIGN KEY (fakeid) REFERENCES accounts(fakeid) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_articles_fakeid_time
                ON articles(fakeid, publish_time DESC);
            """
        )
        conn.commit()
        conn.close()

    def save_account(self, account: Account) -> bool:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO accounts (fakeid, nickname, alias, head_img, service_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(fakeid) DO UPDATE SET
                    nickname = excluded.nickname,
                    alias = excluded.alias,
                    head_img = excluded.head_img,
                    service_type = excluded.service_type
                """,
                (
                    account.fakeid,
                    account.nickname,
                    account.alias or "",
                    account.head_img or "",
                    account.service_type or 0,
                    int(time.time()),
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def remove_account(self, fakeid: str) -> bool:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM accounts WHERE fakeid = ?", (fakeid,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def list_accounts(self) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT a.*, (SELECT COUNT(*) FROM articles ar WHERE ar.fakeid = a.fakeid) AS article_count
                FROM accounts a
                ORDER BY a.created_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_articles(self, fakeid: str, articles: list[dict]) -> int:
        conn = self._get_conn()
        inserted = 0
        try:
            for article in articles:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO articles
                    (fakeid, aid, title, link, digest, cover, author, content, plain_content, publish_time, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fakeid,
                        article.get("aid", ""),
                        article.get("title", ""),
                        article.get("link", ""),
                        article.get("digest", ""),
                        article.get("cover", ""),
                        article.get("author", ""),
                        article.get("content", ""),
                        article.get("plain_content", article.get("plain_text", "")),
                        article.get("publish_time", 0),
                        int(time.time()),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            conn.commit()
            return inserted
        finally:
            conn.close()

    def get_articles(self, fakeid: str, limit: int = 20) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM articles WHERE fakeid = ? ORDER BY publish_time DESC LIMIT ?",
                (fakeid, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
