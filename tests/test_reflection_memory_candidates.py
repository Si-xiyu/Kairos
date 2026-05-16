"""Tests for reflection and memory candidates."""

from datetime import date

from kairos.config import KairosPaths, ensure_workspace
from kairos.lifelog import (
    DailyJournalStore,
    DailyReflectionDraft,
    JournalDraftBuilder,
    ReflectionFragment,
    write_reflection_draft,
)
from kairos.memory import MemoryStore, MemoryType
from kairos.memory.candidates import MemoryCandidateExtractor, save_candidates


def test_journal_draft_builder_from_fragments(tmp_path):
    """Test building draft from fragments."""
    today = date(2026, 5, 15)
    fragments = [
        ReflectionFragment(
            text="今天完成了Kairos的Memory System设计",
            source="user",
        ),
        ReflectionFragment(
            text="我觉得很有成就感，但又有点累",
            source="user",
        ),
    ]

    draft = JournalDraftBuilder.from_fragments(today, fragments)

    assert draft.journal_date == today
    assert len(draft.actions) > 0
    assert len(draft.thoughts) > 0


def test_daily_reflection_draft_to_markdown_sections():
    """Test converting draft to markdown."""
    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        happened=["一个平静的上午"],
        thoughts=["想要更多休息"],
        actions=["实现Memory模块"],
    )

    sections = draft.to_markdown_sections()

    assert "今天发生了什么" in sections
    assert "我在想什么" in sections
    assert "做了哪些事情" in sections
    assert "一个平静的上午" in sections["今天发生了什么"]


def test_write_reflection_draft_to_journal(tmp_path):
    """Test writing draft to journal."""
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = DailyJournalStore(paths)

    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        happened=["测试完成"],
        thoughts=["一切正常"],
    )

    written_path = write_reflection_draft(store, draft)

    assert written_path.exists()

    content = store.read(today)
    assert "测试完成" in content


def test_memory_candidate_extractor_from_draft():
    """Test extracting candidates from draft."""
    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        thoughts=["我喜欢先讨论架构再写代码"],
        energy=["下午有点累", "需要休息"],
    )

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)

    preference_candidates = [c for c in candidates if c.entry.type == MemoryType.USER]
    # Should detect energy pattern
    energy_candidates = [c for c in candidates if c.entry.type == MemoryType.ENERGY_PATTERN]
    assert len(preference_candidates) > 0
    assert len(energy_candidates) > 0
    assert preference_candidates[0].entry.source == "journal/2026-05-15"


def test_save_candidates_to_store(tmp_path):
    """Test saving candidates to memory store."""
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)

    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        energy=["今天很有精力"],
    )

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)
    saved_paths = save_candidates(store, candidates)

    assert len(saved_paths) > 0
    for p in saved_paths:
        assert p.exists()
        assert "candidates" in str(p)
        assert store.load(p).candidate_reason


def test_candidates_not_in_default_list(tmp_path):
    """Test that candidates don't appear in default list."""
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)

    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(journal_date=today, energy=["反复消耗在切换上下文上"])

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)
    assert candidates
    save_candidates(store, candidates)

    # Default list should not include candidates
    default_entries = store.list()
    entry_names = [e.name for e in default_entries]

    for candidate in candidates:
        assert candidate.entry.name not in entry_names

    # With include_candidates=True, they should appear
    all_entries = store.list(include_candidates=True)
    all_names = [e.name for e in all_entries]

    for candidate in candidates:
        assert candidate.entry.name in all_names
