"""
ZUZU – Voice Output (pyttsx3)
Runs TTS in a dedicated daemon thread to avoid blocking the GUI.
"""

import logging
import threading
import queue

log = logging.getLogger(__name__)

try:
    import pyttsx3
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    log.error("pyttsx3 not installed. Run: pip install pyttsx3")


class VoiceOutput:
    """Thread-safe TTS wrapper. Call speak(text) from any thread."""

    def __init__(self, rate=165, volume=0.9):
        self._rate    = rate
        self._volume  = volume
        self._queue   = queue.Queue()
        self._engine  = None
        self._thread  = None
        self._running = False
        self.is_speaking = threading.Event()

    def initialize(self) -> tuple[bool, str]:
        if not _TTS_AVAILABLE:
            return False, "pyttsx3 not installed."
        try:
            # Engine must be created on its own thread
            self._running = True
            self._thread  = threading.Thread(
                target=self._tts_loop, daemon=True, name="TTS-Thread")
            self._thread.start()
            log.info("TTS engine started.")
            return True, "TTS ready."
        except Exception as exc:
            return False, f"TTS init failed: {exc}"

    def _tts_loop(self):
        """Runs pyttsx3 event loop on its own thread."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            # Prefer a clear English voice if available
            voices = engine.getProperty("voices")
            for v in voices:
                if "zira" in v.name.lower() or "david" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            self._engine = engine

            while self._running:
                try:
                    text = self._queue.get(timeout=0.2)
                    if text is None:   # poison pill
                        break
                    self.is_speaking.set()
                    engine.say(text)
                    engine.runAndWait()
                    self.is_speaking.clear()
                except queue.Empty:
                    pass
                except Exception as exc:
                    log.error("TTS error: %s", exc)
                    self.is_speaking.clear()
        except Exception as outer:
            log.error("TTS loop crashed: %s", outer)

    def speak(self, text: str):
        """Queue text for speech. Non-blocking."""
        if not text:
            return
        if not _TTS_AVAILABLE:
            log.info("[TTS unavailable] Would say: %s", text)
            return
        log.info("TTS ▶ %s", text)
        self._queue.put(text)

    def stop(self):
        self._running = False
        self._queue.put(None)   # poison pill


def is_available() -> bool:
    return _TTS_AVAILABLE
