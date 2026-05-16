from __future__ import annotations

from datetime import date

from kairos.config import KairosPaths, ensure_workspace
from kairos.lifelog import DailyJournalStore, WeeklyReviewStore
from kairos.memory import MemoryEntry, MemoryStore, MemoryType


def test_memory_save_load_and_index(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)
    entry = MemoryEntry(
        name="prefer_design_first",
        description="User prefers design discussion before code.",
        type=MemoryType.USER,
        confidence=0.9,
        content="The user likes discussing architecture before implementation.",
    )

    saved = store.save(entry)
    loaded = store.load("prefer_design_first")
    index = store.rebuild_index()

    assert saved.exists()
    assert loaded.name == entry.name
    assert loaded.content == entry.content
    assert "prefer_design_first" in index.read_text(encoding="utf-8")


def test_candidate_memory_is_not_listed_by_default(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)
    candidate = MemoryEntry(
        name="energy_morning",
        description="Possible morning energy pattern.",
        type=MemoryType.ENERGY_PATTERN,
        content="The user may have more energy in the morning.",
    )

    path = store.save(candidate)

    assert "candidates" in str(path)
    assert store.list() == []
    assert store.list(include_candidates=True)[0].name == "energy_morning"


def test_daily_journal_create_append_read(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = DailyJournalStore(paths)
    today = date(2026, 5, 15)

    path = store.create(today)
    store.append_fragment(today, "今天发生了什么", "讨论了 Kairos 的长期记忆设计。")

    content = store.read(today)
    assert path.exists()
    assert "2026-05-15" in content
    assert "今天发生了什么" in content
    assert "长期记忆设计" in content


def test_weekly_review_create_read(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = WeeklyReviewStore(paths)
    start = date(2026, 5, 11)
    end = date(2026, 5, 17)

    path = store.create(start, end, ["journal/2026/05/2026-05-15.md"])
    content = store.read(start, end)

    assert path.exists()
    assert "Weekly Review: 2026-05-11 - 2026-05-17" in content
    assert "哪些事情给你能量" in content
    assert "2026-05-15.md" in content


def test_weekly_review_create_with_section_content(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = WeeklyReviewStore(paths)
    start = date(2026, 5, 11)
    end = date(2026, 5, 17)

    path = store.create(
        start,
        end,
        section_content={
            "这一周你做了什么": ["实现 FastAPI 后端"],
            "下周可以调整什么": ["减少反复消耗"],
        },
    )
    content = path.read_text(encoding="utf-8")

    assert "- 实现 FastAPI 后端" in content
    assert "- 减少反复消耗" in content
