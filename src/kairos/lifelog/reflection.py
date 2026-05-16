from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kairos.lifelog.journal import DailyJournalStore


@dataclass
class ReflectionFragment:
    """A fragment of reflection text from user input."""

    text: str
    source: str
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)


@dataclass
class DailyReflectionDraft:
    """A draft for daily reflection journal."""

    journal_date: date
    happened: list[str] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    energy: list[str] = field(default_factory=list)
    valuable_conversations: list[str] = field(default_factory=list)
    kairos_observations: list[str] = field(default_factory=list)
    tomorrow: list[str] = field(default_factory=list)

    def to_markdown_sections(self) -> dict[str, str]:
        """Convert draft to markdown sections."""
        return {
            "今天发生了什么": "\n".join(self.happened) if self.happened else "",
            "我在想什么": "\n".join(self.thoughts) if self.thoughts else "",
            "做了哪些事情": "\n".join(self.actions) if self.actions else "",
            "情绪与能量": "\n".join(self.energy) if self.energy else "",
            "有价值的对话": "\n".join(self.valuable_conversations) if self.valuable_conversations else "",
            "Kairos 的观察": "\n".join(self.kairos_observations) if self.kairos_observations else "",
            "明天可以推进的事": "\n".join(self.tomorrow) if self.tomorrow else "",
        }


class JournalDraftBuilder:
    """Builds daily reflection drafts from fragments using simple heuristics."""

    # Keywords for categorization
    ACTION_KEYWORDS = {"做了", "完成", "实现", "修复", "写", "创建", "提交", "修改", "添加", "删除", "完成", "开始"}
    THOUGHT_KEYWORDS = {"想", "觉得", "希望", "担心", "认为", "怀疑", "考虑", "思考"}
    ENERGY_KEYWORDS = {"有能量", "开心", "累", "消耗", "精力", "疲惫", "兴奋", "平静", "焦虑", "压力"}
    CONVERSATION_KEYWORDS = {"说", "讨论", "对话", "聊天", "问", "回答", "交流", "沟通"}

    @classmethod
    def from_fragments(
        cls, journal_date: date, fragments: list[ReflectionFragment]
    ) -> DailyReflectionDraft:
        """Build a draft from reflection fragments using simple heuristics."""
        draft = DailyReflectionDraft(journal_date=journal_date)

        for fragment in fragments:
            text = fragment.text
            lines = text.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                categorized = False

                # Check for action keywords
                if any(kw in line for kw in cls.ACTION_KEYWORDS):
                    draft.actions.append(line)
                    categorized = True
                # Check for thought keywords
                elif any(kw in line for kw in cls.THOUGHT_KEYWORDS):
                    draft.thoughts.append(line)
                    categorized = True
                # Check for energy keywords
                elif any(kw in line for kw in cls.ENERGY_KEYWORDS):
                    draft.energy.append(line)
                    categorized = True
                # Check for conversation keywords
                elif any(kw in line for kw in cls.CONVERSATION_KEYWORDS):
                    draft.valuable_conversations.append(line)
                    categorized = True
                # Default to happened
                else:
                    draft.happened.append(line)

        return draft


def write_reflection_draft(store: DailyJournalStore, draft: DailyReflectionDraft) -> Path:
    """Write a reflection draft to the journal store.

    Returns the journal path that received the draft.
    """
    path = store.create(draft.journal_date)
    sections = draft.to_markdown_sections()

    # Map our sections to journal sections
    section_map = {
        "今天发生了什么": "今天发生了什么",
        "我在想什么": "我在想什么",
        "做了哪些事情": "做了哪些事情",
        "情绪与能量": "情绪与能量",
        "有价值的对话": "有价值的对话",
        "Kairos 的观察": "Kairos 的观察",
        "明天可以推进的事": "明天可以推进的事",
    }

    for section_key, section_text in sections.items():
        if section_text:
            journal_section = section_map.get(section_key, section_key)
            path = store.append_fragment(draft.journal_date, journal_section, section_text)

    return path
