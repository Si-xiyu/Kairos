"""Weekly review storage."""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

DEFAULT_WEEKLY_TEMPLATE = """# Weekly Review: {start_date} - {end_date}

## 这一周你做了什么

## 哪些事情给你能量

## 哪些事情反复消耗你

## 反复出现的主题

## Kairos 观察到的模式

## 下周可以调整什么
"""


class WeeklyReviewStore:
    """Store for weekly markdown reviews."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize with base directory for review storage.

        If not provided, uses .kairos/reviews/weekly in current directory.
        """
        if base_dir is None:
            base_dir = Path(".kairos/reviews/weekly")
        self.base_dir = Path(base_dir)

    def path_for(self, start_date: date, end_date: date) -> Path:
        """Get the path for a weekly review."""
        filename = f"{start_date.isoformat()}_to_{end_date.isoformat()}.md"
        return self.base_dir / filename

    def exists(self, start_date: date, end_date: date) -> bool:
        """Check if a weekly review exists."""
        return self.path_for(start_date, end_date).exists()

    def create(
        self,
        start_date: date,
        end_date: date,
        daily_notes: Optional[list[str]] = None,
        template: Optional[str] = None,
    ) -> Path:
        """Create a new weekly review.

        If template not provided, uses default template.
        daily_notes is optional list of daily journal paths or content to include.
        """
        review_path = self.path_for(start_date, end_date)
        review_path.parent.mkdir(parents=True, exist_ok=True)

        if template is None:
            template = DEFAULT_WEEKLY_TEMPLATE

        content = template.format(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # Optionally add references to daily notes
        if daily_notes:
            content = content.rstrip() + "\n\n## 每日记录\n"
            for note in daily_notes:
                content += f"- {note}\n"

        review_path.write_text(content, encoding="utf-8")
        return review_path

    def read(self, start_date: date, end_date: date) -> str:
        """Read a weekly review.

        Returns empty string if not found.
        """
        review_path = self.path_for(start_date, end_date)
        if not review_path.exists():
            return ""
        return review_path.read_text(encoding="utf-8")