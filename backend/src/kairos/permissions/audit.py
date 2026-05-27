from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from kairos.config import KairosPaths


@dataclass(frozen=True)
class AuditEvent:
    action: str
    decision: str
    reason: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.paths.audit.mkdir(parents=True, exist_ok=True)
        self.path = self.paths.audit / "tool-calls.jsonl"

    def append(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
