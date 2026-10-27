"""
ZUZU – Persistent Notes System (SQLite backend)
Notes are stored in data/notes.db.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from config import NOTES_DB_PATH

log = logging.getLogger(__name__)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(NOTES_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            content   TEXT    NOT NULL,
            created   TEXT    NOT NULL,
            tags      TEXT    DEFAULT ''
        )
    """)
    conn.commit()
    return conn


# ── Public API ─────────────────────────────────────────────────

def create_note(content: str, tags: str = "") -> tuple[bool, str]:
    """Save a new note. Never overwrites existing notes."""
    if not content or not content.strip():
        return False, "Note content cannot be empty."
    try:
        conn = _get_conn()
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO notes (content, created, tags) VALUES (?, ?, ?)",
            (content.strip(), now, tags.strip())
        )
        conn.commit()
        conn.close()
        log.info("Note created at %s", now)
        return True, f"Note saved at {now}."
    except sqlite3.Error as exc:
        log.error("DB error saving note: %s", exc)
        return False, f"Failed to save note: {exc}"


def get_recent_notes(limit: int = 5) -> list[dict]:
    """Return the most recent notes as a list of dicts."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log.error("DB error fetching notes: %s", exc)
        return []


def search_notes(query: str) -> list[dict]:
    """Full-text search across note content (LIKE)."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM notes WHERE content LIKE ? ORDER BY id DESC LIMIT 10",
            (f"%{query}%",)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log.error("DB error searching notes: %s", exc)
        return []


def format_notes_for_display(notes: list[dict]) -> str:
    if not notes:
        return "No notes found."
    lines = []
    for n in notes:
        lines.append(f"[{n['created']}] {n['content']}")
    return "\n".join(lines)


def export_notes_to_txt() -> Path | None:
    """Write all notes to a plain-text file and return its path."""
    notes = get_recent_notes(limit=1000)
    if not notes:
        return None
    out = Path(str(NOTES_DB_PATH).replace(".db", "_export.txt"))
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("ZUZU Notes Export\n")
            f.write("=" * 40 + "\n\n")
            for n in reversed(notes):
                f.write(f"[{n['created']}]\n{n['content']}\n\n")
        return out
    except OSError as exc:
        log.error("Export failed: %s", exc)
        return None
