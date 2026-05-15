"""Tests for memory and lifelog subsystems."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from kairos.memory.model import MemoryEntry, MemoryType, MemoryScope
from kairos.memory.store import MemoryStore
from kairos.lifelog.journal import DailyJournalStore
from kairos.lifelog.weekly import WeeklyReviewStore


class TestMemoryEntry:
    """Tests for MemoryEntry model."""

    def test_to_frontmatter(self):
        """Test frontmatter generation."""
        entry = MemoryEntry(
            name="test_memory",
            description="A test memory",
            type=MemoryType.USER,
            scope=MemoryScope.PRIVATE,
            confidence=0.8,
            content="Test content",
        )
        fm = entry.to_frontmatter()
        assert "name: test_memory" in fm
        assert "description: A test memory" in fm
        assert "type: user" in fm
        assert "confidence: 0.8" in fm

    def test_from_frontmatter(self):
        """Test frontmatter parsing."""
        text = """---
name: parsed_memory
description: Parsed from text
type: feedback
scope: private
confidence: 0.9
created_at: 2026-05-15
updated_at: 2026-05-15
---

Parsed content here.
"""
        entry = MemoryEntry.from_frontmatter(text)
        assert entry.name == "parsed_memory"
        assert entry.description == "Parsed from text"
        assert entry.type == MemoryType.FEEDBACK
        assert entry.confidence == 0.9
        assert entry.content == "Parsed content here."

    def test_roundtrip(self):
        """Test save and load produces equivalent entry."""
        entry = MemoryEntry(
            name="roundtrip_test",
            description="Testing roundtrip",
            type=MemoryType.PROJECT,
            content="Some content",
        )
        text = f"---\n{entry.to_frontmatter()}\n---\n\n{entry.content}"
        loaded = MemoryEntry.from_frontmatter(text)
        assert loaded.name == entry.name
        assert loaded.description == entry.description
        assert loaded.type == entry.type
        assert loaded.content == entry.content


class TestMemoryStore:
    """Tests for MemoryStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def store(self, temp_dir):
        """Create a MemoryStore with temp directory."""
        return MemoryStore(base_dir=temp_dir / "memory")

    def test_save_and_load(self, store, temp_dir):
        """Test saving and loading a memory entry."""
        entry = MemoryEntry(
            name="test_save",
            description="A saved memory",
            type=MemoryType.USER,
            content="Saved content",
        )
        path = store.save(entry)
        assert path.exists()

        loaded = store.load(path)
        assert loaded.name == entry.name
        assert loaded.description == entry.description
        assert loaded.type == entry.type

    def test_list(self, store):
        """Test listing memory entries."""
        # Save multiple entries
        entry1 = MemoryEntry(name="user1", description="User memory", type=MemoryType.USER)
        entry2 = MemoryEntry(name="user2", description="Another user", type=MemoryType.USER)
        entry3 = MemoryEntry(name="proj1", description="Project memory", type=MemoryType.PROJECT)

        store.save(entry1)
        store.save(entry2)
        store.save(entry3)

        all_entries = store.list()
        assert len(all_entries) == 3

        user_entries = store.list(MemoryType.USER)
        assert len(user_entries) == 2

    def test_delete(self, store):
        """Test deleting a memory entry."""
        entry = MemoryEntry(
            name="to_delete",
            description="Will be deleted",
            type=MemoryType.USER,
        )
        store.save(entry)
        assert store.delete("to_delete") is True
        assert store.delete("nonexistent") is False

    def test_rebuild_index(self, store):
        """Test rebuilding the memory index."""
        # Save some entries
        entry1 = MemoryEntry(name="index_test1", description="Test 1", type=MemoryType.USER)
        entry2 = MemoryEntry(name="index_test2", description="Test 2", type=MemoryType.PROJECT)
        store.save(entry1)
        store.save(entry2)

        index_path = store.rebuild_index()
        assert index_path.exists()

        content = index_path.read_text(encoding="utf-8")
        assert "Memory Index" in content
        assert "index_test1" in content
        assert "index_test2" in content

    def test_auto_types_go_to_candidates(self, store):
        """Test that auto-generated types go to candidates dir."""
        entry = MemoryEntry(
            name="life_pattern_1",
            description="A life pattern",
            type=MemoryType.LIFE_PATTERN,
        )
        path = store.save(entry)
        assert "candidates" in str(path)


class TestDailyJournalStore:
    """Tests for DailyJournalStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def journal_store(self, temp_dir):
        """Create a DailyJournalStore with temp directory."""
        return DailyJournalStore(base_dir=temp_dir / "journal")

    def test_path_for(self, journal_store):
        """Test getting path for a date."""
        test_date = date(2026, 5, 15)
        path = journal_store.path_for(test_date)
        # Check the date components are in the path
        assert "2026" in str(path)
        assert "05" in str(path)
        assert "2026-05-15.md" in str(path)

    def test_create(self, journal_store):
        """Test creating a journal."""
        test_date = date(2026, 5, 15)
        path = journal_store.create(test_date)

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "2026-05-15" in content
        assert "今天发生了什么" in content

    def test_exists(self, journal_store):
        """Test checking if journal exists."""
        test_date = date(2026, 5, 15)
        assert not journal_store.exists(test_date)

        journal_store.create(test_date)
        assert journal_store.exists(test_date)

    def test_append_fragment(self, journal_store):
        """Test appending a fragment to a journal."""
        test_date = date(2026, 5, 15)
        journal_store.create(test_date)

        journal_store.append_fragment(test_date, "今天发生了什么", "Something happened today.")

        content = journal_store.read(test_date)
        assert "Something happened today." in content

    def test_read_empty(self, journal_store):
        """Test reading a non-existent journal."""
        result = journal_store.read(date(2099, 1, 1))
        assert result == ""


class TestWeeklyReviewStore:
    """Tests for WeeklyReviewStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def weekly_store(self, temp_dir):
        """Create a WeeklyReviewStore with temp directory."""
        return WeeklyReviewStore(base_dir=temp_dir / "reviews/weekly")

    def test_path_for(self, weekly_store):
        """Test getting path for a weekly review."""
        start = date(2026, 5, 12)
        end = date(2026, 5, 18)
        path = weekly_store.path_for(start, end)

        assert "2026-05-12_to_2026-05-18.md" in str(path)

    def test_create(self, weekly_store):
        """Test creating a weekly review."""
        start = date(2026, 5, 12)
        end = date(2026, 5, 18)
        path = weekly_store.create(start, end)

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "2026-05-12" in content
        assert "2026-05-18" in content
        assert "这一周你做了什么" in content

    def test_create_with_daily_notes(self, weekly_store):
        """Test creating a weekly review with daily notes."""
        start = date(2026, 5, 12)
        end = date(2026, 5, 18)
        daily_notes = ["journal/2026/05/2026-05-12.md", "journal/2026/05/2026-05-13.md"]

        path = weekly_store.create(start, end, daily_notes=daily_notes)
        content = path.read_text(encoding="utf-8")

        assert "2026-05-12.md" in content
        assert "2026-05-13.md" in content

    def test_read_empty(self, weekly_store):
        """Test reading a non-existent review."""
        result = weekly_store.read(date(2099, 1, 1), date(2099, 1, 7))
        assert result == ""