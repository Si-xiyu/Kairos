from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from kairos.config import KairosPaths


SCHEDULE_FILE = "cron.json"


class ScheduleKind(str, Enum):
    AT = "at"
    EVERY = "every"
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    CRON = "cron"


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _datetime_to_json(value: datetime | None) -> str | None:
    value = _coerce_datetime(value)
    if value is None:
        return None
    return value.isoformat()


def _datetime_from_json(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _coerce_datetime(datetime.fromisoformat(value))


@dataclass(frozen=True)
class ScheduledJob:
    id: str
    name: str
    schedule: dict[str, Any]
    payload: dict[str, Any]
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    failure_count: int = 0
    max_failures: int = 5
    last_error: str | None = None
    disabled_reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_run_at"] = _datetime_to_json(self.last_run_at)
        data["next_run_at"] = _datetime_to_json(self.next_run_at)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ScheduledJob":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            schedule=dict(data["schedule"]),
            payload=dict(data.get("payload", {})),
            enabled=bool(data.get("enabled", True)),
            last_run_at=_datetime_from_json(data.get("last_run_at")),
            next_run_at=_datetime_from_json(data.get("next_run_at")),
            failure_count=int(data.get("failure_count", 0)),
            max_failures=int(data.get("max_failures", 5)),
            last_error=data.get("last_error"),
            disabled_reason=data.get("disabled_reason"),
        )

    def is_due(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        due_at = self.next_run_at
        if due_at is None and self.last_run_at is not None:
            due_at = self.next_due_after(self.last_run_at)
        if due_at is None and _schedule_kind(self.schedule) in {
            ScheduleKind.AT,
            ScheduleKind.ONCE,
        }:
            due_at = self.next_due_after(now)
        return due_at is not None and due_at <= _coerce_datetime(now)

    def next_due_after(self, after: datetime | None) -> datetime | None:
        schedule = self.schedule
        kind = _schedule_kind(schedule)
        after = _coerce_datetime(after) or datetime.now(timezone.utc)

        if kind in {ScheduleKind.AT, ScheduleKind.ONCE}:
            return _datetime_from_json(schedule.get("at"))
        if kind in {ScheduleKind.EVERY, ScheduleKind.INTERVAL}:
            seconds = int(schedule.get("seconds", schedule.get("every_seconds", 0)))
            return after + timedelta(seconds=seconds)
        if kind == ScheduleKind.DAILY:
            hour = int(schedule["hour"])
            minute = int(schedule.get("minute", 0))
            candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= after:
                candidate += timedelta(days=1)
            return candidate
        if kind == ScheduleKind.CRON:
            return _next_cron_after(str(schedule["expr"]), after)
        return None

    def with_success(self, now: datetime) -> "ScheduledJob":
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        kind = _schedule_kind(self.schedule)
        next_run_at = self.next_due_after(now)
        enabled = self.enabled
        if kind in {ScheduleKind.AT, ScheduleKind.ONCE}:
            enabled = False
            next_run_at = None
        return ScheduledJob(
            id=self.id,
            name=self.name,
            schedule=self.schedule,
            payload=self.payload,
            enabled=enabled,
            last_run_at=now,
            next_run_at=next_run_at,
            failure_count=0,
            max_failures=self.max_failures,
            last_error=None,
            disabled_reason="completed" if not enabled else None,
        )

    def with_failure(self, error: str, now: datetime) -> "ScheduledJob":
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        failure_count = self.failure_count + 1
        enabled = self.enabled and failure_count < self.max_failures
        return ScheduledJob(
            id=self.id,
            name=self.name,
            schedule=self.schedule,
            payload=self.payload,
            enabled=enabled,
            last_run_at=self.last_run_at,
            next_run_at=self.next_due_after(now),
            failure_count=failure_count,
            max_failures=self.max_failures,
            last_error=error,
            disabled_reason=None if enabled else "max_failures_exceeded",
        )

    def with_enabled(self, enabled: bool) -> "ScheduledJob":
        return ScheduledJob(
            id=self.id,
            name=self.name,
            schedule=self.schedule,
            payload=self.payload,
            enabled=enabled,
            last_run_at=self.last_run_at,
            next_run_at=self.next_run_at,
            failure_count=self.failure_count,
            max_failures=self.max_failures,
            last_error=self.last_error,
            disabled_reason=None if enabled else "disabled_by_user",
        )


@dataclass(frozen=True)
class ScheduleStore:
    paths: KairosPaths
    filename: str = SCHEDULE_FILE
    jobs: list[ScheduledJob] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return self.paths.schedules / self.filename

    def load(self) -> list[ScheduledJob]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [ScheduledJob.from_json(job) for job in data.get("jobs", [])]

    def save(self, jobs: list[ScheduledJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"jobs": [job.to_json() for job in jobs]}
        tmp = self.path.parent / f".tmp.{self.path.stem}.{uuid4().hex}.json"
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp, self.path)

    def due(self, now: datetime | None = None) -> list[ScheduledJob]:
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        return [job for job in self.load() if job.is_due(now)]

    def upsert(self, job: ScheduledJob) -> None:
        jobs = self.load()
        replaced = False
        updated: list[ScheduledJob] = []
        for existing in jobs:
            if existing.id == job.id:
                updated.append(job)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(job)
        self.save(updated)

    def add(self, job: ScheduledJob) -> None:
        self.upsert(job)

    def update(self, job: ScheduledJob) -> None:
        self.upsert(job)

    def delete(self, job_id: str) -> bool:
        jobs = self.load()
        updated = [job for job in jobs if job.id != job_id]
        if len(updated) == len(jobs):
            return False
        self.save(updated)
        return True

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        jobs = self.load()
        found = False
        updated: list[ScheduledJob] = []
        for job in jobs:
            if job.id == job_id:
                updated.append(job.with_enabled(enabled))
                found = True
            else:
                updated.append(job)
        if not found:
            return False
        self.save(updated)
        return True

    def mark_success(self, job_id: str, now: datetime | None = None) -> None:
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        self._update_job(job_id, lambda job: job.with_success(now))

    def mark_failure(
        self,
        job_id: str,
        error: str,
        now: datetime | None = None,
    ) -> None:
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        self._update_job(job_id, lambda job: job.with_failure(error, now))

    def _update_job(self, job_id: str, update: Any) -> None:
        jobs = self.load()
        self.save([update(job) if job.id == job_id else job for job in jobs])


def _next_cron_after(expr: str, after: datetime) -> datetime:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"expected 5-field cron expression, got: {expr}")
    minute, hour, day, month, weekday = [_parse_cron_field(part) for part in parts]
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = candidate + timedelta(days=366)

    while candidate <= deadline:
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            _matches(candidate.minute, minute)
            and _matches(candidate.hour, hour)
            and _matches(candidate.day, day)
            and _matches(candidate.month, month)
            and _matches(cron_weekday, weekday)
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError(f"cron expression has no due time within one year: {expr}")


