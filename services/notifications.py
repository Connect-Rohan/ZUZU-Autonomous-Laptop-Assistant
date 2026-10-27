"""
ZUZU – Windows Desktop Notifications
Uses plyer for cross-compatible toast notifications with a Windows fallback.
"""

import logging
import threading

log = logging.getLogger(__name__)


def send_notification(title: str, message: str, timeout: int = 8) -> bool:
    """
    Show a Windows desktop notification.
    Returns True on success.
    """
    # Try plyer first (works on Win 10/11)
    try:
        from plyer import notification as plyer_notif
        plyer_notif.notify(
            title=title,
            message=message,
            app_name="ZUZU Assistant",
            timeout=timeout,
        )
        log.info("Notification sent: %s", title)
        return True
    except Exception as exc:
        log.warning("plyer notification failed: %s — trying fallback", exc)

    # Fallback: Windows Script Host via powershell toast
    try:
        import subprocess
        ps_script = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            f"ContentType = WindowsRuntime] | Out-Null; "
            f"$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
            f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
            f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{title}')) | Out-Null; "
            f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{message}')) | Out-Null; "
            f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ZUZU').Show($toast);"
        )
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            timeout=5, capture_output=True
        )
        return True
    except Exception as exc2:
        log.error("PowerShell notification also failed: %s", exc2)
        return False


def send_reminder_notification(message: str) -> bool:
    return send_notification("⏰ ZUZU Reminder", message, timeout=10)


def send_async_notification(title: str, message: str):
    """Fire-and-forget notification in a daemon thread."""
    threading.Thread(
        target=send_notification, args=(title, message), daemon=True
    ).start()
