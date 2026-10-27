"""
ZUZU Configuration
All runtime settings loaded from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# ── Project paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

NOTES_DB_PATH   = DATA_DIR / "notes.db"
REMINDER_DB_PATH = DATA_DIR / "reminders.db"

# ── AI / Gemini ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Voice ──────────────────────────────────────────────────────
WAKE_PHRASE         = "hey bro"
SPEECH_TIMEOUT      = 5          # seconds of silence before giving up
PHRASE_TIME_LIMIT   = 10         # max seconds for a single command
ENERGY_THRESHOLD    = 300        # microphone sensitivity
TTS_RATE            = 165        # words per minute
TTS_VOLUME          = 0.9

# ── UI ────────────────────────────────────────────────────────
APP_TITLE    = "ZUZU — AI Assistant"
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 680
BG_COLOR     = "#0d0d1a"
ACCENT_COLOR = "#7c5cfc"
ACCENT2_COLOR = "#00d4ff"

# ── Safety: allowed command types ─────────────────────────────
ALLOWED_COMMANDS = {
    "open_application",
    "open_this_pc",
    "open_settings",
    "open_notepad",
    "open_calculator",
    "open_chrome",
    "open_explorer",
    "create_note",
    "show_notes",
    "search_notes",
    "open_notes_file",
    "create_reminder",
    "list_reminders",
    "cancel_reminder",
    "search_store",
    "general_query",
    "unknown",
}
