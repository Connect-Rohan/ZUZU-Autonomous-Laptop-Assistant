"""
ZUZU – Voice Input (SpeechRecognition)
Uses Google Web Speech API (online). Swap recognizer in recognize() for offline later.

NOTE: This is internet-based speech recognition — not an offline model.
"""

import logging
import threading
import queue

log = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False
    log.error("SpeechRecognition not installed. Run: pip install SpeechRecognition pyaudio")


def is_available() -> bool:
    return _SR_AVAILABLE


class VoiceInput:
    """
    Manages a single microphone resource.
    Exposes blocking listen() and stop() methods.
    """

    def __init__(self, energy_threshold=300, timeout=5, phrase_time_limit=10):
        self._energy_threshold  = energy_threshold
        self._timeout           = timeout
        self._phrase_time_limit = phrase_time_limit
        self._recognizer        = None
        self._mic               = None
        self._stop_flag         = threading.Event()
        self._init_error        = None
        self._initialized       = False
        self._mic_lock          = threading.Lock()

    def initialize(self) -> tuple[bool, str]:
        if not _SR_AVAILABLE:
            msg = "SpeechRecognition library is missing."
            self._init_error = msg
            return False, msg
        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self._energy_threshold
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.8
            # Test microphone availability
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.5)
            self._initialized = True
            log.info("Microphone initialized.")
            return True, "Microphone ready."
        except OSError as exc:
            msg = f"Microphone not accessible: {exc}"
            self._init_error = msg
            log.error(msg)
            return False, msg

    def listen_once(self, timeout=None, phrase_time_limit=None) -> tuple[str | None, str]:
        """
        Capture one utterance from the microphone.
        Returns (text, error_message).  text is None on failure.
        """
        if not self._initialized:
            return None, self._init_error or "Not initialized."

        t   = timeout or self._timeout
        ptl = phrase_time_limit or self._phrase_time_limit

        try:
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.2)
                try:
                    audio = self._recognizer.listen(src, timeout=t, phrase_time_limit=ptl)
                except sr.WaitTimeoutError:
                    return None, "Listening timed out."

            text = self._recognizer.recognize_google(audio)
            log.info("Recognized: %s", text)
            return text, ""
        except sr.UnknownValueError:
            return None, "Could not understand audio."
        except sr.RequestError as exc:
            return None, f"Speech service error: {exc}. Check your internet connection."
        except OSError as exc:
            return None, f"Microphone error: {exc}"

    def stop(self):
        self._stop_flag.set()
