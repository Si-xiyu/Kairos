from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.channels import ChannelManager, CLIChannel
from kairos.config import KairosPaths
from kairos.delivery import DeliveryQueue, DeliveryRunner, MAX_RETRIES
from kairos.messages import OutboundMessage
from kairos.presence import (
    DaemonRuntime,
    HeartbeatPolicy,
    HeartbeatState,
    ScheduleStore,
    ScheduledJob,
    should_run,
)


def test_enqueue_generates_pending_file(tmp_path):
    queue = DeliveryQueue(KairosPaths.from_root(tmp_path))

    delivery_id = queue.enqueue("cli", "local-user", "hello")

    pending_file = queue.pending_dir / f"{delivery_id}.json"
    assert pending_file.exists()
    pending = queue.load_pending()
    assert len(pending) == 1
    assert pending[0].channel == "cli"
    assert pending[0].text == "hello"


def test_process_once_success_ack_deletes_pending(tmp_path):
    queue = DeliveryQueue(KairosPaths.from_root(tmp_path))
    delivery_id = queue.enqueue("cli", "local-user", "hello")
    runner = DeliveryRunner(queue, lambda channel, to, text: True)

    stats = runner.process_once()

    assert stats["delivered"] == 1
    assert not (queue.pending_dir / f"{delivery_id}.json").exists()


def test_process_once_failure_increments_retry_count(tmp_path):
    queue = DeliveryQueue(KairosPaths.from_root(tmp_path))
    delivery_id = queue.enqueue("cli", "local-user", "hello")
    now = datetime(2030, 5, 15, 12, tzinfo=timezone.utc)
    runner = DeliveryRunner(queue, lambda channel, to, text: False)

    stats = runner.process_once(now=now)

    assert stats["retried"] == 1
    pending = queue.load_pending()[0]
    assert pending.id == delivery_id
    assert pending.retry_count == 1
    assert pending.last_error == "deliver_fn returned false"
    assert pending.next_retry_at == now + timedelta(seconds=5)


def test_max_retries_moves_delivery_to_failed(tmp_path):
    queue = DeliveryQueue(KairosPaths.from_root(tmp_path))
    delivery_id = queue.enqueue("cli", "local-user", "hello")
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)

    for index in range(MAX_RETRIES):
        queue.fail(delivery_id, f"failure {index}", now=now + timedelta(minutes=index))

    assert not (queue.pending_dir / f"{delivery_id}.json").exists()
    assert (queue.failed_dir / f"{delivery_id}.json").exists()


def test_should_run_allows_when_policy_conditions_pass():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)

    allowed, reason = should_run(
        now,
        HeartbeatPolicy(interval_seconds=60, active_hours=(9, 23)),
        HeartbeatState(last_run_at=now - timedelta(minutes=5)),
        user_active=False,
    )

    assert allowed is True
    assert reason == "ok"


def test_should_run_blocks_interval_active_hours_dnd_budget_and_cooldown():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    policy = HeartbeatPolicy(
        interval_seconds=300,
        active_hours=(9, 23),
        daily_notification_budget=1,
        cooldown_seconds=300,
    )

    assert should_run(
        now,
        policy,
        HeartbeatState(last_run_at=now - timedelta(seconds=10)),
        user_active=False,
    ) == (False, "interval")
    assert should_run(
        now,
        policy,
        HeartbeatState(),
        user_active=False,
        do_not_disturb=True,
    ) == (False, "do_not_disturb")
    assert should_run(
        now.replace(hour=2),
        policy,
        HeartbeatState(),
        user_active=False,
    ) == (False, "outside_active_hours")
    assert should_run(
        now,
        policy,
        HeartbeatState(notifications_today=1),
        user_active=False,
    ) == (False, "daily_budget_exhausted")
    assert should_run(
        now,
        policy,
        HeartbeatState(last_notification_at=now - timedelta(seconds=10)),
        user_active=False,
    ) == (False, "cooldown")


