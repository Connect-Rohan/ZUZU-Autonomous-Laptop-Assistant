"""
ZUZU – Microsoft Store Search & Safe Install Workflow
"""

import logging
from automation.windows_apps import open_store

log = logging.getLogger(__name__)


def search_store(app_name: str) -> tuple[bool, str]:
    """
    Open Microsoft Store and search for an app.
    Uses the official ms-windows-store URI scheme.
    """
    if not app_name or not app_name.strip():
        return open_store()
    ok, msg = open_store(search_query=app_name.strip())
    return ok, msg


def request_install_confirmation(app_name: str) -> str:
    """
    Return a user-facing message asking for confirmation.
    Actual install happens only in the Store UI (no silent installs).
    """
    return (
        f"I've opened the Store page for '{app_name}'. "
        "Please review the app and click Install in the Store window. "
        "ZUZU does not install apps automatically — your confirmation in the Store is required."
    )
