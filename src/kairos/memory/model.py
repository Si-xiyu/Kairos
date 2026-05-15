from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"
    LIFE_PATTERN = "life_pattern"
    ENERGY_PATTERN = "energy_pattern"
    REFLECTION_THEME = "reflection_theme"


class MemoryScope(str, Enum):
    PRIVATE = "private"
    TEAM = "team"


@dataclass(frozen=True)
class MemoryEntry:
    name: str
    description: str
    type: MemoryType
    content: str
    scope: MemoryScope = MemoryScope.PRIVATE
    confidence: float = 0.5
    created_at: date = field(default_factory=date.today)
    updated_at: date = field(default_factory=date.today)
    source: str | None = None

    def to_markdown(self) -> str:
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "scope": self.scope.value,
            "confidence": str(self.confidence),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.source:
            frontmatter["source"] = self.source
        lines = ["---", *[f"{key}: {value}" for key, value in frontmatter.items()], "---", ""]
        return "\n".join(lines) + self.content.rstrip() + "\n"

    @classmethod
    def from_markdown(cls, text: str) -> "MemoryEntry":
        metadata, content = parse_frontmatter(text)
        return cls(
            name=metadata.get("name", ""),
            description=metadata.get("description", ""),
            type=MemoryType(metadata.get("type", MemoryType.USER.value)),
            scope=MemoryScope(metadata.get("scope", MemoryScope.PRIVATE.value)),
            confidence=float(metadata.get("confidence", "0.5")),
            created_at=date.fromisoformat(metadata.get("created_at", date.today().isoformat())),
            updated_at=date.fromisoformat(metadata.get("updated_at", date.today().isoformat())),
            source=metadata.get("source") or None,
            content=content.strip(),
        )


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = "\n---\n"
    end = text.find(marker, 4)
    if end == -1:
        return {}, text
    raw_metadata = text[4:end]
    content = text[end + len(marker) :]
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, content
