"""SQLite database for caching match data, events, stadiums, transfer news."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone, timedelta

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "barcelona_stats.db")
_lock = threading.Lock()

os.makedirs(DB_DIR, exist_ok=True)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = _connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'FINISHED',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                match_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stadiums (
                name TEXT PRIMARY KEY,
                image_path TEXT,
                attribution TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transfer_news (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                source TEXT NOT NULL,
                published TEXT,
                category TEXT DEFAULT 'rumor',
                players TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
            CREATE INDEX IF NOT EXISTS idx_transfer_category ON transfer_news(category);
        """)
        conn.commit()
        conn.close()


def save_matches(matches: list[dict]):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        for m in matches:
            data = json.dumps(m, ensure_ascii=False)
            conn.execute(
                "INSERT OR REPLACE INTO matches (id, data, status, updated_at) VALUES (?, ?, ?, ?)",
                (m["id"], data, m.get("status", "FINISHED"), now),
            )
        conn.commit()
        conn.close()


def load_matches() -> list[dict]:
    with _lock:
        conn = _connect()
        rows = conn.execute("SELECT data FROM matches").fetchall()
        conn.close()
    return [json.loads(r["data"]) for r in rows]


def is_match_list_stale() -> bool:
    """Returns True if the match list needs a fresh API fetch."""
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT updated_at FROM matches ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    if not row:
        return True
    last = datetime.fromisoformat(row["updated_at"])
    return datetime.now(timezone.utc) - last > timedelta(minutes=5)


def save_events(match_id: int, events: dict):
    now = datetime.now(timezone.utc).isoformat()
    data = json.dumps(events, ensure_ascii=False)
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO events (match_id, data, updated_at) VALUES (?, ?, ?)",
            (match_id, data, now),
        )
        conn.commit()
        conn.close()


def load_events(match_id: int) -> dict | None:
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT data FROM events WHERE match_id = ?", (match_id,)).fetchone()
        conn.close()
    if row:
        return json.loads(row["data"])
    return None


def load_all_events() -> dict[int, dict]:
    with _lock:
        conn = _connect()
        rows = conn.execute("SELECT match_id, data FROM events").fetchall()
        conn.close()
    return {r["match_id"]: json.loads(r["data"]) for r in rows}


def is_events_stale(match_id: int) -> bool:
    """Finished matches: never stale. Others: 30 min."""
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT updated_at FROM events WHERE match_id = ?", (match_id,)).fetchone()
        conn.close()
    if not row:
        return True
    last = datetime.fromisoformat(row["updated_at"])
    return datetime.now(timezone.utc) - last > timedelta(minutes=30)


def save_stadium(name: str, image_path: str, attribution: str = ""):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO stadiums (name, image_path, attribution, updated_at) VALUES (?, ?, ?, ?)",
            (name, image_path, attribution, now),
        )
        conn.commit()
        conn.close()


def load_stadium(name: str) -> dict | None:
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM stadiums WHERE name = ?", (name,)).fetchone()
        conn.close()
    if row:
        return {"name": row["name"], "image_path": row["image_path"], "attribution": row["attribution"]}
    return None


def is_stadium_stale(name: str) -> bool:
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT updated_at FROM stadiums WHERE name = ?", (name,)).fetchone()
        conn.close()
    if not row:
        return True
    return False  # Never stale once saved


def upsert_transfer_articles(articles: list[dict]):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        for a in articles:
            conn.execute(
                """INSERT OR REPLACE INTO transfer_news (id, title, link, source, published, category, players, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (a["id"], a["title"], a["link"], a["source"],
                 a.get("published", ""), a.get("category", "rumor"),
                 ",".join(a.get("players", [])), now),
            )
        conn.commit()
        conn.close()


def load_transfer_articles(category: str | None = None, limit: int = 50) -> list[dict]:
    with _lock:
        conn = _connect()
        if category:
            rows = conn.execute(
                "SELECT * FROM transfer_news WHERE category = ? ORDER BY published DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transfer_news ORDER BY published DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def is_transfer_news_stale() -> bool:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT updated_at FROM transfer_news ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    if not row:
        return True
    last = datetime.fromisoformat(row["updated_at"])
    return datetime.now(timezone.utc) - last > timedelta(hours=1)


# Initialize DB on import
init_db()
