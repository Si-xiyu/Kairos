from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import json
from pathlib import Path
from uuid import uuid4

from kairos.config import KairosPaths


GUIDED_QUESTIONS = [
    {
        "id": "happened",
        "heading": "今天发生了什么",
        "text": "今天发生了哪几件值得留下的事？不用完整，几个碎片就行。",
    },
    {
        "id": "energy",
        "heading": "情绪与能量",
        "text": "今天什么让你有能量？什么又在消耗你？",
    },
    {
        "id": "thinking",
        "heading": "我在想什么",
        "text": "今天脑子里反复出现的想法是什么？",
    },
    {
        "id": "tomorrow",
        "heading": "明天可以推进的事",
        "text": "明天只轻轻推进一件事的话，你希望是什么？",
    },
]


@dataclass(frozen=True)
class GuidedAnswer:
    question_id: str
    question: str
    heading: str
    answer: str
    answered_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class GuidedJournalSession:
    id: str
    journal_date: date
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"
    answers: list[GuidedAnswer] = field(default_factory=list)

    def to_json(self) -> dict:
        data = asdict(self)
        data["journal_date"] = self.journal_date.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict) -> "GuidedJournalSession":
        return cls(
            id=str(data["id"]),
            journal_date=date.fromisoformat(str(data["journal_date"])),
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            status=str(data.get("status", "active")),
            answers=[GuidedAnswer(**answer) for answer in data.get("answers", [])],
        )

    def next_question(self) -> dict | None:
        answered = {answer.question_id for answer in self.answers}
        for question in GUIDED_QUESTIONS:
            if question["id"] not in answered:
                return question
        return None

    def with_answer(self, question_id: str, answer: str) -> "GuidedJournalSession":
        question = _question_by_id(question_id)
        answers = [existing for existing in self.answers if existing.question_id != question_id]
        answers.append(
            GuidedAnswer(
                question_id=question["id"],
                question=question["text"],
                heading=question["heading"],
                answer=answer,
            )
        )
        return GuidedJournalSession(
            id=self.id,
            journal_date=self.journal_date,
            created_at=self.created_at,
            status=self.status,
            answers=answers,
        )

    def finished(self) -> "GuidedJournalSession":
        return GuidedJournalSession(
            id=self.id,
            journal_date=self.journal_date,
            created_at=self.created_at,
            status="finished",
            answers=self.answers,
        )


class GuidedJournalStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.base_dir = paths.tasks / "guided-journals"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, journal_date: date, session_id: str | None = None) -> GuidedJournalSession:
        session = GuidedJournalSession(id=session_id or uuid4().hex[:12], journal_date=journal_date)
        self.save(session)
        return session

    def load(self, session_id: str) -> GuidedJournalSession:
        path = self.path_for(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Guided journal session not found: {session_id}")
        return GuidedJournalSession.from_json(json.loads(path.read_text(encoding="utf-8")))

    def save(self, session: GuidedJournalSession) -> Path:
        path = self.path_for(session.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def path_for(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"


def guided_session_to_api(session: GuidedJournalSession) -> dict:
    next_question = session.next_question()
    return {
        "id": session.id,
        "date": session.journal_date.isoformat(),
        "status": session.status,
        "questions": GUIDED_QUESTIONS,
        "next_question": next_question,
        "answers": [asdict(answer) for answer in session.answers],
        "complete": next_question is None,
    }


def grouped_answers(session: GuidedJournalSession) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for answer in session.answers:
        if not answer.answer.strip():
            continue
        grouped.setdefault(answer.heading, []).append(answer.answer.strip())
    return grouped


def _question_by_id(question_id: str) -> dict:
    for question in GUIDED_QUESTIONS:
        if question["id"] == question_id:
            return question
    raise ValueError(f"Unknown guided journal question: {question_id}")