def _parse_cron_field(raw: str) -> set[int] | None:
    if raw == "*":
        return None
    values = {int(part) for part in raw.split(",")}
    if 7 in values:
        values.remove(7)
        values.add(0)
    return values


def _matches(value: int, allowed: set[int] | None) -> bool:
    return allowed is None or value in allowed


def compute_next_run(job: ScheduledJob, now: datetime | None = None) -> datetime | None:
    return job.next_due_after(_coerce_datetime(now) or datetime.now(timezone.utc))


def due_jobs(jobs: list[ScheduledJob], now: datetime) -> list[ScheduledJob]:
    now = _coerce_datetime(now) or datetime.now(timezone.utc)
    return [job for job in jobs if job.is_due(now)]


def mark_success(job: ScheduledJob, now: datetime) -> ScheduledJob:
    return job.with_success(now)


def mark_failure(
    job: ScheduledJob,
    now: datetime,
    error: str = "error",
    max_errors: int = 5,
) -> ScheduledJob:
    if job.max_failures == max_errors:
        return job.with_failure(error, now)
    normalized = ScheduledJob(
        id=job.id,
        name=job.name,
        schedule=job.schedule,
        payload=job.payload,
        enabled=job.enabled,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        failure_count=job.failure_count,
        max_failures=max_errors,
        last_error=job.last_error,
        disabled_reason=job.disabled_reason,
    )
    return normalized.with_failure(error, now)


def _schedule_kind(schedule: dict[str, Any]) -> ScheduleKind | str:
    raw = str(schedule.get("kind", "")).lower()
    try:
        return ScheduleKind(raw)
    except ValueError:
        return raw
