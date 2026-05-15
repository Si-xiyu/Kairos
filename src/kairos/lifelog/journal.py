from __future__ import annotations

from datetime import date
from pathlib import Path

from kairos.config import KairosPaths

DEFAULT_SECTIONS = [
    "今天发生了什么",
    "我在想什么",
    "做了哪些事情",
    "情绪与能量",
    "有价值的对话",
    "Kairos 的观察",
    "明天可以轻轻推进的事",
]


class DailyJournalStore:
    def __init__(self, paths: KairosPaths | None = None, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = paths.journal if paths is not None else Path(".kairos/journal")
        self.base_dir = Path(base_dir)

    def path_for(self, journal_date: date) -> Path:
        return (
            self.base_dir
            / f"{journal_date.year:04d}"
            / f"{journal_date.month:02d}"
            / f"{journal_date.isoformat()}.md"
        )

    def exists(self, journal_date: date) -> bool:
        return self.path_for(journal_date).exists()

    def create(self, journal_date: date, sections: list[str] | None = None) -> Path:
        sections = sections or DEFAULT_SECTIONS
        path = self.path_for(journal_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        content = [f"# {journal_date.isoformat()}", ""]
        for section in sections:
            content.extend([f"## {section}", ""])
        path.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8")
        return path

    def append_fragment(self, journal_date: date, heading: str, text: str) -> Path:
        path = self.create(journal_date)
        content = path.read_text(encoding="utf-8")
        heading_line = f"## {heading}"
        if heading_line not in content:
            content = content.rstrip() + f"\n\n{heading_line}\n\n{text.strip()}\n"
            path.write_text(content, encoding="utf-8")
            return path

        lines = content.splitlines()
        insert_at = len(lines)
        for index, line in enumerate(lines):
            if line.strip() != heading_line:
                continue
            insert_at = len(lines)
            for next_index in range(index + 1, len(lines)):
                if lines[next_index].startswith("## "):
                    insert_at = next_index
                    break
            break
        lines[insert_at:insert_at] = ["", text.strip(), ""]
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def read(self, journal_date: date) -> str:
        path = self.path_for(journal_date)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
