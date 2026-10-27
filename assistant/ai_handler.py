"""
ZUZU – Gemini AI Handler
Converts natural-language commands into validated ZUZU command dicts.
Uses the official google-genai SDK. Requires GEMINI_API_KEY in .env.
"""

import json
import logging
import re
from config import GEMINI_API_KEY, GEMINI_MODEL, ALLOWED_COMMANDS

log = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────
_SYSTEM_PROMPT = f"""
You are the command interpreter for ZUZU, an AI desktop assistant.
Convert the user's natural-language command into a strict JSON object.
Only use actions from this list:
{sorted(ALLOWED_COMMANDS)}

Response format — always return valid JSON, nothing else.
Examples:
  {{"action": "open_chrome"}}
  {{"action": "open_calculator"}}
  {{"action": "open_settings"}}
  {{"action": "open_this_pc"}}
  {{"action": "open_notepad"}}
  {{"action": "open_explorer"}}
  {{"action": "open_application", "app_name": "Spotify"}}
  {{"action": "create_note", "content": "Tomorrow's meeting is at 9 AM."}}
  {{"action": "show_notes"}}
  {{"action": "search_notes", "query": "meeting"}}
  {{"action": "open_notes_file"}}
  {{"action": "create_reminder", "message": "Drink water", "time": "in 10 minutes"}}
  {{"action": "list_reminders"}}
  {{"action": "cancel_reminder", "reminder_id": 3}}
  {{"action": "search_store", "app_name": "WhatsApp"}}
  {{"action": "general_query", "response": "The answer is..."}}
  {{"action": "unknown"}}

Rules:
- Never return Python code or shell commands.
- Never invent actions not in the list.
- If the command is unclear or unsupported, return {{"action": "unknown"}}.
- For general knowledge questions, use "general_query" and put the answer in "response".
- Return only the JSON object — no markdown fences, no explanation.
"""


class AIHandler:
    """Wrapper around the Gemini API."""

    def __init__(self):
        self._client  = None
        self._ready   = False
        self._error   = ""

    def initialize(self) -> tuple[bool, str]:
        if not GEMINI_API_KEY:
            self._error = "GEMINI_API_KEY is not set. Add it to your .env file."
            log.warning(self._error)
            return False, self._error
        try:
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
            self._ready  = True
            log.info("Gemini AI handler ready (model: %s).", GEMINI_MODEL)
            return True, "Gemini ready."
        except ImportError:
            self._error = "google-genai not installed. Run: pip install google-genai"
            log.error(self._error)
            return False, self._error
        except Exception as exc:
            self._error = f"Gemini init failed: {exc}"
            log.error(self._error)
            return False, self._error

    def parse_command(self, user_text: str) -> dict:
        """
        Send user text to Gemini and return a validated command dict.
        Falls back to {"action": "unknown"} on any error.
        """
        if not self._ready or not self._client:
            log.warning("AI not ready — returning unknown")
            return {"action": "unknown", "_ai_error": self._error}

        try:
            from google import genai
            from google.genai import types

            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=256,
                ),
            )
            raw = response.text.strip()
            log.debug("Gemini raw response: %s", raw)
            return self._parse_json(raw)
        except Exception as exc:
            log.error("Gemini API error: %s", exc)
            return {"action": "unknown", "_ai_error": str(exc)}

    def _parse_json(self, raw: str) -> dict:
        # Strip markdown fences if model adds them
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.M).strip()
        raw = re.sub(r"\s*```$", "", raw, flags=re.M).strip()
        try:
            cmd = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("JSON parse error: %s |  raw=%s", exc, raw)
            return {"action": "unknown"}

        if not isinstance(cmd, dict):
            return {"action": "unknown"}

        action = cmd.get("action", "unknown")
        if action not in ALLOWED_COMMANDS:
            log.warning("Gemini returned disallowed action '%s' — blocking.", action)
            return {"action": "unknown"}

        return cmd

    @property
    def is_ready(self) -> bool:
        return self._ready
