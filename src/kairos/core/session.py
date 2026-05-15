from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from kairos.config import KairosPaths

Role = Literal["system", "user", "assistant", "tool"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionEvent:
    role: Role
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionStore:
    """Append-only JSONL session storage."""

    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.paths.conversations.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        safe = _safe_name(session_id)
        return self.paths.conversations / f"{safe}.jsonl"

    def append(self, session_id: str, event: SessionEvent) -> Path:
        path = self.path_for(session_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return path

    def read(self, session_id: str) -> list[SessionEvent]:
        path = self.path_for(session_id)
        if not path.exists():
            return []
        events: list[SessionEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            events.append(SessionEvent(**data))
        return events


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    return cleaned.strip("._") or "default"
