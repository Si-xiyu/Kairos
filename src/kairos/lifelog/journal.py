"""Daily journal storage."""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional


DEFAULT_TEMPLATE = """# {date}

## 今天发生了什么

## 我在想什么

## 做了哪些事情

## 情绪与能量

## 有价值的对话

## Kairos 的观察

## 明天可以轻轻推进的事
"""


class DailyJournalStore:
    """Store for daily markdown journals."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize with base directory for journal storage.

        If not provided, uses .kairos/journal in current directory.
        """
        if base_dir is None:
            base_dir = Path(".kairos/journal")
        self.base_dir = Path(base_dir)

    def _journal_dir(self, journal_date: date) -> Path:
        """Get directory for a journal date."""
        return self.base_dir / str(journal_date.year) / f"{journal_date.month:02d}"

    def path_for(self, journal_date: date | None = None) -> Path:
        """Get the path for a journal date.

        If date not provided, uses today.
        """
        if journal_date is None:
            journal_date = date.today()
        return self._journal_dir(journal_date) / f"{journal_date.isoformat()}.md"

    def exists(self, journal_date: date | None = None) -> bool:
        """Check if a journal exists for the given date."""
        return self.path_for(journal_date).exists()

    def create(
        self, journal_date: date | None = None, template: str | None = None
    ) -> Path:
        """Create a new daily journal.

        Returns the path where the journal was created.
        """
        if journal_date is None:
            journal_date = date.today()

        journal_path = self.path_for(journal_date)
        journal_path.parent.mkdir(parents=True, exist_ok=True)

        if template is None:
            template = DEFAULT_TEMPLATE

        content = template.format(date=journal_date.isoformat())
        journal_path.write_text(content, encoding="utf-8")

        return journal_path

    def append_fragment(
        self, journal_date: date | None, heading: str, text: str
    ) -> Path:
        """Append text under a heading in a journal.

        If the journal doesn't exist, it will be created.
        If the heading doesn't exist, it will be added.
        """
        if journal_date is None:
            journal_date = date.today()

        journal_path = self.path_for(journal_date)

        if not journal_path.exists():
            self.create(journal_date)

        # Read existing content
        content = journal_path.read_text(encoding="utf-8")

        # Check if heading exists
        heading_line = f"## {heading}"
        if heading_line in content:
            # Append to existing heading
            lines = content.split("\n")
            new_lines: list[str] = []
            in_target_heading = False

            for line in lines:
                if line.strip() == heading_line:
                    in_target_heading = True
                    new_lines.append(line)
                elif in_target_heading and line.startswith("## "):
                    in_target_heading = False
                    # Add text before new heading
                    new_lines.append("")
                    new_lines.append(text)
                    new_lines.append("")
                    new_lines.append(line)
                elif in_target_heading and line.strip():
                    # Continue in heading, append after existing text
                    new_lines.append(line)
                elif in_target_heading and not line.strip():
                    # Empty line in heading, add our text here
                    new_lines.append(text)
                    new_lines.append("")
                    in_target_heading = False
                else:
                    new_lines.append(line)

            content = "\n".join(new_lines)
        else:
            # Add new heading
            content = content.rstrip() + f"\n\n{heading_line}\n\n{text}\n"

        journal_path.write_text(content, encoding="utf-8")
        return journal_path

    def read(self, journal_date: date | None = None) -> str:
        """Read a journal by date.

        Returns empty string if not found.
        """
        journal_path = self.path_for(journal_date)
        if not journal_path.exists():
            return ""
        return journal_path.read_text(encoding="utf-8")