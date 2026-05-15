from __future__ import annotations

from abc import ABC, abstractmethod


class Channel(ABC):
    """Outbound channel contract for gateway implementations."""

    name: str

    @abstractmethod
    def send(self, to: str, text: str, **kwargs: object) -> bool:
        """Send text to a recipient and return whether delivery succeeded."""

