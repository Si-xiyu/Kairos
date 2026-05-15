from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kairos.memory.model import MemoryEntry, MemoryType
from kairos.memory.store import MemoryStore


@dataclass
class MemoryCandidate:
    """A candidate memory entry extracted from reflection."""

    entry: MemoryEntry
    reason: str


class MemoryCandidateExtractor:
    """Extracts memory candidates from reflection drafts using simple heuristics."""

    # Keywords for candidate extraction
    USER_PREFERENCE_KEYWORDS = {"喜欢", "偏好", "希望", "想要", "倾向于", "更愿意"}
    FEEDBACK_KEYWORDS = {"不喜欢", "不要", "别", "避免", "不想", "厌恶"}
    ENERGY_POSITIVE_KEYWORDS = {"有能量", "精力充沛", "开心", "兴奋", "满足", "成就"}
    ENERGY_NEGATIVE_KEYWORDS = {"消耗", "疲惫", "累", "无力", "疲倦", "困"}
    PATTERN_KEYWORDS = {"反复", "总是", "通常", "经常", "每次", "又"}

    @classmethod
    def extract_from_draft(cls, draft) -> list[MemoryCandidate]:
        """Extract memory candidates from a reflection draft."""
        candidates: list[MemoryCandidate] = []

        # Collect all text sections
        all_text = "\n".join(
            draft.happened
            + draft.thoughts
            + draft.actions
            + draft.energy
            + draft.valuable_conversations
            + draft.kairos_observations
            + draft.tomorrow
        )

        # Check for user preferences
        for keyword in cls.USER_PREFERENCE_KEYWORDS:
            if keyword in all_text:
                candidate = cls._create_preference_candidate(all_text, keyword, is_positive=True)
                if candidate:
                    candidates.append(candidate)
                break

        # Check for negative feedback
        for keyword in cls.FEEDBACK_KEYWORDS:
            if keyword in all_text:
                candidate = cls._create_preference_candidate(all_text, keyword, is_positive=False)
                if candidate:
                    candidates.append(candidate)
                break

        # Check for energy patterns
        if any(kw in all_text for kw in cls.ENERGY_POSITIVE_KEYWORDS):
            candidates.append(
                MemoryCandidate(
                    entry=MemoryEntry(
                        name=f"energy_positive_{draft.journal_date.isoformat()}",
                        description="Positive energy state recorded",
                        type=MemoryType.ENERGY_PATTERN,
                        content=all_text,
                        source=f"journal/{draft.journal_date.isoformat()}",
                    ),
                    reason="Positive energy keywords detected",
                )
            )
        elif any(kw in all_text for kw in cls.ENERGY_NEGATIVE_KEYWORDS):
            candidates.append(
                MemoryCandidate(
                    entry=MemoryEntry(
                        name=f"energy_negative_{draft.journal_date.isoformat()}",
                        description="Energy drain or fatigue recorded",
                        type=MemoryType.ENERGY_PATTERN,
                        content=all_text,
                        source=f"journal/{draft.journal_date.isoformat()}",
                    ),
                    reason="Energy drain keywords detected",
                )
            )

        # Check for recurring patterns
        if any(kw in all_text for kw in cls.PATTERN_KEYWORDS):
            candidates.append(
                MemoryCandidate(
                    entry=MemoryEntry(
                        name=f"pattern_observed_{draft.journal_date.isoformat()}",
                        description="Recurring pattern observed",
                        type=MemoryType.REFLECTION_THEME,
                        content=all_text,
                        source=f"journal/{draft.journal_date.isoformat()}",
                    ),
                    reason="Pattern keywords (反复/总是/经常) detected",
                )
            )

        return candidates

    @classmethod
    def _create_preference_candidate(
        cls, text: str, keyword: str, is_positive: bool
    ) -> MemoryCandidate | None:
        """Create a preference memory candidate."""
        lines = text.split("\n")
        relevant_lines = [
            line.strip() for line in lines if keyword in line
        ][:3]  # Limit to 3 relevant lines

        if not relevant_lines:
            return None

        content = "\n".join(relevant_lines)
        mem_type = MemoryType.USER if is_positive else MemoryType.FEEDBACK

        return MemoryCandidate(
            entry=MemoryEntry(
                name=f"{'prefer' if is_positive else 'avoid'}_{keyword}_{date.today().isoformat()}",
                description=f"User {'preference' if is_positive else 'preference'} detected: {keyword}",
                type=mem_type,
                content=content,
                source=f"journal/{date.today().isoformat()}",
            ),
            reason=f"{'Positive' if is_positive else 'Negative'} preference keyword: {keyword}",
        )


def save_candidates(store: MemoryStore, candidates: list[MemoryCandidate]) -> list[Path]:
    """Save memory candidates to the store.

    Returns list of paths where candidates were saved.
    """
    paths: list[Path] = []
    for candidate in candidates:
        path = store.save(candidate.entry, candidate=True)
        paths.append(path)
    return paths