"""Memory data model."""

from datetime import date
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


class MemoryType(str, Enum):
    """Types of memory entries."""

    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"
    LIFE_PATTERN = "life_pattern"
    ENERGY_PATTERN = "energy_pattern"
    REFLECTION_THEME = "reflection_theme"


class MemoryScope(str, Enum):
    """Scope of memory visibility."""

    PRIVATE = "private"
    SHARED = "shared"


@dataclass
class MemoryEntry:
    """A single memory entry stored in the memory system."""

    name: str
    description: str
    type: MemoryType
    scope: MemoryScope = MemoryScope.PRIVATE
    confidence: float = 0.5
    created_at: date = field(default_factory=date.today)
    updated_at: date = field(default_factory=date.today)
    source: Optional[str] = None
    content: str = ""

    def to_frontmatter(self) -> str:
        """Convert to frontmatter string (simple key: value format)."""
        lines = [
            f"name: {self.name}",
            f"description: {self.description}",
            f"type: {self.type.value}",
            f"scope: {self.scope.value}",
            f"confidence: {self.confidence}",
            f"created_at: {self.created_at.isoformat()}",
            f"updated_at: {self.updated_at.isoformat()}",
        ]
        if self.source:
            lines.append(f"source: {self.source}")
        return "\n".join(lines)

    @classmethod
    def from_frontmatter(cls, text: str) -> "MemoryEntry":
        """Parse from frontmatter text."""
        # Split at first --- boundaries
        parts = text.split("---")
        if len(parts) < 3:
            # No frontmatter found, treat all as content
            return cls(
                name="",
                description="",
                type=MemoryType.USER,
                content=text.strip(),
            )

        # parts[0] is empty before first ---
        # parts[1] is frontmatter
        # parts[2+] is content
        frontmatter = parts[1].strip()
        content = "---".join(parts[2:]).strip()

        fm = {}
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                fm[key.strip()] = value.strip()

        return cls(
            name=fm.get("name", ""),
            description=fm.get("description", ""),
            type=MemoryType(fm.get("type", "user")),
            scope=MemoryScope(fm.get("scope", "private")),
            confidence=float(fm.get("confidence", 0.5)),
            created_at=date.fromisoformat(fm.get("created_at", date.today().isoformat())),
            updated_at=date.fromisoformat(fm.get("updated_at", date.today().isoformat())),
            source=fm.get("source"),
            content=content,
        )