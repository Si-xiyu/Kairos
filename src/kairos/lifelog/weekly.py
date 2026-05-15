from __future__ import annotations

from datetime import date
from pathlib import Path

from kairos.config import KairosPaths

WEEKLY_SECTIONS = [
    "这一周你做了什么",
    "哪些事情给你能量",
    "哪些事情反复消耗你",
    "反复出现的主题",
    "Kairos 观察到的模式",
    "下周可以调整什么",
]


class WeeklyReviewStore:
    def __init__(self, paths: KairosPaths | None = None, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = paths.reviews / "weekly" if paths is not None else Path(".kairos/reviews/weekly")
        self.base_dir = Path(base_dir)

    def path_for(self, start_date: date, end_date: date) -> Path:
        return self.base_dir / f"{start_date.isoformat()}_to_{end_date.isoformat()}.md"

    def create(self, start_date: date, end_date: date, daily_notes: list[str] | None = None) -> Path:
        path = self.path_for(start_date, end_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = [f"# Weekly Review: {start_date.isoformat()} - {end_date.isoformat()}", ""]
        for section in WEEKLY_SECTIONS:
            content.extend([f"## {section}", ""])
        if daily_notes:
            content.extend(["## 每日记录", ""])
            content.extend(f"- {note}" for note in daily_notes)
            content.append("")
        path.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8")
        return path

    def read(self, start_date: date, end_date: date) -> str:
        path = self.path_for(start_date, end_date)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
