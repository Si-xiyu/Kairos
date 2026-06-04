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
    today = date(2026, 5, 15)
    fragments = [
        ReflectionFragment(text="今天完成了 Kairos 的 Memory System 设计", source="user"),
        ReflectionFragment(text="我觉得很有成就感，但又有点累", source="user"),
    ]

    draft = JournalDraftBuilder.from_fragments(today, fragments)

    assert draft.journal_date == today
    assert draft.actions
    assert draft.thoughts


def test_daily_reflection_draft_to_markdown_sections():
    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        happened=["一个平静的上午"],
        thoughts=["想要更多休息"],
        actions=["实现 Memory 模块"],
    )

    sections = draft.to_markdown_sections()

    assert "今天发生了什么" in sections
    assert "我在想什么" in sections
    assert "做了哪些事情" in sections
    assert "一个平静的上午" in sections["今天发生了什么"]


def test_write_reflection_draft_to_journal(tmp_path):
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
    assert "测试完成" in store.read(today)


def test_memory_candidate_extractor_from_draft():
    today = date(2026, 5, 15)
    draft = DailyReflectionDraft(
        journal_date=today,
        thoughts=["我喜欢先讨论架构再写代码"],
        energy=["下午有点累", "需要休息"],
    )

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)

    preference_candidates = [c for c in candidates if c.entry.type == MemoryType.USER]
    energy_candidates = [c for c in candidates if c.entry.type == MemoryType.ENERGY_PATTERN]
    assert preference_candidates
    assert energy_candidates
    assert preference_candidates[0].entry.source == "journal/2026-05-15"


def test_save_candidates_to_store(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)

    draft = DailyReflectionDraft(
        journal_date=date(2026, 5, 15),
        energy=["今天很有精力"],
    )

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)
    saved_paths = save_candidates(store, candidates)

    assert saved_paths
    for path in saved_paths:
        assert path.exists()
        assert "candidates" in str(path)
        assert store.load(path).candidate_reason


def test_candidates_not_in_default_list(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = MemoryStore(paths)

    draft = DailyReflectionDraft(
        journal_date=date(2026, 5, 15),
        energy=["反复消耗在切换上下文上"],
    )

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)
    assert candidates
    save_candidates(store, candidates)

    default_names = [entry.name for entry in store.list()]
    all_names = [entry.name for entry in store.list(include_candidates=True)]
    for candidate in candidates:
        assert candidate.entry.name not in default_names
        assert candidate.entry.name in all_names