def test_should_run_blocks_user_active_and_running():
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    policy = HeartbeatPolicy()

    assert should_run(now, policy, HeartbeatState(), user_active=True) == (
        False,
        "user_active",
    )
    assert should_run(
        now,
        policy,
        HeartbeatState(running=True),
        user_active=False,
    ) == (False, "running")


def test_channel_manager_routes_registered_channels(capsys):
    manager = ChannelManager([CLIChannel()])

    assert manager.names == ("cli",)
    assert manager.send("cli", "local-user", "hello") is True
    assert manager.send("missing", "local-user", "hello") is False
    assert "[kairos:cli:local-user] hello" in capsys.readouterr().out


def test_schedule_store_finds_due_interval_job_and_marks_success(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    store = ScheduleStore(paths)
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    job = ScheduledJob(
        id="heartbeat",
        name="Heartbeat",
        schedule={"kind": "interval", "seconds": 60},
        payload={"kind": "presence_event", "event": "heartbeat"},
        last_run_at=now - timedelta(minutes=2),
    )
    store.save([job])

    due = store.due(now=now)
    assert [item.id for item in due] == ["heartbeat"]

    store.mark_success("heartbeat", now=now)
    updated = store.load()[0]
    assert updated.failure_count == 0
    assert updated.last_run_at == now
    assert updated.next_run_at == now + timedelta(seconds=60)


def test_schedule_store_disables_job_after_max_failures(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    store = ScheduleStore(paths)
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    store.save(
        [
            ScheduledJob(
                id="nightly",
                name="Nightly",
                schedule={"kind": "daily", "hour": 23, "minute": 0},
                payload={"kind": "presence_event", "event": "daily_journal_check"},
                max_failures=2,
            )
        ]
    )

    store.mark_failure("nightly", "first", now=now)
    store.mark_failure("nightly", "second", now=now)

    updated = store.load()[0]
    assert updated.enabled is False
    assert updated.failure_count == 2
    assert updated.disabled_reason == "max_failures_exceeded"


def test_scheduled_job_computes_common_cron_due_time():
    after = datetime(2026, 5, 15, 22, 59, tzinfo=timezone.utc)
    job = ScheduledJob(
        id="nightly",
        name="Nightly",
        schedule={"kind": "cron", "expr": "0 23 * * *"},
        payload={"kind": "presence_event", "event": "daily_journal_check"},
    )

    assert job.next_due_after(after) == datetime(
        2026,
        5,
        15,
        23,
        0,
        tzinfo=timezone.utc,
    )


def test_daemon_tick_runs_due_job_and_processes_delivery(tmp_path):
    paths = KairosPaths.from_root(tmp_path)
    store = ScheduleStore(paths)
    queue = DeliveryQueue(paths)
    now = datetime(2026, 5, 15, 12, tzinfo=timezone.utc)
    sent: list[tuple[str, str, str]] = []

    store.save(
        [
            ScheduledJob(
                id="journal",
                name="Journal",
                schedule={"kind": "interval", "seconds": 60},
                payload={"kind": "presence_event", "event": "daily_journal_check"},
                last_run_at=now - timedelta(minutes=2),
            )
        ]
    )

    def handler(event, current_time):
        assert event.event == "daily_journal_check"
        assert current_time == now
        return [OutboundMessage(channel="capture", to="local-user", text="journal?")]

    class CaptureChannel(CLIChannel):
        name = "capture"

        def send(self, to: str, text: str, **kwargs: object) -> bool:
            sent.append((self.name, to, text))
            return True

    runtime = DaemonRuntime(
        schedule_store=store,
        delivery_queue=queue,
        channel_manager=ChannelManager([CaptureChannel()]),
        presence_handler=handler,
    )

    result = runtime.tick(now=now)

    assert result.due_jobs == 1
    assert result.enqueued == 1
    assert result.delivery["delivered"] == 1
    assert sent == [("capture", "local-user", "journal?")]
    assert queue.load_pending() == []
