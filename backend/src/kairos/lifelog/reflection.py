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
    """A draft for a daily reflection journal."""

    journal_date: date
    happened: list[str] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    energy: list[str] = field(default_factory=list)
    valuable_conversations: list[str] = field(default_factory=list)
    kairos_observations: list[str] = field(default_factory=list)
    tomorrow: list[str] = field(default_factory=list)

    def to_markdown_sections(self) -> dict[str, str]:
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
    """Build daily reflection drafts from fragments using simple heuristics."""

    ACTION_KEYWORDS = {"做了", "完成", "实现", "修复", "写", "创建", "提交", "修改", "添加", "删除", "开始"}
    THOUGHT_KEYWORDS = {"想", "觉得", "希望", "担心", "认为", "怀疑", "考虑", "思考"}
    ENERGY_KEYWORDS = {"有能量", "有精力", "开心", "累", "消耗", "精力", "疲惫", "兴奋", "平静", "焦虑", "压力"}
    CONVERSATION_KEYWORDS = {"说", "讨论", "对话", "聊天", "问", "回答", "交流", "沟通"}

    @classmethod
    def from_fragments(
        cls, journal_date: date, fragments: list[ReflectionFragment]
    ) -> DailyReflectionDraft:
        draft = DailyReflectionDraft(journal_date=journal_date)
        for fragment in fragments:
            for raw_line in fragment.text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if any(keyword in line for keyword in cls.ACTION_KEYWORDS):
                    draft.actions.append(line)
                elif any(keyword in line for keyword in cls.THOUGHT_KEYWORDS):
                    draft.thoughts.append(line)
                elif any(keyword in line for keyword in cls.ENERGY_KEYWORDS):
                    draft.energy.append(line)
                elif any(keyword in line for keyword in cls.CONVERSATION_KEYWORDS):
                    draft.valuable_conversations.append(line)
                else:
                    draft.happened.append(line)
        return draft


def write_reflection_draft(store: DailyJournalStore, draft: DailyReflectionDraft) -> Path:
    path = store.create(draft.journal_date)
    for section_key, section_text in draft.to_markdown_sections().items():
        if section_text:
            path = store.append_fragment(draft.journal_date, section_key, section_text)
    return path
