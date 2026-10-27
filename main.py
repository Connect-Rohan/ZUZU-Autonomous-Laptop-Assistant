"""
ZUZU – Main Entry Point
Wires together: GUI, voice input/output, wake-word, AI, and command execution.
Run with: python main.py
"""

import logging
import threading
import sys

# ── Logging setup (before all imports) ────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("zuzu.main")

# ── Core imports ───────────────────────────────────────────────
from config import (
    WAKE_PHRASE, SPEECH_TIMEOUT, PHRASE_TIME_LIMIT,
    ENERGY_THRESHOLD, TTS_RATE, TTS_VOLUME, GEMINI_API_KEY
)


class ZUZUApp:
    """
    Top-level controller.  Owns all sub-systems and the GUI.
    Background work runs on daemon threads; GUI updates go via ui.post().
    """

    def __init__(self):
        self.ui            = None
        self.voice_in      = None
        self.voice_out     = None
        self.wake_detector = None
        self.ai_handler    = None
        self.reminder_sched = None
        self._listening    = False
        self._processing   = False
        self._shutdown     = threading.Event()

    # ── Initialization ─────────────────────────────────────────

    def _init_ui(self):
        from ui.assistant_window import AssistantWindow
        self.ui = AssistantWindow(
            on_text_command  = self._handle_text_command,
            on_toggle_listen = self._toggle_listen,
            on_quit          = self._shutdown_all,
        )

    def _init_voice(self):
        from assistant.voice_input  import VoiceInput
        from assistant.voice_output import VoiceOutput

        self.voice_in  = VoiceInput(
            energy_threshold  = ENERGY_THRESHOLD,
            timeout           = SPEECH_TIMEOUT,
            phrase_time_limit = PHRASE_TIME_LIMIT,
        )
        self.voice_out = VoiceOutput(rate=TTS_RATE, volume=TTS_VOLUME)

        ok_tts, tts_msg = self.voice_out.initialize()
        if not ok_tts:
            self.ui.add_history(f"⚠ TTS: {tts_msg}")

        ok_mic, mic_msg = self.voice_in.initialize()
        if ok_mic:
            self.ui.update_status("Listening for 'Hey ZUZU'…")
            self.ui.set_state("listening", "Listening for 'Hey ZUZU'…")
        else:
            self.ui.show_error(f"Mic unavailable: {mic_msg}")
            self.ui.add_history(f"⚠ {mic_msg}")
            self.ui.add_history("Use the text input below to send commands.")

        return ok_mic

    def _init_ai(self):
        from assistant.ai_handler import AIHandler
        self.ai_handler = AIHandler()
        ok, msg = self.ai_handler.initialize()
        if ok:
            self.ui.add_history("✓ Gemini AI connected.")
        else:
            self.ui.add_history(f"⚠ AI: {msg} — local commands still work.")

    def _init_wake_detector(self):
        from assistant.wake_word import WakeWordDetector
        self.wake_detector = WakeWordDetector(
            voice_input = self.voice_in,
            on_wake     = self._on_wake_phrase,
        )
        self.wake_detector.set_tts_speaking_event(self.voice_out.is_speaking)
        self.wake_detector.start()
        self._listening = True

    def _init_reminder_scheduler(self):
        from services.reminders import ReminderScheduler
        self.reminder_sched = ReminderScheduler(
            on_reminder=self._on_reminder_due
        )
        self.reminder_sched.start()

    def _on_reminder_due(self, message: str):
        from services.notifications import send_reminder_notification
        send_reminder_notification(message)
        if self.voice_out:
            self.voice_out.speak(f"Reminder: {message}")
        if self.ui:
            self.ui.add_history(f"⏰ REMINDER: {message}")
            self.ui.show_transcript(f"[Reminder] {message}")

    # ── Wake word callback ─────────────────────────────────────

    def _on_wake_phrase(self):
        """Called (on wake detector thread) when 'Hey ZUZU' is detected."""
        if self._processing:
            return

        log.info("Wake phrase detected — capturing command…")
        self.ui.set_state("listening", "Hey ZUZU detected! Listening for command…")
        self.ui.show_transcript("Hey ZUZU detected…")
        if self.voice_out:
            self.voice_out.speak("Yes?")

        # Brief pause so TTS "Yes?" finishes before we listen
        import time; time.sleep(1.2)

        text, err = self.voice_in.listen_once(
            timeout=SPEECH_TIMEOUT, phrase_time_limit=PHRASE_TIME_LIMIT
        )
        if text:
            self.ui.show_transcript(text)
            self._process_command(text)
        else:
            self.ui.set_state("listening", "Listening for 'Hey ZUZU'…")
            self.ui.show_transcript(f"Didn't catch that: {err}")
            if err:
                self.voice_out.speak("I didn't catch that. Please try again.")

    # ── Text fallback ──────────────────────────────────────────

    def _handle_text_command(self, text: str):
        """Called when user submits a typed command."""
        self._process_command(text)

    # ── Core processing pipeline ───────────────────────────────

    def _process_command(self, text: str):
        if self._processing:
            return
        self._processing = True

        try:
            self.ui.set_state("processing", "Working…")
            self.ui.add_history(f"▶ {text}")

            # Step 1: try local matcher first
            from assistant.command_router import local_match, validate_command, execute_command
            cmd = local_match(text)

            # Step 2: fall back to Gemini
            if cmd is None:
                if self.ai_handler and self.ai_handler.is_ready:
                    self.ui.update_status("Thinking…")
                    cmd = self.ai_handler.parse_command(text)
                else:
                    cmd = {"action": "unknown"}

            # Step 3: validate
            ok, reason = validate_command(cmd)
            if not ok:
                log.warning("Invalid command blocked: %s | reason: %s", cmd, reason)
                result = "I can't do that — the action isn't supported."
            else:
                result = execute_command(cmd, ui=self.ui, tts=self.voice_out)

            log.info("Result: %s", result)
            self.ui.add_history(f"✓ {result}")
            self.ui.show_transcript(result[:120])

            # Speak the result
            if self.voice_out:
                self.ui.set_state("speaking", "Speaking…")
                self.voice_out.speak(result)
                # Wait a moment for speech to begin
                import time; time.sleep(0.5)

        except Exception as exc:
            log.error("Processing error: %s", exc, exc_info=True)
            self.ui.show_error(str(exc)[:80])
        finally:
            self._processing = False
            self.ui.set_state("listening", "Listening for 'Hey ZUZU'…")

    # ── Toggle listen button ───────────────────────────────────

    def _toggle_listen(self):
        if not self.wake_detector:
            return
        if self._listening:
            self.wake_detector.stop()
            self._listening = False
            self.ui.set_state("idle", "Listening paused — press Start to resume.")
        else:
            self._init_wake_detector()
            self._listening = True
            self.ui.set_state("listening", "Listening for 'Hey ZUZU'…")

    # ── Shutdown ───────────────────────────────────────────────

    def _shutdown_all(self):
        log.info("Shutting down ZUZU…")
        self._shutdown.set()
        if self.wake_detector:
            self.wake_detector.stop()
        if self.voice_out:
            self.voice_out.stop()
        if self.reminder_sched:
            self.reminder_sched.stop()

    # ── Start ──────────────────────────────────────────────────

    def run(self):
        # Build GUI on main thread first
        self._init_ui()
        self.ui.set_state("idle", "Initializing…")

        # Heavy init in background so GUI appears immediately
        def _bg_init():
            ok_mic = self._init_voice()
            self._init_ai()
            self._init_reminder_scheduler()
            if ok_mic:
                self._init_wake_detector()
            self.ui.add_history("✓ ZUZU ready. Say 'Hey ZUZU' to start.")

        threading.Thread(target=_bg_init, daemon=True, name="ZUZU-Init").start()

        # Blocks until window closes
        self.ui.run()


# ── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    app = ZUZUApp()
    app.run()
