from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kairos.backend.approvals import ApprovalStore
from kairos.backend.scopes import ProjectScopeStore
from kairos.backend.settings import SettingsStore
from kairos.backend.todos import TodoStore, proposed_todo
from kairos.channels import ChannelManager, CLIChannel, WindowsToastChannel
from kairos.capabilities import SkillRegistry, list_capabilities
from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext
from kairos.core.session import SessionEvent, SessionStore
from kairos.delivery import DeliveryQueue, DeliveryRunner
from kairos.lifelog import (
    DailyJournalStore,
    JournalDraftBuilder,
    ReflectionFragment,
    WeeklyReviewStore,
    write_reflection_draft,
)
from kairos.lifelog.artifacts import JournalArtifactStore
from kairos.memory import MemoryEntry, MemoryScope, MemoryStore, MemoryType
from kairos.memory.candidates import MemoryCandidateExtractor, save_candidates
from kairos.messages import InboundMessage, OutboundMessage
from kairos.permissions import AutonomyLevel
from kairos.presence import (
    DaemonRuntime,
    HeartbeatRunner,
    PRESENCE_SESSION_ID,
    PresenceEvent,
    ScheduleStore,
    ScheduledJob,
)

DEFAULT_JOURNAL_REMINDER = "今天还没有留下记录。要不要随手丢几个碎片给我，我帮你整理成日记？"
DEFAULT_JOURNAL_CAPTURE_HEADING = "有价值的对话"


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
                    "message": DEFAULT_JOURNAL_REMINDER,
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
        today_payload = self.today()
        capabilities = self.capabilities()
        schedules = today_payload["reminders"]["items"]
        return {
            "app": {"name": "Kairos", "mode": "local-first-backend"},
            "doctor": doctor,
            "today": {
                "date": today_payload["date"],
                "journal_exists": today_payload["diary"]["exists"],
                "journal_path": today_payload["diary"]["path"],
            },
            "recent_journals": self.list_journals(limit=7)["journals"],
            "memories": self.list_memories(include_candidates=True)["summary"],
            "schedules": {
                "total": today_payload["reminders"]["total"],
                "enabled": today_payload["reminders"]["enabled"],
                "due": today_payload["reminders"]["due"],
                "items": schedules[:5],
            },
            "delivery": today_payload["delivery"],
            "presence": {
                "session_id": PRESENCE_SESSION_ID,
                "events": len(self.list_session_events(PRESENCE_SESSION_ID)["events"]),
            },
            "capabilities": {
                "tools": len(capabilities["tools"]),
                "skills": len(capabilities["skills"]),
                "mcp_plugins": len(capabilities["mcp_plugins"]),
            },
            "sessions": today_payload["recent_sessions"],
        }

    def today(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        today = date.today()
        journal_store = DailyJournalStore(self.paths)
        todo_store = TodoStore(self.paths)
        todos = todo_store.list_todos(status="open")
        due_todos, upcoming_todos = _due_and_upcoming_todos(todos)
        schedules = self.list_schedules()["schedules"]
        due_jobs = ScheduleStore(self.paths).due()
        memories = self.list_memories(include_candidates=True)["summary"]
        approvals = self.list_approvals(status="pending")["actions"]
        return {
            "date": today.isoformat(),
            "diary": {
                "date": today.isoformat(),
                "exists": journal_store.exists(today),
                "path": str(journal_store.path_for(today)),
                "available": True,
            },
            "todos": {
                "available": True,
                "items": _upcoming_todos(todos),
                "due": due_todos,
                "upcoming": upcoming_todos,
                "total_open": len(todos),
            },
            "reminders": {
                "available": True,
                "total": len(schedules),
                "enabled": sum(1 for job in schedules if job["enabled"]),
                "due": len(due_jobs),
                "high_level": [todo for todo in todos if todo.get("reminder_level") == "high"],
                "normal": [todo for todo in todos if todo.get("reminder_level") == "normal"],
                "companion_nudges": [],
                "items": schedules[:10],
            },
            "recent_artifacts": self.recent_journal_artifacts(limit=7),
            "recent_sessions": self.list_sessions(limit=5)["sessions"],
            "memory": {
                "pending_candidates": memories["candidates"],
                "available": True,
            },
            "approvals": {
                "available": True,
                "pending": len(approvals),
                "actions": approvals,
            },
            "delivery": {
                "pending": _count_files(self.paths.delivery_pending, "*.json"),
                "failed": _count_files(self.paths.delivery_failed, "*.json"),
            },
            "daemon": {
                "available": True,
                "heartbeat_session_id": PRESENCE_SESSION_ID,
                "presence_events": len(self.list_session_events(PRESENCE_SESSION_ID)["events"]),
            },
            "model": self.model_status(),
        }

    def model_status(self) -> dict[str, Any]:
        llm = SettingsStore(self.paths).read()["llm"]
        provider = str(llm.get("provider") or "local")
        if provider in {"openai-compatible", "openai", "api", "deepseek"}:
            return {
                "provider": "openai-compatible",
                "suggested_provider": "deepseek",
                "base_url": llm.get("base_url") or "https://api.deepseek.com/v1",
                "model": llm.get("model") or "deepseek-chat",
                "configured": bool(llm.get("api_key_configured")),
            }
        return {
            "provider": "local",
            "suggested_provider": "deepseek",
            "base_url": None,
            "model": "kairos-local-mvp",
            "configured": True,
        }

    def settings(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return SettingsStore(self.paths).read()

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return SettingsStore(self.paths).update(values)

    def list_project_scopes(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"scopes": ProjectScopeStore(self.paths).list()}

    def create_project_scope(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"scope": ProjectScopeStore(self.paths).create(values)}

    def update_project_scope(self, scope_id: str, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"scope": ProjectScopeStore(self.paths).update(scope_id, values)}

    def delete_project_scope(self, scope_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"deleted": ProjectScopeStore(self.paths).delete(scope_id)}

    def list_approvals(self, status: str | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        actions = ApprovalStore(self.paths).list(status=status)
        return {"actions": actions, "pending": sum(1 for item in actions if item.get("status") == "pending")}

    def approve_action(self, approval_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        action = ApprovalStore(self.paths).set_status(approval_id, "approved")
        result: dict[str, Any] | None = None
        if action.get("action_type") == "todo.create":
            payload = action.get("payload", {})
            arguments = payload.get("arguments", payload) if isinstance(payload, dict) else {}
            if isinstance(arguments, dict):
                result = self.create_todo(arguments)
        return {"action": action, "result": result}

    def reject_action(self, approval_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"action": ApprovalStore(self.paths).set_status(approval_id, "rejected")}

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
            "candidates": [
                {
                    "name": candidate.entry.name,
                    "description": candidate.entry.description,
                    "type": candidate.entry.type.value,
                    "reason": candidate.reason,
                    "source": candidate.entry.source,
                }
                for candidate in candidates
            ],
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
            "memories": [_memory_to_api(entry, path, candidate) for entry, path, candidate in entries],
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
            if journal_date is None:
                continue
            content = path.read_text(encoding="utf-8")
            journals.append(
                {
                    "date": journal_date.isoformat(),
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
        heading: str = DEFAULT_JOURNAL_CAPTURE_HEADING,
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        DailyJournalStore(self.paths).append_fragment(journal_date, heading, text)
        return self.read_journal(journal_date)

    def capture_session_to_journal(
        self,
        session_id: str,
        journal_date: date | None = None,
        heading: str = DEFAULT_JOURNAL_CAPTURE_HEADING,
        include_roles: list[str] | None = None,
        artifact_type: str = "diary",
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        journal_date = journal_date or date.today()
        include_roles = include_roles or ["user", "assistant"]
        events = [
            event
            for event in SessionStore(self.paths).read(session_id)
            if event.role in include_roles and event.content.strip()
        ]
        if not events:
            return {**self.read_journal(journal_date), "captured": 0, "session_id": session_id}

        summary = _summarize_session_events(events)
        body = _journal_capture_body(session_id, summary)
        if artifact_type == "record":
            artifact = self.create_journal_artifact(
                {
                    "type": "record",
                    "title": heading,
                    "summary": summary["summary"],
                    "tags": ["capture"],
                    "source": {"kind": "chat", "session_id": session_id},
                    "body": body,
                }
            )["artifact"]
            return {
                "captured": len(events),
                "session_id": session_id,
                "message": "已加入记录",
                "artifact": artifact,
                "summary": summary,
            }

        DailyJournalStore(self.paths).append_fragment(journal_date, heading, body)
        return {
            **self.read_journal(journal_date),
            "captured": len(events),
            "session_id": session_id,
            "message": "已加入日记",
            "summary": summary,
        }

    def journal_capture(self, values: dict[str, Any]) -> dict[str, Any]:
        session_id = str(values.get("session") or values.get("session_id") or "")
        if session_id:
            return self.capture_session_to_journal(
                session_id=session_id,
                journal_date=_date_from_value(values.get("date")),
                heading=str(values.get("title") or values.get("heading") or DEFAULT_JOURNAL_CAPTURE_HEADING),
                include_roles=values.get("include_roles"),
                artifact_type=str(values.get("type", values.get("artifact_type", "diary"))),
            )
        text = str(values.get("text", "")).strip()
        if not text:
            raise ValueError("session or text is required")
        artifact_type = str(values.get("type", values.get("artifact_type", "record")))
        summary = _summarize_text(text)
        body = _journal_capture_body(None, summary)
        if artifact_type == "diary":
            journal_date = _date_from_value(values.get("date")) or date.today()
            DailyJournalStore(self.paths).append_fragment(
                journal_date,
                str(values.get("title") or DEFAULT_JOURNAL_CAPTURE_HEADING),
                body,
            )
            return {**self.read_journal(journal_date), "message": "已加入日记", "summary": summary, "captured": 1}
        artifact = self.create_journal_artifact(
            {
                "type": "record",
                "title": str(values.get("title") or "Conversation record"),
                "summary": summary["summary"],
                "tags": values.get("tags", ["capture"]),
                "source": {"kind": "chat", "session_id": None},
                "body": body,
            }
        )["artifact"]
        return {"message": "已加入记录", "artifact": artifact, "summary": summary, "captured": 1}

    def recent_journal_artifacts(self, limit: int = 7) -> list[dict[str, Any]]:
        artifacts = JournalArtifactStore(self.paths).list(limit=limit)
        legacy = self.list_journals(limit=limit)["journals"]
        legacy_artifacts = [
            {
                "id": item["date"],
                "type": "diary",
                "title": item["title"],
                "created_at": item["updated_at"],
                "updated_at": item["updated_at"],
                "tags": [],
                "source": {"kind": "manual", "session_id": None},
                "date": item["date"],
                "summary": None,
                "preview": item["preview"],
                "path": item["path"],
            }
            for item in legacy
        ]
        combined = [*artifacts, *legacy_artifacts]
        combined.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return combined[:limit]

    def list_journal_artifacts(self, artifact_type: str | None = None, limit: int = 50) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"artifacts": JournalArtifactStore(self.paths).list(artifact_type=artifact_type, limit=limit)}

    def read_journal_artifact(self, artifact_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"artifact": JournalArtifactStore(self.paths).read(artifact_id)}

    def create_journal_artifact(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"artifact": JournalArtifactStore(self.paths).create(values)}

    def update_journal_artifact(self, artifact_id: str, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"artifact": JournalArtifactStore(self.paths).update(artifact_id, values)}

    def delete_journal_artifact(self, artifact_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"deleted": JournalArtifactStore(self.paths).delete(artifact_id)}

    def list_todos(self, status: str | None = None, list_id: str | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        store = TodoStore(self.paths)
        return {"todos": store.list_todos(status=status, list_id=list_id), "lists": store.list_lists()}

    def create_todo(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        todo = TodoStore(self.paths).create_todo(values)
        enqueued = self.enqueue_due_todo_reminders()
        return {"todo": todo, "delivery_enqueued": enqueued["enqueued"]}

    def update_todo(self, todo_id: str, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        todo = TodoStore(self.paths).update_todo(todo_id, values)
        enqueued = self.enqueue_due_todo_reminders()
        return {"todo": todo, "delivery_enqueued": enqueued["enqueued"]}

    def complete_todo(self, todo_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"todo": TodoStore(self.paths).complete_todo(todo_id)}

    def delete_todo(self, todo_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"deleted": TodoStore(self.paths).delete_todo(todo_id)}

    def propose_todo(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return proposed_todo(values)

    def enqueue_due_todo_reminders(self, now: datetime | None = None) -> dict[str, Any]:
        ensure_workspace(self.paths)
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        store = TodoStore(self.paths)
        queue = DeliveryQueue(self.paths)
        enqueued: list[dict[str, Any]] = []
        for todo in store.list_todos(status="open"):
            if todo.get("reminder_level") == "none" or not todo.get("remind_at"):
                continue
            remind_at = _parse_iso_datetime(str(todo["remind_at"]))
            if remind_at > now or todo.get("reminder_delivery_id"):
                continue
            prefix = "High-level reminder" if todo.get("reminder_level") == "high" else "Reminder"
            delivery_id = queue.enqueue(
                channel="windows_toast",
                to="local-user",
                text=f"{prefix}: {todo['title']}",
                now=now,
            )
            updated = store.update_todo(
                str(todo["id"]),
                {
                    "reminder_delivery_id": delivery_id,
                    "reminder_delivered_at": now.isoformat(),
                },
            )
            enqueued.append(updated)
        return {"enqueued": len(enqueued), "todos": enqueued}

    def list_todo_lists(self) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"lists": TodoStore(self.paths).list_lists()}

    def create_todo_list(self, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"list": TodoStore(self.paths).create_list(values)}

    def update_todo_list(self, list_id: str, values: dict[str, Any]) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"list": TodoStore(self.paths).update_list(list_id, values)}

    def delete_todo_list(self, list_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"deleted": TodoStore(self.paths).delete_list(list_id)}

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
        return {"updated": ScheduleStore(self.paths).set_enabled(job_id, enabled)}

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
            channel_manager=ChannelManager([CaptureCLIChannel(), WindowsToastChannel()]),
            presence_handler=lambda event, now: _presence_handler(event, now, self.paths),
        )
        result = runtime.tick()
        todo_reminders = self.enqueue_due_todo_reminders()
        return {
            "due_jobs": result.due_jobs,
            "todo_reminders": todo_reminders["enqueued"],
            "enqueued": result.enqueued,
            "failed_jobs": result.failed_jobs,
            "delivery": result.delivery,
            "delivered": delivered,
        }

    def heartbeat_tick(
        self,
        force: bool = False,
        user_active: bool = False,
        do_not_disturb: bool = False,
        channel: str = "windows_toast",
        to: str = "local-user",
    ) -> dict[str, Any]:
        ensure_workspace(self.paths)
        delivered: list[dict[str, str]] = []

        class CaptureCLIChannel(CLIChannel):
            def send(self, to: str, text: str, **kwargs: object) -> bool:
                delivered.append({"channel": self.name, "to": to, "text": text})
                return super().send(to=to, text=text, **kwargs)

        class CaptureWindowsToastChannel(WindowsToastChannel):
            def send(self, to: str, text: str, **kwargs: object) -> bool:
                delivered.append({"channel": self.name, "to": to, "text": text})
                return super().send(to=to, text=text, **kwargs)

        run = HeartbeatRunner(self.paths).run(
            force=force,
            user_active=user_active,
            do_not_disturb=do_not_disturb,
        )
        queue = DeliveryQueue(self.paths)
        enqueued = 0
        if run.should_notify:
            queue.enqueue(channel=channel, to=to, text=run.message)
            enqueued = 1
        delivery = DeliveryRunner(
            queue,
            ChannelManager([CaptureCLIChannel(), CaptureWindowsToastChannel()]).send,
        ).process_once()
        return {
            "heartbeat": run.to_json(),
            "enqueued": enqueued,
            "delivery": delivery,
            "delivered": delivered,
            **self._session_payload(PRESENCE_SESSION_ID),
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
            **self._session_payload(session),
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

    def read_session(self, session_id: str) -> dict[str, Any]:
        ensure_workspace(self.paths)
        return {"session": self._session_to_api(session_id, SessionStore(self.paths).read(session_id))}

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

    def _session_payload(self, session_id: str) -> dict[str, Any]:
        store = SessionStore(self.paths)
        events = store.read(session_id)
        return {
            "session": self._session_to_api(session_id, events),
            "messages": [_session_event_to_message(session_id, index, event) for index, event in enumerate(events)],
            "events": [
                _session_event_to_agent_event(session_id, index, event)
                for index, event in enumerate(events)
                if event.role in {"tool", "system"} or event.metadata
            ],
        }

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
        raw_daily: list[tuple[date, str]] = []
        cursor = start_date
        while cursor <= end_date:
            content = store.read(cursor)
            if content.strip():
                raw_daily.append((cursor, content))
                notes.append(f"{cursor.isoformat()}: {_preview_markdown(content, limit=160)}")
            cursor += timedelta(days=1)
        sections = _weekly_sections(raw_daily)
        review_store = WeeklyReviewStore(self.paths)
        path = review_store.create(start_date, end_date, daily_notes=notes, section_content=sections)
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "path": str(path),
            "content": review_store.read(start_date, end_date),
            "sections": sections,
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


def _presence_handler(event: PresenceEvent, now: datetime, paths: KairosPaths):
    if event.event == "heartbeat":
        run = HeartbeatRunner(paths).run(
            now=now,
            user_active=bool(event.payload.get("user_active", False)),
            do_not_disturb=bool(event.payload.get("do_not_disturb", False)),
            force=bool(event.payload.get("force", True)),
        )
        if not run.should_notify:
            return []
        return [
            OutboundMessage(
                channel=str(event.payload.get("channel", "windows_toast")),
                to=str(event.payload.get("to", "local-user")),
                text=run.message,
            )
        ]
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
        return DEFAULT_JOURNAL_REMINDER
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
        "candidate_reason": entry.candidate_reason,
        "source_journal_date": _source_journal_date(entry.source),
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


def _source_journal_date(source: str | None) -> str | None:
    if not source or not source.startswith("journal/"):
        return None
    return source.removeprefix("journal/")


def _weekly_sections(daily_notes: list[tuple[date, str]]) -> dict[str, list[str]]:
    sections = {
        "这一周你做了什么": [],
        "哪些事情给你能量": [],
        "哪些事情反复消耗你": [],
        "反复出现的主题": [],
        "Kairos 观察到的模式": [],
        "下周可以调整什么": [],
    }
    seen_themes: dict[str, int] = {}
    for day, content in daily_notes:
        for line in _meaningful_lines(content):
            prefix = f"{day.isoformat()}: "
            if _contains_any(line, {"做了", "完成", "实现", "修复", "写", "提交", "推进"}):
                sections["这一周你做了什么"].append(prefix + line)
            if _contains_any(line, {"有能量", "有精力", "开心", "兴奋", "满足", "成就"}):
                sections["哪些事情给你能量"].append(prefix + line)
            if _contains_any(line, {"消耗", "疲惫", "累", "无力", "压力", "焦虑"}):
                sections["哪些事情反复消耗你"].append(prefix + line)
            if _contains_any(line, {"反复", "总是", "经常", "通常", "每次"}):
                sections["反复出现的主题"].append(prefix + line)
            for keyword in ("架构", "日记", "记忆", "前端", "后端", "通知", "任务", "Todo"):
                if keyword in line:
                    seen_themes[keyword] = seen_themes.get(keyword, 0) + 1

    repeated = [f"`{theme}` 在本周记录中出现 {count} 次。" for theme, count in seen_themes.items() if count >= 2]
    sections["Kairos 观察到的模式"].extend(repeated)
    if sections["哪些事情反复消耗你"]:
        sections["下周可以调整什么"].append("优先减少反复消耗项，为深度工作留出连续时间。")
    if sections["哪些事情给你能量"]:
        sections["下周可以调整什么"].append("保留至少一个带来能量的工作块，不要只安排维护性任务。")
    if not sections["下周可以调整什么"] and daily_notes:
        sections["下周可以调整什么"].append("继续记录每天的行动、能量和消耗，先积累更清晰的样本。")
    return {key: value for key, value in sections.items() if value}


def _meaningful_lines(content: str) -> list[str]:
    return [
        line.strip("- ").strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


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
        if line.strip() and not line.lstrip().startswith("#") and not line.strip() == "---"
    ]
    preview = " ".join(lines)
    if len(preview) <= limit:
        return preview
    return preview[: limit - 3].rstrip() + "..."


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return _coerce_datetime(parsed)


def _date_from_value(value: object | None) -> date | None:
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value))


def _upcoming_todos(todos: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    def key(todo: dict[str, Any]) -> tuple[str, str]:
        due = str(todo.get("due_at") or todo.get("remind_at") or "9999-12-31T23:59:59+00:00")
        return due, str(todo.get("created_at", ""))

    return sorted(todos, key=key)[:limit]


def _due_and_upcoming_todos(todos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now(timezone.utc)
    due: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for todo in _upcoming_todos(todos, limit=len(todos) or 1):
        raw = todo.get("due_at") or todo.get("remind_at")
        if raw and _parse_iso_datetime(str(raw)) <= now:
            due.append(todo)
        else:
            upcoming.append(todo)
    return due, upcoming[:10]


def _summarize_session_events(events: list[SessionEvent]) -> dict[str, Any]:
    user_lines = [_single_line(event.content, 180) for event in events if event.role == "user"]
    assistant_lines = [_single_line(event.content, 180) for event in events if event.role == "assistant"]
    topic_source = user_lines[0] if user_lines else (assistant_lines[0] if assistant_lines else "Conversation")
    highlights = [line for line in [*user_lines[:3], *assistant_lines[:2]] if line]
    action_items = [
        line
        for line in highlights
        if _contains_any(line.lower(), {"todo", "remind", "deadline", "follow up", "action", "任务", "提醒", "截止", "跟进"})
    ]
    return {
        "summary": _single_line(topic_source, 160),
        "topics": highlights[:5],
        "decisions": [],
        "action_items": action_items[:5],
        "message_count": len(events),
    }


def _summarize_text(text: str) -> dict[str, Any]:
    lines = [_single_line(line, 180) for line in text.splitlines() if line.strip()]
    if not lines:
        lines = [_single_line(text, 180)]
    action_items = [
        line
        for line in lines
        if _contains_any(line.lower(), {"todo", "remind", "deadline", "follow up", "action", "任务", "提醒", "截止", "跟进"})
    ]
    return {
        "summary": _single_line(lines[0], 160),
        "topics": lines[:5],
        "decisions": [],
        "action_items": action_items[:5],
        "message_count": 1,
    }


def _journal_capture_body(session_id: str | None, summary: dict[str, Any]) -> str:
    lines = []
    if session_id:
        lines.extend([f"来源会话：`{session_id}`", ""])
    lines.extend(["## 摘要", "", str(summary["summary"]), "", "## 要点", ""])
    topics = summary.get("topics") or []
    lines.extend(f"- {topic}" for topic in topics)
    action_items = summary.get("action_items") or []
    if action_items:
        lines.extend(["", "## 行动项", ""])
        lines.extend(f"- {item}" for item in action_items)
    return "\n".join(lines).rstrip()
