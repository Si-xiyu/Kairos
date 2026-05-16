from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from kairos.channels import ChannelManager, CLIChannel
from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext
from kairos.delivery import DeliveryQueue
from kairos.lifelog import DailyJournalStore, JournalDraftBuilder, ReflectionFragment, write_reflection_draft
from kairos.memory import MemoryStore
from kairos.memory.candidates import MemoryCandidateExtractor, save_candidates
from kairos.messages import InboundMessage, OutboundMessage
from kairos.permissions import AutonomyLevel
from kairos.presence import DaemonRuntime, PresenceEvent, ScheduleStore, ScheduledJob


class KairosBackend:
    def __init__(self, root: Path) -> None:
        self.paths = KairosPaths.from_root(root)

    def bootstrap(self, force: bool = False) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = ScheduleStore(self.paths)
        jobs = store.load()
        default_job = ScheduledJob(
            id="nightly-journal",
            name="Nightly Journal Check",
            schedule={"kind": "daily", "hour": 23, "minute": 0},
            payload={
                "kind": "presence_event",
                "event": "daily_journal_check",
                "payload": {
                    "message": "今天还没有留下记录。要不要随便丢几个碎片给我，我帮你整理成日记？",
                    "channel": "cli",
                    "to": "local-user",
                },
            },
        )
        if force or not any(job.id == default_job.id for job in jobs):
            store.add(default_job)
            action = "installed"
        else:
            action = "kept"
        return {"workspace": str(self.paths.home), "default_nightly_journal": action}

    def doctor(self) -> dict[str, Any]:
        memory_store = MemoryStore(self.paths)
        confirmed_memories = memory_store.list() if self.paths.memory.exists() else []
        all_memories = memory_store.list(include_candidates=True) if self.paths.memory.exists() else []
        return {
            "root": str(self.paths.root),
            "kairos_home": str(self.paths.home),
            "initialized": self.paths.home.exists(),
            "conversations": _count_files(self.paths.conversations, "*.jsonl"),
            "journals": _count_files(self.paths.journal, "*.md"),
            "memories": len(confirmed_memories),
            "memory_candidates": len(all_memories) - len(confirmed_memories),
            "schedules": len(ScheduleStore(self.paths).load()) if self.paths.schedules.exists() else 0,
            "delivery_pending": _count_files(self.paths.delivery_pending, "*.json"),
            "delivery_failed": _count_files(self.paths.delivery_failed, "*.json"),
            "audit_events": _count_lines(self.paths.audit / "tool-calls.jsonl"),
        }

    def reflect(
        self,
        text: str,
        journal_date: date | None = None,
        source: str = "api",
        save_memory_candidates: bool = True,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        draft = JournalDraftBuilder.from_fragments(
            journal_date,
            [ReflectionFragment(text=text, source=source)],
        )
        journal_path = write_reflection_draft(DailyJournalStore(self.paths), draft)
        candidates = MemoryCandidateExtractor.extract_from_draft(draft)
        saved = save_candidates(MemoryStore(self.paths), candidates) if save_memory_candidates else []
        return {
            "journal_path": str(journal_path),
            "candidate_count": len(candidates),
            "candidate_paths": [str(path) for path in saved],
            "sections": draft.to_markdown_sections(),
        }

    def list_memories(self, include_candidates: bool = False) -> dict[str, Any]:
        ensure_workspace(self.paths)
        entries = MemoryStore(self.paths).list(include_candidates=include_candidates)
        return {
            "memories": [
                {
                    "name": entry.name,
                    "description": entry.description,
                    "type": entry.type.value,
                    "scope": entry.scope.value,
                    "confidence": entry.confidence,
                    "source": entry.source,
                    "content": entry.content,
                }
                for entry in entries
            ]
        }

    def read_journal(self, journal_date: date | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        store = DailyJournalStore(self.paths)
        path = store.path_for(journal_date)
        return {
            "date": journal_date.isoformat(),
            "path": str(path),
            "exists": path.exists(),
            "content": store.read(journal_date),
        }

    def add_schedule(
        self,
        job_id: str,
        name: str,
        kind: str = "every",
        at: datetime | None = None,
        seconds: int = 3600,
        event: str = "daily_journal_check",
        message: str | None = None,
        due_now: bool = False,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        now = datetime.now(timezone.utc)
        if kind == "at":
            if at is None and not due_now:
                raise ValueError("at is required for kind=at unless due_now is true")
            schedule = {"kind": "at", "at": (now if due_now else _coerce_datetime(at)).isoformat()}
        elif kind == "every":
            schedule = {"kind": "every", "seconds": seconds}
        else:
            raise ValueError(f"unsupported schedule kind: {kind}")
        job = ScheduledJob(
            id=job_id,
            name=name,
            schedule=schedule,
            payload={
                "kind": "presence_event",
                "event": event,
                "payload": {"message": message, "channel": "cli", "to": "local-user"},
            },
            next_run_at=now if due_now else None,
        )
        ScheduleStore(self.paths).add(job)
        return {"id": job.id, "name": job.name, "schedule": job.schedule, "payload": job.payload}

    def daemon_tick(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        delivered: list[dict[str, str]] = []

        class CaptureCLIChannel(CLIChannel):
            def send(self, to: str, text: str, **kwargs: object) -> bool:
                delivered.append({"channel": self.name, "to": to, "text": text})
                return super().send(to=to, text=text, **kwargs)

        runtime = DaemonRuntime(
            schedule_store=ScheduleStore(self.paths),
            delivery_queue=DeliveryQueue(self.paths),
            channel_manager=ChannelManager([CaptureCLIChannel()]),
            presence_handler=_presence_handler,
        )
        result = runtime.tick()
        return {
            "due_jobs": result.due_jobs,
            "enqueued": result.enqueued,
            "failed_jobs": result.failed_jobs,
            "delivery": result.delivery,
            "delivered": delivered,
        }

    def chat_once(self, text: str, session: str = "default", autonomy: int = 3) -> dict[str, Any]:
        ensure_workspace(self.paths)
        context = RuntimeContext.local(
            self.paths,
            session_id=session,
            autonomy_level=AutonomyLevel(autonomy),
        )
        result = AgentLoop(context).run_turn(
            InboundMessage(text=text, sender_id="api-user", channel="api", peer_id="api-user")
        )
        return {
            "outbound": [
                {"channel": message.channel, "to": message.to, "text": message.text}
                for message in result.outbound
            ],
            "observations": result.observations,
        }


def _presence_handler(event: PresenceEvent, now: datetime):
    message = event.payload.get("message") or _default_presence_message(event)
    if not message:
        return []
    return [
        OutboundMessage(
            channel=str(event.payload.get("channel", "cli")),
            to=str(event.payload.get("to", "local-user")),
            text=str(message),
        )
    ]


def _default_presence_message(event: PresenceEvent) -> str:
    if event.event == "daily_journal_check":
        return "今天还没有留下记录。要不要随便丢几个碎片给我，我帮你整理成日记？"
    if event.event == "heartbeat":
        return "Kairos heartbeat check."
    return f"Kairos presence event: {event.event}"


def _count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob(pattern))


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
