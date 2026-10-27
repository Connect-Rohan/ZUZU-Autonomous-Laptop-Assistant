"""
ZUZU – Command Router
Routes validated command dicts to the appropriate action handler.
Local patterns can shortcut simple commands without calling Gemini.
"""

import re
import logging
from config import ALLOWED_COMMANDS

log = logging.getLogger(__name__)

# ── Local pattern matching (no API needed for these) ───────────

_LOCAL_PATTERNS = [
    # App opens
    (re.compile(r"\b(open|launch|start)\s+(google\s+)?chrome\b", re.I), "open_chrome", {}),
    (re.compile(r"\b(open|launch|start)\s+notepad\b", re.I),             "open_notepad", {}),
    (re.compile(r"\b(open|launch|start)\s+calc(ulator)?\b", re.I),       "open_calculator", {}),
    (re.compile(r"\b(open|launch|start)\s+(file\s+)?explorer\b", re.I),  "open_explorer", {}),
    (re.compile(r"\b(open|show|go to)\s+(this|my)\s+pc\b", re.I),        "open_this_pc", {}),
    (re.compile(r"\b(open|launch)\s+(windows\s+)?settings\b", re.I),     "open_settings", {}),
    # Store + search — MUST come before plain store pattern
    (re.compile(r"\b(?:open|launch)\s+(?:microsoft\s+)?store\s+(?:and\s+)?(?:search|find)\s+(?:for\s+)?(.+)", re.I),
     "search_store", None),   # None = special handler below

    (re.compile(r"\b(open|launch)\s+(microsoft\s+)?store\b", re.I),      "search_store", {"app_name": ""}),

    # Notes
    (re.compile(r"\b(make|create|add|save)\s+a?\s*note\b", re.I),        "create_note", None),
    (re.compile(r"\bshow\s+(recent\s+)?notes?\b", re.I),                  "show_notes", {}),
    (re.compile(r"\bopen\s+notes?\s*(file)?\b", re.I),                    "open_notes_file", {}),
    (re.compile(r"\bsearch\s+notes?\s+(?:for\s+)?(.+)", re.I),            "search_notes", None),

    # Reminders
    (re.compile(r"\b(remind\s+me|set\s+a?\s*reminder|schedule\s+a?\s*reminder)\b", re.I),
     "create_reminder", None),
    (re.compile(r"\b(list|show)\s+(my\s+)?reminders?\b", re.I),           "list_reminders", {}),
    (re.compile(r"\bcancel\s+reminder\s+#?(\d+)\b", re.I),                "cancel_reminder", None),
]


def local_match(text: str) -> dict | None:
    """
    Attempt to match a command locally without calling Gemini.
    Returns a command dict, or None if no local match found.
    """
    for pattern, action, fixed_args in _LOCAL_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        if fixed_args is not None:
            return {"action": action, **fixed_args}

        # Dynamic argument extraction
        if action == "search_store":
            # Group 1 contains the app name (new pattern has only 1 capture group)
            try:
                app_name = m.group(1).strip()
            except (IndexError, AttributeError):
                app_name = ""
            return {"action": "search_store", "app_name": app_name}

        if action == "create_note":
            # Extract content after "note (that)?"
            content = re.sub(
                r"^.*?\bnote\b\s*(?:that\s+)?", "", text, flags=re.I
            ).strip()
            return {"action": "create_note", "content": content}

        if action == "search_notes":
            try:
                query = m.group(1).strip()
            except IndexError:
                query = text
            return {"action": "search_notes", "query": query}

        if action == "create_reminder":
            # We'll pass the whole text to the reminders service for parsing
            return {"action": "create_reminder", "raw_text": text}

        if action == "cancel_reminder":
            try:
                rid = int(m.group(1))
            except (IndexError, ValueError):
                rid = -1
            return {"action": "cancel_reminder", "reminder_id": rid}

    return None


