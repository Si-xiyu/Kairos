from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from kairos.memory.model import MemoryEntry, MemoryType
from kairos.memory.store import MemoryStore

if TYPE_CHECKING:
    from kairos.lifelog.reflection import DailyReflectionDraft


@dataclass
class MemoryCandidate:
    """A candidate memory entry extracted from reflection."""

    entry: MemoryEntry
    reason: str


class MemoryCandidateExtractor:
    """Extracts memory candidates from reflection drafts using simple heuristics."""

    # Keywords for candidate extraction
    USER_PREFERENCE_KEYWORDS = {"喜欢", "偏好", "希望", "想要", "倾向于", "更愿意", "以后"}
    FEEDBACK_KEYWORDS = {"不喜欢", "不要", "别", "避免", "不想", "厌恶"}
    ENERGY_POSITIVE_KEYWORDS = {"有能量", "有精力", "精力充沛", "开心", "兴奋", "满足", "成就"}
    ENERGY_NEGATIVE_KEYWORDS = {"消耗", "疲惫", "累", "无力", "疲倦", "困"}
    PATTERN_KEYWORDS = {"反复", "总是", "通常", "经常", "每次", "又"}

    @classmethod
    def extract_from_draft(cls, draft: DailyReflectionDraft) -> list[MemoryCandidate]:
        """Extract memory candidates from a reflection draft."""
        candidates: list[MemoryCandidate] = []
        lines = cls._draft_lines(draft)
        all_text = "\n".join(lines)

        # Check for user preferences
        positive_lines = [
            line
            for line in cls._matching_lines(lines, cls.USER_PREFERENCE_KEYWORDS)
            if not any(keyword in line for keyword in cls.FEEDBACK_KEYWORDS)
        ]
        if positive_lines:
            candidates.append(
                cls._create_preference_candidate(draft, positive_lines, is_positive=True)
            )

        # Check for negative feedback
        feedback_lines = cls._matching_lines(lines, cls.FEEDBACK_KEYWORDS)
        if feedback_lines:
            candidates.append(
                cls._create_preference_candidate(draft, feedback_lines, is_positive=False)
            )

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
    def _draft_lines(cls, draft: DailyReflectionDraft) -> list[str]:
        return [
            line.strip()
            for line in (
                draft.happened
                + draft.thoughts
                + draft.actions
                + draft.energy
                + draft.valuable_conversations
                + draft.kairos_observations
                + draft.tomorrow
            )
            if line.strip()
        ]

    @classmethod
    def _matching_lines(cls, lines: list[str], keywords: set[str]) -> list[str]:
        return [line for line in lines if any(keyword in line for keyword in keywords)]

    @classmethod
    def _create_preference_candidate(
        cls, draft: DailyReflectionDraft, lines: list[str], is_positive: bool
    ) -> MemoryCandidate:
        """Create a preference memory candidate."""
        content = "\n".join(lines[:3])
        mem_type = MemoryType.USER if is_positive else MemoryType.FEEDBACK
        journal_date = draft.journal_date.isoformat()
        kind = "prefer" if is_positive else "avoid"

        return MemoryCandidate(
            entry=MemoryEntry(
                name=f"{kind}_{journal_date}",
                description=f"User {'preference' if is_positive else 'feedback'} candidate from reflection draft.",
                type=mem_type,
                content=content,
                source=f"journal/{journal_date}",
            ),
            reason=f"{'Positive preference' if is_positive else 'Negative feedback'} keywords detected",
        )


def save_candidates(store: MemoryStore, candidates: list[MemoryCandidate]) -> list[Path]:
    """Save memory candidates to the store.

    Returns list of paths where candidates were saved.
    """
    paths: list[Path] = []
    for candidate in candidates:
        entry = replace(candidate.entry, candidate_reason=candidate.reason)
        path = store.save(entry, candidate=True)
        paths.append(path)
    return paths
