from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kairos.channels import ChannelManager, CLIChannel
from kairos.capabilities import SkillRegistry, list_capabilities
from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext
from kairos.core.session import SessionEvent, SessionStore
from kairos.delivery import DeliveryQueue
from kairos.lifelog import (
    DailyJournalStore,
    JournalDraftBuilder,
    ReflectionFragment,
    WeeklyReviewStore,
    write_reflection_draft,
)
from kairos.memory import MemoryEntry, MemoryScope, MemoryStore, MemoryType
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

    def state(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        doctor = self.doctor()
        today = date.today()
        journal_store = DailyJournalStore(self.paths)
        schedules = self.list_schedules()["schedules"]
        capabilities = self.capabilities()
        return {
            "app": {"name": "Kairos", "mode": "local-first-backend"},
            "doctor": doctor,
            "today": {
                "date": today.isoformat(),
                "journal_exists": journal_store.exists(today),
                "journal_path": str(journal_store.path_for(today)),
            },
            "recent_journals": self.list_journals(limit=7)["journals"],
            "memories": self.list_memories(include_candidates=True)["summary"],
            "schedules": {
                "total": len(schedules),
                "enabled": sum(1 for job in schedules if job["enabled"]),
                "due": len(ScheduleStore(self.paths).due()),
                "items": schedules[:5],
            },
            "delivery": {
                "pending": _count_files(self.paths.delivery_pending, "*.json"),
                "failed": _count_files(self.paths.delivery_failed, "*.json"),
            },
            "capabilities": {
                "tools": len(capabilities["tools"]),
                "skills": len(capabilities["skills"]),
                "mcp_plugins": len(capabilities["mcp_plugins"]),
            },
            "sessions": self.list_sessions(limit=5)["sessions"],
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
        entries = MemoryStore(self.paths).list_with_paths(include_candidates=include_candidates)
        confirmed = [item for item in entries if not item[2]]
        candidates = [item for item in entries if item[2]]
        return {
            "summary": {
                "confirmed": len(confirmed),
                "candidates": len(candidates),
                "total": len(entries),
            },
            "memories": [
                _memory_to_api(entry, path, candidate)
                for entry, path, candidate in entries
            ]
        }

    def save_memory(
        self,
        name: str,
        description: str,
        content: str,
        memory_type: str = "user",
        scope: str = "private",
        confidence: float = 0.7,
        source: str | None = "api",
        candidate: bool = False,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        entry = MemoryEntry(
            name=name,
            description=description,
            type=MemoryType(memory_type),
            scope=MemoryScope(scope),
            confidence=confidence,
            source=source,
            content=content,
        )
        path = MemoryStore(self.paths).save(entry, candidate=candidate)
        return {"memory": _memory_to_api(entry, path, candidate)}

    def confirm_memory(self, name: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = MemoryStore(self.paths)
        path = store.confirm_candidate(name)
        entry = store.load(path, include_candidates=False)
        return {"memory": _memory_to_api(entry, path, False)}

    def update_memory(
        self,
        name: str,
        description: str | None = None,
        content: str | None = None,
        confidence: float | None = None,
        candidate: bool | None = None,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = MemoryStore(self.paths)
        entry, old_path, old_candidate = _find_memory(store, name)
        target_candidate = old_candidate if candidate is None else candidate
        updated = replace(
            entry,
            description=description if description is not None else entry.description,
            content=content if content is not None else entry.content,
            confidence=confidence if confidence is not None else entry.confidence,
            updated_at=date.today(),
        )
        path = store.save(updated, candidate=target_candidate)
        if old_path.exists() and old_path != path:
            old_path.unlink()
        if not target_candidate:
            store.rebuild_index()
        return {"memory": _memory_to_api(updated, path, target_candidate)}

    def delete_memory(self, name: str, candidate: bool | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = MemoryStore(self.paths)
        if candidate is True:
            deleted = store.delete_candidate(name)
        else:
            deleted = store.delete(name, include_candidates=candidate is not False)
        return {"deleted": deleted}

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

    def list_journals(self, limit: int = 30) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journals: list[dict[str, Any]] = []
        for path in sorted(self.paths.journal.rglob("*.md"), reverse=True):
            journal_date = _date_from_journal_path(path)
            content = path.read_text(encoding="utf-8")
            journals.append(
                {
                    "date": journal_date.isoformat() if journal_date else path.stem,
                    "path": str(path),
                    "title": content.splitlines()[0] if content.splitlines() else path.stem,
                    "preview": _preview_markdown(content),
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                }
            )
            if len(journals) >= limit:
                break
        return {"journals": journals}

    def save_journal(self, content: str, journal_date: date | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        store = DailyJournalStore(self.paths)
        path = store.path_for(journal_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return self.read_journal(journal_date)

    def append_journal(
        self,
        text: str,
        journal_date: date | None = None,
        heading: str = "有价值的对话",
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        DailyJournalStore(self.paths).append_fragment(journal_date, heading, text)
        return self.read_journal(journal_date)

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

    def list_schedules(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"schedules": [_job_to_api(job) for job in ScheduleStore(self.paths).load()]}

    def delete_schedule(self, job_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"deleted": ScheduleStore(self.paths).delete(job_id)}

    def set_schedule_enabled(self, job_id: str, enabled: bool) -> dict[str, Any]:
        ensure_workspace(self.paths)
        updated = ScheduleStore(self.paths).set_enabled(job_id, enabled)
        return {"updated": updated}

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

    def create_session(
        self,
        session_id: str,
        title: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = SessionStore(self.paths)
        if title or summary:
            store.append(
                session_id,
                SessionEvent(
                    role="system",
                    content=summary or title or "Session created.",
                    metadata={"title": title or session_id},
                ),
            )
        else:
            store.path_for(session_id).touch()
        return {"session": self._session_to_api(session_id, store.read(session_id))}

    def list_sessions(self, limit: int = 50) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = SessionStore(self.paths)
        sessions: list[dict[str, Any]] = []
        for path in sorted(self.paths.conversations.glob("*.jsonl"), key=_mtime, reverse=True):
            session_id = path.stem
            sessions.append(self._session_to_api(session_id, store.read(session_id)))
            if len(sessions) >= limit:
                break
        return {"sessions": sessions}

    def list_session_messages(self, session_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        events = SessionStore(self.paths).read(session_id)
        return {
            "session_id": session_id,
            "messages": [_session_event_to_message(session_id, index, event) for index, event in enumerate(events)],
        }

    def list_session_events(self, session_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        events = SessionStore(self.paths).read(session_id)
        agent_events = [
            _session_event_to_agent_event(session_id, index, event)
            for index, event in enumerate(events)
            if event.role in {"tool", "system"} or event.metadata
        ]
        return {"session_id": session_id, "events": agent_events}

    def capabilities(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return list_capabilities(self.paths)

    def list_skills(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"skills": [skill.manifest() for skill in SkillRegistry(self.paths).list()]}

    def read_skill(self, name: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        skill = SkillRegistry(self.paths).load(name)
        return {**skill.manifest(), "body": skill.body}

    def weekly_review(self, start_date: date | None = None, end_date: date | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        end_date = end_date or date.today()
        start_date = start_date or (end_date - timedelta(days=6))
        store = DailyJournalStore(self.paths)
        notes: list[str] = []
        cursor = start_date
        while cursor <= end_date:
            content = store.read(cursor)
            if content.strip():
                notes.append(f"{cursor.isoformat()}: {_preview_markdown(content, limit=160)}")
            cursor += timedelta(days=1)
        review_store = WeeklyReviewStore(self.paths)
        path = review_store.create(start_date, end_date, daily_notes=notes)
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "path": str(path),
            "content": review_store.read(start_date, end_date),
        }

    def _session_to_api(self, session_id: str, events: list[SessionEvent]) -> dict[str, Any]:
        last = events[-1] if events else None
        user_events = [event for event in events if event.role == "user"]
        title = _session_title(session_id, events)
        summary = user_events[-1].content if user_events else (last.content if last else "No messages yet.")
        return {
            "id": session_id,
            "title": title,
            "summary": _single_line(summary, limit=96),
            "updatedAt": _relative_or_iso(last.created_at if last else None),
            "unreadCount": 0,
            "status": "active" if session_id == "default" else "idle",
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


def _job_to_api(job: ScheduledJob) -> dict[str, Any]:
    data = job.to_json()
    computed_next = job.next_due_after(datetime.now(timezone.utc)) if job.enabled else None
    data["next_run_at"] = data.get("next_run_at") or (
        computed_next.isoformat() if computed_next is not None else None
    )
    return data


def _memory_to_api(entry: MemoryEntry, path: Path, candidate: bool) -> dict[str, Any]:
    return {
        "name": entry.name,
        "description": entry.description,
        "type": entry.type.value,
        "scope": entry.scope.value,
        "confidence": entry.confidence,
        "source": entry.source,
        "content": entry.content,
        "candidate": candidate,
        "path": str(path),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def _session_event_to_message(session_id: str, index: int, event: SessionEvent) -> dict[str, Any]:
    role = event.role if event.role in {"user", "assistant", "system"} else "system"
    return {
        "id": f"{session_id}-{index}",
        "sessionId": session_id,
        "role": role,
        "author": _author_for_role(event.role),
        "createdAt": event.created_at,
        "status": "complete",
        "blocks": [{"kind": _block_kind(event.content), "content": event.content}],
    }


def _session_event_to_agent_event(session_id: str, index: int, event: SessionEvent) -> dict[str, Any]:
    if event.role == "tool":
        kind = "tool_result"
        title = str(event.metadata.get("tool", "Tool result"))
        status = "ok" if event.metadata.get("status") == "ok" else "warning"
    elif event.role == "system":
        kind = "runtime"
        title = str(event.metadata.get("title", "Runtime event"))
        status = "ok"
    else:
        kind = "runtime"
        title = "Message metadata"
        status = "ok"
    return {
        "id": f"{session_id}-event-{index}",
        "sessionId": session_id,
        "kind": kind,
        "title": title,
        "timestamp": event.created_at,
        "status": status,
        "summary": _single_line(event.content, limit=120),
        "details": _metadata_details(event),
    }


def _session_title(session_id: str, events: list[SessionEvent]) -> str:
    for event in events:
        title = event.metadata.get("title")
        if title:
            return str(title)
    for event in events:
        if event.role == "user" and event.content.strip():
            return _single_line(event.content, limit=36)
    return session_id.replace("_", " ").replace("-", " ").title() or "Session"


def _author_for_role(role: str) -> str:
    if role == "user":
        return "You"
    if role == "assistant":
        return "Kairos"
    if role == "tool":
        return "Tool"
    return "System"


def _block_kind(content: str) -> str:
    stripped = content.lstrip()
    if stripped.startswith("#") or "\n-" in content or "\n```" in content:
        return "markdown"
    return "text"


def _metadata_details(event: SessionEvent) -> str:
    if not event.metadata:
        return event.content
    import json

    return json.dumps(event.metadata, ensure_ascii=False, indent=2)


def _find_memory(store: MemoryStore, name: str) -> tuple[MemoryEntry, Path, bool]:
    for entry, path, candidate in store.list_with_paths(include_candidates=True):
        if entry.name == name or path.stem == name or str(path) == name:
            return entry, path, candidate
    raise FileNotFoundError(f"Memory not found: {name}")


def _single_line(text: str, limit: int = 120) -> str:
    value = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _relative_or_iso(created_at: str | None) -> str:
    return created_at or "Never"


def _mtime(path: Path) -> float:
    return path.stat().st_mtime


def _date_from_journal_path(path: Path) -> date | None:
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def _preview_markdown(content: str, limit: int = 240) -> str:
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    preview = " ".join(lines)
    if len(preview) <= limit:
        return preview
    return preview[: limit - 3].rstrip() + "..."


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
