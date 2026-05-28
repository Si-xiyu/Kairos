from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from kairos.config import KairosPaths
from kairos.core.session import SessionEvent, SessionStore
from kairos.lifelog import DailyJournalStore
from kairos.memory import MemoryStore

from .heartbeat import HeartbeatPolicy, HeartbeatState, should_run

HEARTBEAT_OK = "HEARTBEAT_OK"
PRESENCE_SESSION_ID = "kairos-presence"


@dataclass(frozen=True)
class HeartbeatRun:
    status: Literal["ok", "notify", "skipped"]
    reason: str
    message: str = HEARTBEAT_OK
    snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def should_notify(self) -> bool:
        return self.status == "notify" and self.message != HEARTBEAT_OK

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class HeartbeatRunner:
    """Local proactive check inspired by OpenClaw heartbeat semantics.

    It is intentionally deterministic: gather local context, decide whether a
    lightweight reminder is warranted, persist the event, then let delivery
    queues handle side effects.
    """

    def __init__(
        self,
        paths: KairosPaths,
        policy: HeartbeatPolicy | None = None,
        session_id: str = PRESENCE_SESSION_ID,
    ) -> None:
        self.paths = paths
        self.policy = policy or HeartbeatPolicy()
        self.session_id = session_id
        self.state_path = paths.home / "presence" / "heartbeat-state.json"

    def run(
        self,
        now: datetime | None = None,
        user_active: bool = False,
        do_not_disturb: bool = False,
        force: bool = False,
    ) -> HeartbeatRun:
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        state = self._load_state(now)
        allowed, reason = should_run(now, self.policy, state, user_active, do_not_disturb)
        snapshot = self._snapshot(now)

        if not allowed and not force:
            run = HeartbeatRun(status="skipped", reason=reason, snapshot=snapshot)
            self._record(run, now)
            return run

        message, decision_reason = self._decide_message(now, snapshot)
        status: Literal["ok", "notify"] = "notify" if message != HEARTBEAT_OK else "ok"
        run = HeartbeatRun(
            status=status,
            reason=decision_reason if status == "notify" else "heartbeat_ok",
            message=message,
            snapshot=snapshot,
        )
        self._save_state(now, state, notified=run.should_notify)
        self._record(run, now)
        return run

    def _snapshot(self, now: datetime) -> dict[str, Any]:
        memory_store = MemoryStore(self.paths)
        confirmed = memory_store.list() if self.paths.memory.exists() else []
        all_memories = (
            memory_store.list(include_candidates=True) if self.paths.memory.exists() else []
        )
        recent_sessions = _recent_session_summaries(self.paths, limit=3)
        journal_store = DailyJournalStore(self.paths)
        today = now.date()
        return {
            "now": now.isoformat(),
            "today": today.isoformat(),
            "today_journal_exists": journal_store.exists(today),
            "confirmed_memories": len(confirmed),
            "memory_candidates": max(0, len(all_memories) - len(confirmed)),
            "recent_sessions": recent_sessions,
            "delivery_pending": _count_json(self.paths.delivery_pending),
            "delivery_failed": _count_json(self.paths.delivery_failed),
        }

    def _decide_message(self, now: datetime, snapshot: dict[str, Any]) -> tuple[str, str]:
        if snapshot["memory_candidates"] >= 3:
            return (
                f"Kairos has {snapshot['memory_candidates']} memory candidates waiting for review.",
                "memory_candidates_pending",
            )
        if not snapshot["today_journal_exists"] and now.hour >= 21:
            return (
                "You have not written today's journal yet. Want to leave a quick note?",
                "daily_journal_missing",
            )
        if snapshot["delivery_failed"]:
            return (
                f"Kairos has {snapshot['delivery_failed']} failed delivery item(s) to review.",
                "delivery_failures",
            )
        return HEARTBEAT_OK, "no_action"

    def _record(self, run: HeartbeatRun, now: datetime) -> None:
        SessionStore(self.paths).append(
            self.session_id,
            SessionEvent(
                role="system",
                content=run.message,
                created_at=now.isoformat(),
                metadata={
                    "title": "Heartbeat",
                    "kind": "heartbeat",
                    "status": run.status,
                    "reason": run.reason,
                    "snapshot": run.snapshot,
                },
            ),
        )

    def _load_state(self, now: datetime) -> HeartbeatState:
        if not self.state_path.exists():
            return HeartbeatState()
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        today = now.date().isoformat()
        notifications_today = int(data.get("notifications_today", 0))
        if data.get("notification_date") != today:
            notifications_today = 0
        return HeartbeatState(
            last_run_at=_datetime_from_json(data.get("last_run_at")),
            running=bool(data.get("running", False)),
            notifications_today=notifications_today,
            last_notification_at=_datetime_from_json(data.get("last_notification_at")),
        )

    def _save_state(self, now: datetime, state: HeartbeatState, notified: bool) -> None:
        next_state = {
            "last_run_at": now.isoformat(),
            "running": False,
            "notifications_today": state.notifications_today + (1 if notified else 0),
            "notification_date": now.date().isoformat(),
            "last_notification_at": now.isoformat() if notified else _datetime_to_json(state.last_notification_at),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _recent_session_summaries(paths: KairosPaths, limit: int) -> list[dict[str, Any]]:
    if not paths.conversations.exists():
        return []
    store = SessionStore(paths)
    sessions: list[dict[str, Any]] = []
    for path in sorted(paths.conversations.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        session_id = path.stem
        if session_id == PRESENCE_SESSION_ID:
            continue
        events = store.read(session_id)
        latest = next((event for event in reversed(events) if event.role in {"user", "assistant"}), None)
        if latest is None:
            continue
        sessions.append(
            {
                "id": session_id,
                "latest_role": latest.role,
                "latest": " ".join(latest.content.split())[:160],
                "updated_at": latest.created_at,
            }
        )
        if len(sessions) >= limit:
            break
    return sessions


def _count_json(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.glob("*.json") if not item.name.startswith(".tmp."))


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _datetime_from_json(value: str | None) -> datetime | None:
    if not value:
        return None
    return _coerce_datetime(datetime.fromisoformat(value))


def _datetime_to_json(value: datetime | None) -> str | None:
    value = _coerce_datetime(value)
    return value.isoformat() if value else None
