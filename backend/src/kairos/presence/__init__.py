"""Heartbeat and cron driven presence subsystem."""

from .events import PresenceEvent
from .heartbeat import HeartbeatPolicy, HeartbeatState, should_run
from .heartbeat_runner import HEARTBEAT_OK, PRESENCE_SESSION_ID, HeartbeatRun, HeartbeatRunner
from .daemon import DaemonRuntime, DaemonTickResult
from .daemon_service import BackgroundDaemon, DaemonStatus
from .schedule import (
    ScheduleKind,
    ScheduleStore,
    ScheduledJob,
    compute_next_run,
    due_jobs,
    mark_failure,
    mark_success,
)

__all__ = [
    "DaemonRuntime",
    "BackgroundDaemon",
    "DaemonTickResult",
    "DaemonStatus",
    "HeartbeatPolicy",
    "HeartbeatRun",
    "HeartbeatRunner",
    "HeartbeatState",
    "HEARTBEAT_OK",
    "PRESENCE_SESSION_ID",
    "PresenceEvent",
    "ScheduleKind",
    "ScheduleStore",
    "ScheduledJob",
    "compute_next_run",
    "due_jobs",
    "mark_failure",
    "mark_success",
    "should_run",
]
