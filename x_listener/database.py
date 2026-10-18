from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import XPost


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY, handle TEXT NOT NULL, url TEXT NOT NULL,
                created_at TEXT NOT NULL, observed_at TEXT NOT NULL, text TEXT NOT NULL,
                candidate_json TEXT, inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS deliveries (
                post_id TEXT NOT NULL REFERENCES posts(post_id), channel TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, delivered_at TEXT, last_error TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(post_id, channel)
            )""")

    def save_post(self, post: XPost, candidate: dict[str, Any] | None, channels: Iterable[str]) -> bool:
        candidate_json = json.dumps(candidate, separators=(",", ":")) if candidate else None
        with self._connect() as conn:
            cur = conn.execute("""INSERT OR IGNORE INTO posts
                (post_id,handle,url,created_at,observed_at,text,candidate_json)
                VALUES (?,?,?,?,?,?,?)""", (post.post_id, post.handle, post.url, post.created_at,
                    post.observed_at, post.text[:8000], candidate_json))
            # If channel config is added after a post was first detected, create a delivery task then.
            row = conn.execute("SELECT candidate_json FROM posts WHERE post_id=?", (post.post_id,)).fetchone()
            if row and row["candidate_json"]:
                for channel in channels:
                    conn.execute("INSERT OR IGNORE INTO deliveries(post_id,channel) VALUES(?,?)", (post.post_id, channel))
            return cur.rowcount == 1

    def pending_deliveries(self, channel: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT p.*,d.channel,d.attempts FROM posts p
                JOIN deliveries d ON p.post_id=d.post_id
                WHERE d.channel=? AND d.delivered_at IS NULL AND d.attempts < 20
                ORDER BY p.inserted_at LIMIT ?""", (channel, limit)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["candidate"] = json.loads(item.pop("candidate_json"))
            result.append(item)
        return result

    def record_delivery(self, post_id: str, channel: str, error: str | None = None) -> None:
        with self._connect() as conn:
            if error is None:
                conn.execute("""UPDATE deliveries SET attempts=attempts+1, delivered_at=CURRENT_TIMESTAMP,
                    last_error=NULL, updated_at=CURRENT_TIMESTAMP WHERE post_id=? AND channel=?""", (post_id, channel))
            else:
                conn.execute("""UPDATE deliveries SET attempts=attempts+1, last_error=?,
                    updated_at=CURRENT_TIMESTAMP WHERE post_id=? AND channel=?""", (error[:1000], post_id, channel))

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            signals = conn.execute("SELECT COUNT(*) FROM posts WHERE candidate_json IS NOT NULL").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM deliveries WHERE delivered_at IS NULL AND attempts < 20").fetchone()[0]
        return {"posts_seen": posts, "candidate_signals": signals, "pending_deliveries": pending}