def validate_command(cmd: dict) -> tuple[bool, str]:
    """Ensure a command dict has an allowed action."""
    if not isinstance(cmd, dict):
        return False, "Command is not a dict."
    action = cmd.get("action", "")
    if action not in ALLOWED_COMMANDS:
        return False, f"Action '{action}' is not in the allowed list."
    return True, "OK"


def execute_command(cmd: dict, ui=None, tts=None) -> str:
    """
    Execute a validated command dict.
    Returns a human-readable result string.
    Falls back through import errors gracefully.
    """
    action = cmd.get("action", "unknown")
    log.info("Executing command: %s", cmd)

    # ── App opens ──────────────────────────────────────────────
    if action == "open_chrome":
        from automation.windows_apps import open_chrome
        ok, msg = open_chrome()
        return msg

    if action == "open_notepad":
        from automation.windows_apps import open_notepad
        ok, msg = open_notepad()
        return msg

    if action == "open_calculator":
        from automation.windows_apps import open_calculator
        ok, msg = open_calculator()
        return msg

    if action == "open_explorer":
        from automation.windows_apps import open_explorer
        ok, msg = open_explorer(cmd.get("path", ""))
        return msg

    if action == "open_this_pc":
        from automation.windows_apps import open_this_pc
        ok, msg = open_this_pc()
        return msg

    if action == "open_settings":
        from automation.windows_apps import open_settings
        ok, msg = open_settings()
        return msg

    if action == "open_application":
        from automation.windows_apps import launch_app_by_name
        name = cmd.get("app_name", cmd.get("name", ""))
        ok, msg = launch_app_by_name(name)
        return msg

    # ── Store ──────────────────────────────────────────────────
    if action == "search_store":
        from automation.store import search_store
        ok, msg = search_store(cmd.get("app_name", ""))
        return msg

    # ── Notes ──────────────────────────────────────────────────
    if action == "create_note":
        from services.notes import create_note
        content = cmd.get("content", "").strip()
        if not content:
            return "What should I put in the note? Please say the note content."
        ok, msg = create_note(content)
        return msg

    if action == "show_notes":
        from services.notes import get_recent_notes, format_notes_for_display
        notes = get_recent_notes(limit=5)
        return format_notes_for_display(notes)

    if action == "search_notes":
        from services.notes import search_notes, format_notes_for_display
        results = search_notes(cmd.get("query", ""))
        return format_notes_for_display(results)

    if action == "open_notes_file":
        from services.notes import export_notes_to_txt
        from automation.windows_apps import open_notepad
        path = export_notes_to_txt()
        if path:
            open_notepad(str(path))
            return f"Notes exported and opened in Notepad: {path}"
        return "No notes found to open."

    # ── Reminders ──────────────────────────────────────────────
    if action == "create_reminder":
        from services.reminders import create_reminder as _cr
        from services.reminders import _extract_reminder_parts
        message, time_str = _extract_reminder_parts(
            cmd.get("raw_text", ""),
            cmd.get("message", ""),
            cmd.get("time", "")
        )
        if not time_str:
            return "Please specify when the reminder should go off. E.g. 'in 10 minutes' or 'tomorrow at 8 AM'."
        ok, msg = _cr(message, time_str)
        return msg

    if action == "list_reminders":
        from services.reminders import list_reminders, format_reminders_for_display
        return format_reminders_for_display(list_reminders())

    if action == "cancel_reminder":
        from services.reminders import cancel_reminder
        rid = cmd.get("reminder_id", -1)
        if rid < 0:
            return "Please specify the reminder number to cancel. E.g. 'cancel reminder 2'."
        ok, msg = cancel_reminder(rid)
        return msg

    # ── General query (Gemini answered it directly) ────────────
    if action == "general_query":
        return cmd.get("response", "I'm not sure how to answer that.")

    # ── Unknown ────────────────────────────────────────────────
    return (
        "I didn't understand that command. "
        "Try opening an app, creating a note, or setting a reminder."
    )
