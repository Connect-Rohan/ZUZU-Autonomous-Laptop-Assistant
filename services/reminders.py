"""
ZUZU – Reminders System (SQLite + background scheduler)

NOTE: This scheduler only works while ZUZU is running.
For persistent reminders after app close, integrate Windows Task Scheduler
in a future version (see scheduler module design below).
"""

import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from dateutil import parser as du_parser
from dateutil.relativedelta import relativedelta
from config import REMINDER_DB_PATH

log = logging.getLogger(__name__)

# ── DB init ────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(REMINDER_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message     TEXT    NOT NULL,
            due_dt      TEXT    NOT NULL,
            created     TEXT    NOT NULL,
            delivered   INTEGER DEFAULT 0,
            cancelled   INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


# ── Date parsing ───────────────────────────────────────────────

def parse_reminder_time(time_str: str) -> datetime | None:
    """
    Parse relative or absolute time strings.
    Examples:
      "in 10 minutes", "tomorrow at 8 AM", "Friday at 3 PM", "2026-11-01 14:00"
    Returns a naive datetime in local time, or None if unparseable.
    """
    now = datetime.now()
    text = time_str.lower().strip()

    # Relative: "in X minutes/hours/days"
    import re
    m = re.match(r"in\s+(\d+)\s+(second|minute|hour|day|week)s?", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta_map = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour":   timedelta(hours=n),
            "day":    timedelta(days=n),
            "week":   timedelta(weeks=n),
        }
        return now + delta_map[unit]

    # "tomorrow" keyword
    if "tomorrow" in text:
        base = now + timedelta(days=1)
        try:
            # Extract time part after "tomorrow"
            rest = text.replace("tomorrow", "").strip()
            if rest:
                parsed = du_parser.parse(rest, default=base)
                return base.replace(hour=parsed.hour, minute=parsed.minute, second=0)
        except Exception:
            pass
        return base.replace(hour=8, minute=0, second=0)

    # Absolute parse with dateutil
    try:
        dt = du_parser.parse(time_str, default=now, fuzzy=True)
        # If the parsed time is in the past, assume user means next occurrence
        if dt < now:
            dt += timedelta(days=1)
        return dt
    except Exception:
        return None


# ── CRUD ───────────────────────────────────────────────────────

def create_reminder(message: str, time_str: str) -> tuple[bool, str]:
    due = parse_reminder_time(time_str)
    if due is None:
        return False, (
            f"I couldn't understand the time '{time_str}'. "
            "Try: 'in 10 minutes', 'tomorrow at 8 AM', or a date like '2026-11-01 14:00'."
        )
    if due < datetime.now():
        return False, "That time is already in the past. Please choose a future time."

    try:
        conn = _get_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        due_str = due.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO reminders (message, due_dt, created) VALUES (?, ?, ?)",
            (message.strip(), due_str, now_str)
        )
        conn.commit()
        conn.close()
        log.info("Reminder set for %s: %s", due_str, message)
        return True, f"Reminder set for {due.strftime('%A, %b %d at %I:%M %p')}: '{message}'."
    except sqlite3.Error as exc:
        log.error("DB error creating reminder: %s", exc)
        return False, f"Failed to save reminder: {exc}"


def list_reminders() -> list[dict]:
    try:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT * FROM reminders
               WHERE delivered=0 AND cancelled=0
               ORDER BY due_dt ASC LIMIT 10"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        log.error("DB error listing reminders: %s", exc)
        return []


def cancel_reminder(reminder_id: int) -> tuple[bool, str]:
    try:
        conn = _get_conn()
        conn.execute("UPDATE reminders SET cancelled=1 WHERE id=?", (reminder_id,))
        conn.commit()
        conn.close()
        return True, f"Reminder #{reminder_id} cancelled."
    except sqlite3.Error as exc:
        return False, f"Failed to cancel: {exc}"


def format_reminders_for_display(reminders: list[dict]) -> str:
    if not reminders:
        return "No upcoming reminders."
    lines = []
    for r in reminders:
        lines.append(f"#{r['id']} [{r['due_dt']}] {r['message']}")
    return "\n".join(lines)


def _extract_reminder_parts(raw_text: str, message: str = "", time_str: str = "") -> tuple[str, str]:
    """
    Given a raw utterance like 'remind me in 10 minutes to drink water',
    extract (message, time_string).
    Returns whatever was passed in message/time_str if already parsed by AI.
    """
    if message and time_str:
        return message, time_str

    text = raw_text.lower()

    # Try to extract time portion
    time_patterns = [
        r"in\s+\d+\s+(?:second|minute|hour|day|week)s?",
        r"tomorrow(?:\s+at\s+[\d:apm]+)?",
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at\s+[\d:apm]+)?",
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)",
        r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?",
    ]
    import re
    found_time = ""
    for pat in time_patterns:
        m = re.search(pat, text)
        if m:
            found_time = m.group(0)
            break

    # Extract message = everything after "to/about/that" or the whole text
    msg_match = re.search(
        r"(?:to|about|that|for)\s+(.+?)(?:\s*$)", raw_text, re.I
    )
    extracted_msg = msg_match.group(1).strip() if msg_match else raw_text

    return extracted_msg or raw_text, found_time or time_str


def _get_due_reminders() -> list[dict]:
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = _get_conn()
        rows = conn.execute(
            """SELECT * FROM reminders
               WHERE due_dt <= ? AND delivered=0 AND cancelled=0""",
            (now_str,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _mark_delivered(reminder_id: int):
    try:
        conn = _get_conn()
        conn.execute("UPDATE reminders SET delivered=1 WHERE id=?", (reminder_id,))
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


# ── Background scheduler ───────────────────────────────────────

class ReminderScheduler:
    """
    Polls the DB every 30 seconds.
    Calls on_reminder(message) when a reminder is due.

    LIMITATION: Only runs while ZUZU is open.
    Future: integrate Windows Task Scheduler for persistent reminders.
    """

    def __init__(self, on_reminder=None):
        self._on_reminder = on_reminder or (lambda m: None)
        self._stop_event  = threading.Event()
        self._thread      = threading.Thread(
            target=self._loop, daemon=True, name="ReminderScheduler")

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _loop(self):
        while not self._stop_event.is_set():
            due = _get_due_reminders()
            for r in due:
                _mark_delivered(r["id"])
                try:
                    self._on_reminder(r["message"])
                except Exception as exc:
                    log.error("Reminder callback error: %s", exc)
            self._stop_event.wait(timeout=30)
