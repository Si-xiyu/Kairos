from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PresenceEvent:
    kind: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PresenceEvent":
        return cls(
            kind=str(payload.get("kind", "presence_event")),
            event=str(payload["event"]),
            payload=dict(payload.get("payload", {})),
        )
