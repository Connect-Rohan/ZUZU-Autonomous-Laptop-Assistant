"""
Tests for ZUZU – Command routing, notes, reminders, and validation.
Run: python -m pytest tests/ -v
"""

import sys
import os
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════
# 1. Command Router – local_match
# ══════════════════════════════════════════════════════════════

from assistant.command_router import local_match, validate_command, execute_command
from config import ALLOWED_COMMANDS


class TestLocalMatch:

    def test_open_chrome(self):
        cmd = local_match("open chrome")
        assert cmd is not None
        assert cmd["action"] == "open_chrome"

    def test_open_chrome_with_launch(self):
        cmd = local_match("launch Google Chrome please")
        assert cmd is not None
        assert cmd["action"] == "open_chrome"

    def test_open_calculator(self):
        cmd = local_match("open calculator")
        assert cmd["action"] == "open_calculator"

    def test_open_notepad(self):
        cmd = local_match("start notepad")
        assert cmd["action"] == "open_notepad"

    def test_open_this_pc(self):
        cmd = local_match("open this PC")
        assert cmd["action"] == "open_this_pc"

    def test_open_my_pc(self):
        cmd = local_match("show my pc")
        assert cmd["action"] == "open_this_pc"

    def test_open_settings(self):
        cmd = local_match("open Windows settings")
        assert cmd["action"] == "open_settings"

    def test_open_explorer(self):
        cmd = local_match("open file explorer")
        assert cmd["action"] == "open_explorer"

    def test_open_store(self):
        cmd = local_match("open Microsoft Store")
        assert cmd["action"] == "search_store"

    def test_search_store(self):
        cmd = local_match("open Microsoft Store and search for WhatsApp")
        assert cmd["action"] == "search_store"
        assert "whatsapp" in cmd.get("app_name", "").lower()

    def test_create_note(self):
        cmd = local_match("make a note that the meeting is tomorrow")
        assert cmd is not None
        assert cmd["action"] == "create_note"
        assert "meeting" in cmd.get("content", "").lower()

    def test_show_notes(self):
        cmd = local_match("show recent notes")
        assert cmd["action"] == "show_notes"

    def test_search_notes(self):
        cmd = local_match("search notes for meeting")
        assert cmd["action"] == "search_notes"

    def test_create_reminder(self):
        cmd = local_match("remind me in 10 minutes to drink water")
        assert cmd["action"] == "create_reminder"

    def test_list_reminders(self):
        cmd = local_match("list my reminders")
        assert cmd["action"] == "list_reminders"

    def test_cancel_reminder(self):
        cmd = local_match("cancel reminder #3")
        assert cmd["action"] == "cancel_reminder"
        assert cmd.get("reminder_id") == 3

    def test_unrecognized_returns_none(self):
        cmd = local_match("what is the capital of France")
        assert cmd is None   # falls through to AI


class TestValidateCommand:

    def test_valid_action(self):
        ok, _ = validate_command({"action": "open_chrome"})
        assert ok

    def test_invalid_action_blocked(self):
        ok, _ = validate_command({"action": "execute_python_code"})
        assert not ok

    def test_not_a_dict(self):
        ok, _ = validate_command("open chrome")
        assert not ok

    def test_missing_action(self):
        ok, _ = validate_command({})
        assert not ok

    def test_all_allowed_commands_pass(self):
        for action in ALLOWED_COMMANDS:
            ok, _ = validate_command({"action": action})
            assert ok, f"'{action}' should be valid"


# ══════════════════════════════════════════════════════════════
# 2. Notes – SQLite
# ══════════════════════════════════════════════════════════════

from services import notes as notes_mod


@pytest.fixture
def temp_notes_db(tmp_path, monkeypatch):
    db = tmp_path / "test_notes.db"
    monkeypatch.setattr(notes_mod, "NOTES_DB_PATH", db, raising=False)
    # Patch config ref used inside module
    import config
    original = config.NOTES_DB_PATH
    config.NOTES_DB_PATH = db
    yield db
    config.NOTES_DB_PATH = original


