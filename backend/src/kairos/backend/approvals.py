from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import uuid4

from kairos.config import KairosPaths

ApprovalStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class ApprovedAction:
    id: str
    action_type: str
    title: str
    summary: str
    payload: dict[str, Any]
    status: ApprovalStatus = "pending"
    source: str = "kairos"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ApprovalStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.path = paths.home / "approvals.json"

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        items = self._load()
        if status:
            items = [item for item in items if item.get("status") == status]
        return sorted(items, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        items = self._load()
        now = datetime.now(timezone.utc).isoformat()
        action = ApprovedAction(
            id=str(values.get("id") or f"approval-{uuid4().hex[:12]}"),
            action_type=_required_text(values, "action_type"),
            title=_required_text(values, "title"),
            summary=str(values.get("summary", "")),
            payload=dict(values.get("payload", {})),
            status=_status(values.get("status", "pending")),
            source=str(values.get("source", "kairos")),
            created_at=now,
            updated_at=now,
        )
        items.append(asdict(action))
        self._save(items)
        return asdict(action)

    def set_status(self, approval_id: str, status: ApprovalStatus) -> dict[str, Any]:
        items = self._load()
        for item in items:
            if item["id"] == approval_id:
                item["status"] = _status(status)
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(items)
                return item
        raise FileNotFoundError(f"Approved Action not found: {approval_id}")

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _status(value: object) -> ApprovalStatus:
    text = str(value)
    if text not in {"pending", "approved", "rejected"}:
        raise ValueError("status must be one of: approved, pending, rejected")
    return text  # type: ignore[return-value]


def _required_text(values: dict[str, Any], key: str) -> str:
    value = str(values.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value
