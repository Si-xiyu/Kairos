from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.config import KairosPaths
from kairos.presence import (
    ScheduleStore,
    ScheduledJob,
    compute_next_run,
    due_jobs,
    mark_failure,
    mark_success,
)


def test_at_job_is_due_and_disables_after_success():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    job = ScheduledJob(
        id="once",
        name="Once",
        schedule={"kind": "at", "at": now.isoformat()},
        payload={"kind": "presence_event", "event": "daily_journal_check"},
    )

    assert due_jobs([job], now) == [job]

    completed = mark_success(job, now)
    assert completed.enabled is False
    assert completed.disabled_reason == "completed"
    assert completed.next_run_at is None


def test_every_job_uses_seconds_and_helper_functions():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    job = ScheduledJob(
        id="repeat",
        name="Repeat",
        schedule={"kind": "every", "seconds": 60},
        payload={"kind": "presence_event", "event": "heartbeat"},
        last_run_at=now - timedelta(seconds=120),
    )

    assert compute_next_run(job, now) == now + timedelta(seconds=60)
    assert due_jobs([job], now) == [job]

    succeeded = mark_success(job, now)
    assert succeeded.next_run_at == now + timedelta(seconds=60)


def test_mark_failure_default_disables_after_five_errors():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    job = ScheduledJob(
        id="fragile",
        name="Fragile",
        schedule={"kind": "every", "seconds": 60},
        payload={"kind": "presence_event", "event": "heartbeat"},
    )

    for _ in range(5):
        job = mark_failure(job, now, "boom")

    assert job.enabled is False
    assert job.failure_count == 5
    assert job.disabled_reason == "max_failures_exceeded"


def test_schedule_store_add_update_aliases(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    store = ScheduleStore(paths)
    job = ScheduledJob(
        id="job",
        name="Job",
        schedule={"kind": "every", "seconds": 60},
        payload={"kind": "presence_event", "event": "heartbeat"},
    )

    store.add(job)
    assert store.load()[0].id == "job"

    updated = ScheduledJob(
        id="job",
        name="Updated",
        schedule={"kind": "every", "seconds": 120},
        payload={"kind": "presence_event", "event": "heartbeat"},
    )
    store.update(updated)
    assert store.load()[0].name == "Updated"
