from __future__ import annotations

import platform
import subprocess

from .base import Channel


class CLIChannel(Channel):
    name = "cli"

    def send(self, to: str, text: str, **kwargs: object) -> bool:
        print(f"[kairos:{self.name}:{to}] {text}")
        return True


class WindowsToastChannel(Channel):
    """Best-effort local Windows notification channel."""

    name = "windows_toast"

    def send(self, to: str, text: str, **kwargs: object) -> bool:
        if platform.system().lower() != "windows":
            return False
        title = str(kwargs.get("title") or to or "Kairos")
        script = _toast_script(title=title, text=text)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
        except OSError:
            return False
        return True


def _toast_script(title: str, text: str) -> str:
    return (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.BalloonTipTitle = '" + _ps_single_quote(title) + "'; "
        "$n.BalloonTipText = '" + _ps_single_quote(text) + "'; "
        "$n.Visible = $true; "
        "$n.ShowBalloonTip(5000); "
        "Start-Sleep -Seconds 6; "
        "$n.Dispose();"
    )


def _ps_single_quote(value: str) -> str:
    return value.replace("'", "''").replace("\r", " ").replace("\n", " ")
