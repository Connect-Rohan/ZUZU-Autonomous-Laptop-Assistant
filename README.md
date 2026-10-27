# ZUZU — AI Autonomous Laptop Assistant

![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey) ![AI](https://img.shields.io/badge/AI-Google%20Gemini-orange)

**ZUZU** is a voice-controlled AI desktop assistant that runs on Windows. Say "Hey ZUZU" to launch apps, create notes, set reminders, and ask general questions — all from a beautiful animated desktop interface.

---

## Requirements

- Python **3.11** or **3.12**
- Windows 10 or Windows 11
- A working microphone (optional — typed fallback is available)
- A **Google Gemini API key** (free at [Google AI Studio](https://aistudio.google.com/app/apikey))

---

## Step-by-Step Setup

### 1 – Create a virtual environment

Open **PowerShell** in the project folder (`ZUZUUUU`) and run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> If you get an execution policy error, run first:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 2 – Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

> **PyAudio note:** If `pyaudio` fails to install, download the matching `.whl` from
> [https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)
> and install it manually:
> ```powershell
> pip install PyAudio‑0.2.14‑cpXX‑cpXX‑win_amd64.whl
> ```

### 3 – Configure your API key

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace `PASTE_YOUR_GOOGLE_AI_STUDIO_API_KEY_HERE` with your real key.  
The `.env` file is **git-ignored** and never committed.

### 4 – Launch ZUZU

```powershell
python main.py
```

The ZUZU window will open. Initialization takes a few seconds.

---

## Voice Commands

| Say…                                        | Action                          |
|---------------------------------------------|---------------------------------|
| Hey ZUZU, open Chrome                       | Launches Google Chrome          |
| Hey ZUZU, open Calculator                   | Launches Calculator             |
| Hey ZUZU, open Notepad                      | Launches Notepad                |
| Hey ZUZU, open File Explorer                | Opens File Explorer             |
| Hey ZUZU, open This PC                      | Opens This PC view              |
| Hey ZUZU, open Settings                     | Opens Windows Settings          |
| Hey ZUZU, open Microsoft Store              | Opens Microsoft Store           |
| Hey ZUZU, open Store and search for Spotify | Searches Store for Spotify      |
| Hey ZUZU, make a note that…                 | Saves a note with timestamp     |
| Hey ZUZU, show recent notes                 | Displays last 5 notes           |
| Hey ZUZU, open notes file                   | Exports & opens notes in Notepad |
| Hey ZUZU, search notes for meeting          | Searches notes                  |
| Hey ZUZU, remind me in 10 minutes to…       | Sets a reminder                 |
| Hey ZUZU, remind me tomorrow at 8 AM about… | Sets a future reminder          |
| Hey ZUZU, list reminders                    | Shows upcoming reminders        |
| Hey ZUZU, cancel reminder #2                | Cancels reminder by number      |

You can also type any command in the text box and click **Send** without needing a microphone.

---

## Running Tests

```powershell
pip install pytest
python -m pytest tests/ -v
```

---

## Data Storage

| File                        | Contents                        |
|-----------------------------|---------------------------------|
| `data/notes.db`             | SQLite notes database           |
| `data/notes_export.txt`     | Plain-text export (on demand)   |
| `data/reminders.db`         | SQLite reminders database       |

---

## Features Requiring Internet

| Feature              | Requires Internet? |
|----------------------|--------------------|
| Voice recognition    | ✅ Yes (Google Web Speech API) |
| Gemini AI commands   | ✅ Yes              |
| App launching        | ❌ No               |
| Notes system         | ❌ No               |
| Reminders            | ❌ No               |
| Notifications        | ❌ No               |

---

## Prototype Limitations

1. **Wake-word detection** uses Google Web Speech transcription + text match, not an offline wake-word model. It requires internet and briefly sends audio to Google's servers.
2. **Reminders only trigger while ZUZU is running.** Windows Task Scheduler integration is planned for a future version.
3. **Microsoft Store installs** require the user to click Install inside the Store window. ZUZU does not install apps silently.
4. **Microphone conflicts** — if another application holds the microphone, ZUZU will show an error and fall back to text input.

---

## Troubleshooting

| Problem                        | Solution                                                  |
|--------------------------------|-----------------------------------------------------------|
| `ModuleNotFoundError: pyaudio` | Install PyAudio wheel manually (see setup step 2)         |
| `GEMINI_API_KEY not set`        | Copy `.env.example` → `.env` and add your key             |
| Microphone not detected        | Check Windows privacy settings → Microphone allowed       |
| `SpeechRecognition` not hearing | Increase `ENERGY_THRESHOLD` in `config.py` (default 300)  |
| Window doesn't open            | Ensure you have activated the virtual environment          |
| Reminder not firing            | ZUZU must remain open; check `list reminders` command     |

---

## Demo Script (for Supervisor)

```
1. "Hey ZUZU, open Chrome"          → Chrome launches
2. "Hey ZUZU, open Calculator"      → Calculator opens
3. "Hey ZUZU, make a note that our AI project demo is on Friday at 3 PM"
                                    → Note saved with timestamp
4. "Hey ZUZU, show recent notes"    → Reads back the note
5. "Hey ZUZU, remind me in 1 minute to check the slides"
                                    → Reminder set; fires 1 minute later
6. "Hey ZUZU, open Microsoft Store and search for WhatsApp"
                                    → Store opens with WhatsApp search
```

---

## Project Structure

```
ZUZUUUU/
├── main.py               ← Entry point
├── config.py             ← All settings (loaded from .env)
├── requirements.txt
├── .env.example
├── assistant/
│   ├── ai_handler.py     ← Gemini API integration
│   ├── command_router.py ← Local pattern matching + execution
│   ├── voice_input.py    ← SpeechRecognition microphone
│   ├── voice_output.py   ← pyttsx3 TTS
│   └── wake_word.py      ← "Hey ZUZU" detection
├── automation/
│   ├── windows_apps.py   ← App launchers (Chrome, Notepad, etc.)
│   └── store.py          ← Microsoft Store workflow
├── services/
│   ├── notes.py          ← SQLite notes
│   ├── reminders.py      ← SQLite reminders + scheduler
│   └── notifications.py  ← Windows desktop notifications
├── ui/
│   └── assistant_window.py ← Animated Tkinter GUI
├── tests/
│   └── test_zuzu.py      ← Unit tests
└── data/                 ← Runtime databases (git-ignored)
```
