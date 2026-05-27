from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KairosPaths:
    root: Path
    home: Path
    conversations: Path
    journal: Path
    memory: Path
    reviews: Path
    tasks: Path
    delivery_pending: Path
    delivery_failed: Path
    schedules: Path
    audit: Path

    @classmethod
    def from_root(cls, root: Path) -> "KairosPaths":
        resolved = root.resolve()
        home = resolved / ".kairos"
        return cls(
            root=resolved,
            home=home,
            conversations=home / "conversations",
            journal=home / "journal",
            memory=home / "memory",
            reviews=home / "reviews",
            tasks=home / "tasks",
            delivery_pending=home / "delivery" / "pending",
            delivery_failed=home / "delivery" / "failed",
            schedules=home / "schedules",
            audit=home / "audit",
        )


def ensure_workspace(paths: KairosPaths) -> None:
    for path in (
        paths.conversations,
        paths.journal,
        paths.memory / "user",
        paths.memory / "feedback",
        paths.memory / "project",
        paths.memory / "reference",
        paths.memory / "candidates",
        paths.reviews / "weekly",
        paths.reviews / "monthly",
        paths.tasks,
        paths.delivery_pending,
        paths.delivery_failed,
        paths.schedules,
        paths.audit,
    ):
        path.mkdir(parents=True, exist_ok=True)

    config = paths.home / "config.toml"
    if not config.exists():
        config.write_text(
            "\n".join(
                [
                    "# Kairos local configuration",
                    "autonomy_level = 1",
                    "active_hours = [9, 23]",
                    "daily_notification_budget = 3",
                    "",
                ]
            ),
            encoding="utf-8",
        )
