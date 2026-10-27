"""
ZUZU – Windows Application Launcher
Uses OS-native launch mechanisms; never invents paths.
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path

log = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────

def _run(*args, **kwargs) -> bool:
    """Start a subprocess; return True on success."""
    try:
        subprocess.Popen(list(args), **kwargs)
        return True
    except FileNotFoundError:
        log.warning("Not found: %s", args)
        return False
    except OSError as exc:
        log.error("OSError launching %s: %s", args, exc)
        return False


def _startfile(target: str) -> bool:
    """os.startfile wrapper; return True on success."""
    try:
        os.startfile(target)   # type: ignore[attr-defined]
        return True
    except OSError as exc:
        log.error("startfile(%s) failed: %s", target, exc)
        return False


def _find_chrome() -> str | None:
    """Search common Chrome installation paths on Windows."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return shutil.which("chrome") or shutil.which("google-chrome")


# ── Public launcher functions ──────────────────────────────────

def open_chrome(url: str = "") -> tuple[bool, str]:
    exe = _find_chrome()
    if exe:
        args = [exe]
        if url:
            args.append(url)
        ok = _run(*args)
        return ok, "Chrome opened." if ok else "Failed to open Chrome."
    # Fallback: let Windows find it
    ok = _startfile("chrome")
    return ok, "Chrome opened." if ok else (
        "Chrome not found. Please install Google Chrome.")


def open_notepad(filepath: str = "") -> tuple[bool, str]:
    args = ["notepad.exe"]
    if filepath:
        args.append(filepath)
    ok = _run(*args)
    return ok, "Notepad opened." if ok else "Failed to open Notepad."


def open_calculator() -> tuple[bool, str]:
    # Modern Windows: calc.exe is a launcher stub that opens the UWP app
    ok = _run("calc.exe")
    if not ok:
        ok = _startfile("calculator:")   # URI scheme
    return ok, "Calculator opened." if ok else "Failed to open Calculator."


def open_explorer(path: str = "") -> tuple[bool, str]:
    if path:
        ok = _run("explorer.exe", path)
    else:
        ok = _run("explorer.exe")
    return ok, "File Explorer opened." if ok else "Failed to open File Explorer."


def open_this_pc() -> tuple[bool, str]:
    # ::{20D04FE0-3AEA-1069-A2D8-08002B30309D} is the CLSID for This PC
    ok = _run("explorer.exe", "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}")
    return ok, "Opened This PC." if ok else "Failed to open This PC."


def open_settings() -> tuple[bool, str]:
    ok = _startfile("ms-settings:")
    if not ok:
        ok = _run("start", "ms-settings:", shell=True)
    return ok, "Windows Settings opened." if ok else "Failed to open Settings."


def open_store(search_query: str = "") -> tuple[bool, str]:
    if search_query:
        # ms-windows-store://search/?query=<term> is documented by Microsoft
        uri = f"ms-windows-store://search/?query={search_query.replace(' ', '+')}"
    else:
        uri = "ms-windows-store:"
    ok = _startfile(uri)
    if not ok:
        # backup via explorer
        ok = _run("explorer.exe", uri)
    msg = (
        f"Microsoft Store opened, searching for '{search_query}'."
        if search_query else "Microsoft Store opened."
    )
    return ok, msg if ok else "Failed to open Microsoft Store."


# ── Dispatcher ─────────────────────────────────────────────────

APP_DISPATCH = {
    "chrome":       open_chrome,
    "notepad":      open_notepad,
    "calculator":   open_calculator,
    "calc":         open_calculator,
    "explorer":     open_explorer,
    "file explorer": open_explorer,
    "this pc":      open_this_pc,
    "my pc":        open_this_pc,
    "settings":     open_settings,
    "windows settings": open_settings,
    "store":        open_store,
    "microsoft store": open_store,
}


def launch_app_by_name(name: str) -> tuple[bool, str]:
    """Try to launch an application by its common name."""
    key = name.lower().strip()
    fn  = APP_DISPATCH.get(key)
    if fn:
        return fn()
    return False, f"Application '{name}' is not in ZUZU's allowed list."
