from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib

from kairos.config import KairosPaths
from kairos.core.session import SessionEvent
from kairos.memory import MemoryEntry, MemoryStore, MemoryType


@dataclass(frozen=True)
class CapturedMemory:
    name: str
    reason: str


VALUE_KEYWORDS = {
    "remember",
    "i prefer",
    "i like",
    "i dislike",
    "my preference",
    "以后",
    "记住",
    "请记住",
    "我喜欢",
    "我不喜欢",
    "偏好",
    "习惯",
}


def capture_memory_candidates(
    paths: KairosPaths,
    session_id: str,
    events: list[SessionEvent],
    summary: str | None = None,
) -> list[CapturedMemory]:
    captures: list[CapturedMemory] = []
    store = MemoryStore(paths)
    for event in events[-8:]:
        if event.role != "user":
            continue
        content = event.content.strip()
        if not _looks_valuable(content):
            continue
        entry = _entry_from_text(session_id, content, reason="User stated a preference or durable fact")
        store.save(entry, candidate=True)
        captures.append(CapturedMemory(name=entry.name, reason=entry.candidate_reason or "candidate"))

    if summary and len(summary.strip()) > 80:
        entry = MemoryEntry(
            name=f"context_summary_{_digest(session_id + summary)}",
            description="Conversation summary candidate from context compression.",
            type=MemoryType.REFLECTION_THEME,
            content=summary.strip(),
            source=f"session/{session_id}",
            candidate_reason="Context compression produced a durable summary",
            confidence=0.55,
        )
        store.save(entry, candidate=True)
        captures.append(CapturedMemory(name=entry.name, reason=entry.candidate_reason or "summary"))
    return captures


def _entry_from_text(session_id: str, content: str, reason: str) -> MemoryEntry:
    mem_type = MemoryType.FEEDBACK if _negative(content) else MemoryType.USER
    return MemoryEntry(
        name=f"conversation_{_digest(session_id + content)}",
        description=_description(content),
        type=mem_type,
        content=content,
        source=f"session/{session_id}",
        candidate_reason=reason,
        confidence=0.65,
        created_at=date.today(),
        updated_at=date.today(),
    )


def _looks_valuable(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower or keyword in text for keyword in VALUE_KEYWORDS)


def _negative(text: str) -> bool:
    lower = text.lower()
    return any(item in lower or item in text for item in {"dislike", "avoid", "我不喜欢", "不要", "避免"})


def _description(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) > 72:
        compact = compact[:69].rstrip() + "..."
    return f"Conversation-derived memory candidate: {compact}"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
