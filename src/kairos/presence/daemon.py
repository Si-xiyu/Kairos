from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from kairos.channels import ChannelManager
from kairos.delivery import DeliveryQueue, DeliveryRunner
from kairos.messages import OutboundMessage

from .events import PresenceEvent
from .schedule import ScheduleStore


PresenceHandler = Callable[[PresenceEvent, datetime], Iterable[OutboundMessage]]


@dataclass(frozen=True)
class DaemonTickResult:
    due_jobs: int = 0
    enqueued: int = 0
    failed_jobs: int = 0
    delivery: dict[str, Any] = field(default_factory=dict)


class DaemonRuntime:
    def __init__(
        self,
        schedule_store: ScheduleStore,
        delivery_queue: DeliveryQueue,
        channel_manager: ChannelManager,
        presence_handler: PresenceHandler | None = None,
    ) -> None:
        self.schedule_store = schedule_store
        self.delivery_queue = delivery_queue
        self.channel_manager = channel_manager
        self.presence_handler = presence_handler or self._default_presence_handler

    def tick(self, now: datetime | None = None) -> DaemonTickResult:
        now = _coerce_datetime(now) or datetime.now(timezone.utc)
        due_jobs = self.schedule_store.due(now)
        enqueued = 0
        failed_jobs = 0

        for job in due_jobs:
            try:
                event = PresenceEvent.from_payload(job.payload)
                for message in self.presence_handler(event, now):
                    self.delivery_queue.enqueue(
                        channel=message.channel,
                        to=message.to,
                        text=message.text,
                        now=now,
                    )
                    enqueued += 1
                self.schedule_store.mark_success(job.id, now=now)
            except Exception as exc:
                failed_jobs += 1
                self.schedule_store.mark_failure(job.id, str(exc), now=now)

        delivery = DeliveryRunner(self.delivery_queue, self.channel_manager.send).process_once(
            now=now
        )
        return DaemonTickResult(
            due_jobs=len(due_jobs),
            enqueued=enqueued,
            failed_jobs=failed_jobs,
            delivery=delivery,
        )

    @staticmethod
    def _default_presence_handler(
        event: PresenceEvent,
        now: datetime,
    ) -> Iterable[OutboundMessage]:
        return []


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