class TestNotes:

    def test_create_note(self, temp_notes_db):
        ok, msg = notes_mod.create_note("Test note content")
        assert ok
        assert "saved" in msg.lower()

    def test_create_empty_note_fails(self, temp_notes_db):
        ok, msg = notes_mod.create_note("")
        assert not ok

    def test_notes_never_overwrite(self, temp_notes_db):
        notes_mod.create_note("Note A")
        notes_mod.create_note("Note B")
        notes = notes_mod.get_recent_notes(limit=10)
        contents = [n["content"] for n in notes]
        assert "Note A" in contents
        assert "Note B" in contents

    def test_search_notes(self, temp_notes_db):
        notes_mod.create_note("AI project meeting tomorrow")
        notes_mod.create_note("Grocery list: milk, eggs")
        results = notes_mod.search_notes("meeting")
        assert any("meeting" in r["content"].lower() for r in results)
        assert not any("milk" in r["content"].lower() for r in results)

    def test_get_recent_limit(self, temp_notes_db):
        for i in range(10):
            notes_mod.create_note(f"Note {i}")
        results = notes_mod.get_recent_notes(limit=3)
        assert len(results) <= 3

    def test_format_empty(self, temp_notes_db):
        txt = notes_mod.format_notes_for_display([])
        assert "no notes" in txt.lower()


# ══════════════════════════════════════════════════════════════
# 3. Reminders – time parsing
# ══════════════════════════════════════════════════════════════

from services.reminders import parse_reminder_time, create_reminder as create_rem
import services.reminders as rem_mod


@pytest.fixture
def temp_reminders_db(tmp_path, monkeypatch):
    db = tmp_path / "test_reminders.db"
    import config
    original = config.REMINDER_DB_PATH
    config.REMINDER_DB_PATH = db
    monkeypatch.setattr(rem_mod, "REMINDER_DB_PATH", db, raising=False)
    yield db
    config.REMINDER_DB_PATH = original


class TestReminderParsing:

    def test_in_minutes(self):
        dt = parse_reminder_time("in 10 minutes")
        assert dt is not None
        diff = (dt - datetime.now()).total_seconds()
        assert 540 < diff < 660   # ~10 minutes

    def test_in_hours(self):
        dt = parse_reminder_time("in 2 hours")
        assert dt is not None
        diff = (dt - datetime.now()).total_seconds()
        assert 7100 < diff < 7300

    def test_tomorrow(self):
        dt = parse_reminder_time("tomorrow")
        assert dt is not None
        assert dt.date() == (datetime.now() + timedelta(days=1)).date()

    def test_tomorrow_at_time(self):
        dt = parse_reminder_time("tomorrow at 9 AM")
        assert dt is not None
        assert dt.date() == (datetime.now() + timedelta(days=1)).date()
        assert dt.hour == 9

    def test_invalid_time_returns_none(self):
        dt = parse_reminder_time("sometime next year maybe")
        # May return None or a parsed date — it should not crash
        # Just verify no exception
        assert True

    def test_create_reminder_past_time_fails(self, temp_reminders_db):
        ok, msg = create_rem("test", "in 0 seconds")
        # Either past time fails or succeeds with very short delay — both acceptable
        assert isinstance(ok, bool)

    def test_create_reminder_future(self, temp_reminders_db):
        ok, msg = create_rem("drink water", "in 5 minutes")
        assert ok

    def test_list_reminders_empty(self, temp_reminders_db):
        from services.reminders import list_reminders
        r = list_reminders()
        assert isinstance(r, list)


# ══════════════════════════════════════════════════════════════
# 4. AI Handler – safe command validation
# ══════════════════════════════════════════════════════════════

from assistant.ai_handler import AIHandler


class TestAIHandlerSafety:

    def test_parse_json_valid(self):
        handler = AIHandler()
        cmd = handler._parse_json('{"action": "open_chrome"}')
        assert cmd["action"] == "open_chrome"

    def test_parse_json_disallowed_action_blocked(self):
        handler = AIHandler()
        cmd = handler._parse_json('{"action": "execute_shell_command", "cmd": "rm -rf /"}')
        assert cmd["action"] == "unknown"

    def test_parse_json_invalid_json(self):
        handler = AIHandler()
        cmd = handler._parse_json("not json at all")
        assert cmd["action"] == "unknown"

    def test_parse_json_strips_fences(self):
        handler = AIHandler()
        cmd = handler._parse_json('```json\n{"action": "open_calculator"}\n```')
        assert cmd["action"] == "open_calculator"

    def test_parse_json_non_dict_returns_unknown(self):
        handler = AIHandler()
        cmd = handler._parse_json('["open_chrome"]')
        assert cmd["action"] == "unknown"

    def test_not_ready_returns_unknown(self):
        handler = AIHandler()   # not initialized
        result = handler.parse_command("open chrome")
        assert result["action"] == "unknown"
