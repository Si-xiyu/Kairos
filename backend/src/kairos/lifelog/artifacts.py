from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from kairos.config import KairosPaths

ArtifactType = Literal["diary", "record"]
SourceKind = Literal["chat", "manual", "import", "kairos"]


@dataclass(frozen=True)
class JournalArtifact:
    id: str
    type: ArtifactType
    title: str
    body: str
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    tags: list[str] = field(default_factory=list)
    source: dict[str, str | None] = field(default_factory=lambda: {"kind": "manual", "session_id": None})
    date: str | None = None
    summary: str | None = None


class JournalArtifactStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.base_dir = paths.journal / "artifacts"

    def list(self, artifact_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        artifacts = [self._read(path) for path in self._paths()]
        if artifact_type:
            artifacts = [item for item in artifacts if item["type"] == artifact_type]
        artifacts.sort(key=lambda item: str(item["updated_at"]), reverse=True)
        return [self._summary(item) for item in artifacts[:limit]]

    def read(self, artifact_id: str) -> dict[str, Any]:
        return self._read(self._path_for_id(artifact_id))

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        artifact = JournalArtifact(
            id=str(values.get("id") or _new_id("journal")),
            type=_literal(values.get("type", "record"), {"diary", "record"}, "type"),
            title=_required_text(values, "title"),
            body=str(values.get("body", values.get("content", ""))).rstrip(),
            created_at=now,
            updated_at=now,
            tags=_tags(values.get("tags")),
            source=_source(values.get("source")),
            date=_date_value(values.get("date")),
            summary=_optional_str(values.get("summary")),
        )
        if artifact.type == "diary" and artifact.date is None:
            artifact = _replace_artifact(artifact, date=date.today().isoformat())
        path = self._path_for_id(artifact.id)
        if path.exists():
            raise ValueError(f"Journal artifact already exists: {artifact.id}")
        self._write(path, artifact)
        return self.read(artifact.id)

    def update(self, artifact_id: str, values: dict[str, Any]) -> dict[str, Any]:
        current = self.read(artifact_id)
        updated = JournalArtifact(
            id=current["id"],
            type=_literal(values.get("type", current["type"]), {"diary", "record"}, "type"),
            title=_required_text({**current, **values}, "title"),
            body=str(values.get("body", values.get("content", current["body"]))).rstrip(),
            created_at=str(current["created_at"]),
            updated_at=_now(),
            tags=_tags(values.get("tags", current.get("tags", []))),
            source=_source(values.get("source", current.get("source"))),
            date=_date_value(values.get("date", current.get("date"))),
            summary=_optional_str(values.get("summary", current.get("summary"))),
        )
        if updated.type == "diary" and updated.date is None:
            updated = _replace_artifact(updated, date=date.today().isoformat())
        self._write(self._path_for_id(artifact_id), updated)
        return self.read(artifact_id)

    def delete(self, artifact_id: str) -> bool:
        path = self._path_for_id(artifact_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _paths(self) -> list[Path]:
        if not self.base_dir.exists():
            return []
        return sorted(self.base_dir.glob("*.md"))

    def _path_for_id(self, artifact_id: str) -> Path:
        clean = _slug(str(artifact_id))
        if not clean:
            raise ValueError("artifact id is required")
        return self.base_dir / f"{clean}.md"

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Journal artifact not found: {path.stem}")
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        data = _parse_frontmatter(frontmatter)
        data["id"] = path.stem
        data["body"] = body.rstrip()
        data["content"] = data["body"]
        data.setdefault("tags", [])
        data.setdefault("source", {"kind": "manual", "session_id": None})
        data.setdefault("summary", None)
        data.setdefault("date", None)
        return data

    def _write(self, path: Path, artifact: JournalArtifact) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter: dict[str, Any] = {
            "type": artifact.type,
            "title": artifact.title,
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
            "tags": artifact.tags,
            "source": artifact.source,
        }
        if artifact.type == "diary":
            frontmatter["date"] = artifact.date
        if artifact.type == "record" and artifact.summary:
            frontmatter["summary"] = artifact.summary
        path.write_text(_format_artifact(frontmatter, artifact.body), encoding="utf-8")

    def _summary(self, artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": artifact["id"],
            "type": artifact["type"],
            "title": artifact["title"],
            "created_at": artifact["created_at"],
            "updated_at": artifact["updated_at"],
            "tags": artifact.get("tags", []),
            "source": artifact.get("source", {"kind": "manual", "session_id": None}),
            "date": artifact.get("date"),
            "summary": artifact.get("summary"),
            "preview": _preview(artifact.get("body", "")),
        }


def _format_artifact(frontmatter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(_quote(item) for item in value)}]")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for child_key, child_value in value.items():
                lines.append(f"  {child_key}: {_quote(child_value)}")
        else:
            lines.append(f"{key}: {_quote(value)}")
    lines.extend(["---", "", body.rstrip(), ""])
    return "\n".join(lines)


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    _, rest = text.split("---\n", 1)
    frontmatter, body = rest.split("\n---\n", 1)
    return frontmatter, body


def _parse_frontmatter(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_parent: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and current_parent:
            key, value = line.strip().split(":", 1)
            parent = data.setdefault(current_parent, {})
            if isinstance(parent, dict):
                parent[key.strip()] = _unquote(value.strip())
            continue
        current_parent = None
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = {}
            current_parent = key
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [] if not inner else [_unquote(item.strip()) for item in inner.split(",")]
        else:
            data[key] = _unquote(value)
    return data


def _replace_artifact(artifact: JournalArtifact, **changes: Any) -> JournalArtifact:
    data = artifact.__dict__ | changes
    return JournalArtifact(**data)


def _source(value: object | None) -> dict[str, str | None]:
    if not isinstance(value, dict):
        return {"kind": "manual", "session_id": None}
    kind = _literal(value.get("kind", "manual"), {"chat", "manual", "import", "kairos"}, "source.kind")
    session_id = _optional_str(value.get("session_id"))
    return {"kind": kind, "session_id": session_id}


def _tags(value: object | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _date_value(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)).isoformat()


def _required_text(values: dict[str, Any], key: str) -> str:
    value = str(values.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _literal(value: object, allowed: set[str], name: str) -> Any:
    text = str(value)
    if text not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return text


def _quote(value: object) -> str:
    if value is None:
        return "null"
    text = str(value)
    if text == "" or any(char in text for char in ":#[]{}\","):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _unquote(value: str) -> str | None:
    if value == "null":
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:80]


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(body: str, limit: int = 180) -> str:
    text = " ".join(line.strip() for line in body.splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
