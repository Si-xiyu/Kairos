from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from kairos.config import KairosPaths


@dataclass(frozen=True)
class ScopePermissions:
    read: bool = True
    write: bool = False
    command: bool = False


@dataclass(frozen=True)
class ProjectScope:
    id: str
    name: str
    path: str
    permissions: dict[str, bool] = field(default_factory=lambda: asdict(ScopePermissions()))
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProjectScopeStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.path = paths.home / "project-scopes.json"

    def list(self) -> list[dict[str, Any]]:
        return [_to_api(item) for item in self._load()]

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        scopes = self._load()
        now = datetime.now(timezone.utc).isoformat()
        raw_path = _required_text(values, "path")
        resolved = _resolve_scope_path(self.paths, raw_path)
        scope = ProjectScope(
            id=str(values.get("id") or f"scope-{uuid4().hex[:12]}"),
            name=str(values.get("name") or resolved.name or raw_path),
            path=str(resolved),
            permissions=_permissions(values.get("permissions")),
            enabled=bool(values.get("enabled", True)),
            created_at=now,
            updated_at=now,
        )
        if any(item["id"] == scope.id for item in scopes):
            raise ValueError(f"Project Scope already exists: {scope.id}")
        scopes.append(asdict(scope))
        self._save(scopes)
        return _to_api(asdict(scope))

    def update(self, scope_id: str, values: dict[str, Any]) -> dict[str, Any]:
        scopes = self._load()
        for item in scopes:
            if item["id"] != scope_id:
                continue
            if "name" in values:
                item["name"] = _required_text(values, "name")
            if "path" in values:
                item["path"] = str(_resolve_scope_path(self.paths, str(values["path"])))
            if "permissions" in values:
                item["permissions"] = _permissions(values["permissions"])
            if "enabled" in values:
                item["enabled"] = bool(values["enabled"])
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(scopes)
            return _to_api(item)
        raise FileNotFoundError(f"Project Scope not found: {scope_id}")

    def delete(self, scope_id: str) -> bool:
        scopes = self._load()
        kept = [item for item in scopes if item["id"] != scope_id]
        deleted = len(kept) != len(scopes)
        if deleted:
            self._save(kept)
        return deleted

    def scope_for_path(self, value: str | Path, permission: str = "read") -> dict[str, Any] | None:
        target = Path(value).resolve()
        for scope in self.list():
            if not scope["enabled"]:
                continue
            root = Path(scope["path"]).resolve()
            if (target == root or target.is_relative_to(root)) and bool(scope["permissions"].get(permission, False)):
                return scope
        return None

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []

    def _save(self, scopes: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(scopes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _to_api(scope: dict[str, Any]) -> dict[str, Any]:
    permissions = _permissions(scope.get("permissions"))
    return {
        **scope,
        "permissions": permissions,
        "permission_summary": _permission_summary(permissions),
    }


def _permissions(value: object | None) -> dict[str, bool]:
    defaults = asdict(ScopePermissions())
    if isinstance(value, dict):
        for key in defaults:
            if key in value:
                defaults[key] = bool(value[key])
    return defaults


def _permission_summary(permissions: dict[str, bool]) -> str:
    enabled = [name for name, allowed in permissions.items() if allowed]
    return ", ".join(enabled) if enabled else "none"


def _resolve_scope_path(paths: KairosPaths, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = paths.root / candidate
    return candidate.resolve()


def _required_text(values: dict[str, Any], key: str) -> str:
    value = str(values.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value
