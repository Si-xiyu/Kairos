from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.config import KairosPaths
from kairos.delivery import DeliveryQueue, DeliveryRunner, MAX_RETRIES
from kairos.presence import HeartbeatPolicy, HeartbeatState, should_run


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
