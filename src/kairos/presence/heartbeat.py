from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class HeartbeatPolicy:
    interval_seconds: int = 300
    active_hours: tuple[int, int] = (9, 23)
    daily_notification_budget: int = 3
    cooldown_seconds: int = 1800


@dataclass
class HeartbeatState:
    last_run_at: datetime | None = None
    running: bool = False
    notifications_today: int = 0
    last_notification_at: datetime | None = None


def should_run(
    now: datetime,
    policy: HeartbeatPolicy,
    state: HeartbeatState,
    user_active: bool = True,
    do_not_disturb: bool = False,
) -> tuple[bool, str]:
    now = _coerce_datetime(now)
    if do_not_disturb:
        return False, "do_not_disturb"
    if state.running:
        return False, "running"
    if user_active:
        return False, "user_active"
    if state.last_run_at is not None:
        elapsed = (now - _coerce_datetime(state.last_run_at)).total_seconds()
        if elapsed < policy.interval_seconds:
            return False, "interval"
    if not _within_active_hours(now, policy.active_hours):
        return False, "outside_active_hours"
    if state.notifications_today >= policy.daily_notification_budget:
        return False, "daily_budget_exhausted"
    if state.last_notification_at is not None:
        cooldown = (now - _coerce_datetime(state.last_notification_at)).total_seconds()
        if cooldown < policy.cooldown_seconds:
            return False, "cooldown"
    return True, "ok"


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _within_active_hours(now: datetime, active_hours: tuple[int, int]) -> bool:
    start, end = active_hours
    hour = now.hour
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end

