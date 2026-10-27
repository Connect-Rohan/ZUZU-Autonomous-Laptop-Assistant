"""
ZUZU – Wake Word Detection
Implementation: Speech transcription + text matching.
NOTE: This is NOT a dedicated wake-word model. It uses the Google Web Speech API
to transcribe short audio chunks and looks for the phrase "hey zuzu".
A future version may replace this with an offline model such as Porcupine or openWakeWord.
"""

import logging
import threading

from config import WAKE_PHRASE

log = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Continuously samples the microphone in short bursts and checks for WAKE_PHRASE.
    When detected, calls on_wake() callback on the detector's thread.
    """

    def __init__(self, voice_input, on_wake=None):
        self._voice_input = voice_input
        self._on_wake     = on_wake or (lambda: None)
        self._stop_event  = threading.Event()
        self._thread      = None
        self._active      = False
        self._tts_speaking = None   # injected by main to suppress self-listening

    def set_tts_speaking_event(self, event: threading.Event):
        """Pass the TTS is_speaking event so we skip listening during speech."""
        self._tts_speaking = event

    def start(self):
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._detect_loop, daemon=True, name="WakeWordDetector")
        self._thread.start()
        log.info("Wake word detector started (phrase: '%s')", WAKE_PHRASE)

    def stop(self):
        self._active = False
        self._stop_event.set()

    def _detect_loop(self):
        while not self._stop_event.is_set():
            # Don't listen while ZUZU is speaking (prevents echo loop)
            if self._tts_speaking and self._tts_speaking.is_set():
                self._stop_event.wait(timeout=0.3)
                continue

            text, err = self._voice_input.listen_once(timeout=4, phrase_time_limit=5)

            if self._stop_event.is_set():
                break

            if text:
                log.debug("Wake scan heard: %s", text)
                if WAKE_PHRASE in text.lower():
                    log.info("Wake phrase detected!")
                    try:
                        self._on_wake()
                    except Exception as exc:
                        log.error("Wake callback error: %s", exc)
