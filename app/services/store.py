"""SQLite log of unanswered questions and captured leads."""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


class Store:
    def __init__(self, path: Path = settings.DATA_DIR / "app.db"):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS unanswered (id INTEGER PRIMARY KEY, ts TEXT, question TEXT, query TEXT, reason TEXT);
            CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, ts TEXT, name TEXT, email TEXT, question TEXT);
        """)

    def _insert(self, sql: str, args: tuple) -> None:
        with self.lock:
            self.conn.execute(sql, (datetime.now(timezone.utc).isoformat(timespec="seconds"), *args))
            self.conn.commit()

    def log_unanswered(self, question: str, query: str, reason: str) -> None:
        self._insert("INSERT INTO unanswered (ts, question, query, reason) VALUES (?, ?, ?, ?)", (question, query, reason))

    def add_lead(self, name: str, email: str, question: str) -> None:
        self._insert("INSERT INTO leads (ts, name, email, question) VALUES (?, ?, ?, ?)", (name, email, question))

    def list(self, table: str, limit: int = 200) -> list[dict]:
        assert table in {"unanswered", "leads"}
        with self.lock:
            return [dict(r) for r in self.conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))]
