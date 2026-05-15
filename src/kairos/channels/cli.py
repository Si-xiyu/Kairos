from __future__ import annotations

from .base import Channel


class CLIChannel(Channel):
    name = "cli"

    def send(self, to: str, text: str, **kwargs: object) -> bool:
        print(f"[kairos:{self.name}:{to}] {text}")
        return True


class WindowsToastChannel(Channel):
    """Placeholder for future Windows toast integration."""

    name = "windows_toast"

    def send(self, to: str, text: str, **kwargs: object) -> bool:
        return True
