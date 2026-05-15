from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .queue import DeliveryQueue, _coerce_datetime, utc_now


DeliverFn = Callable[[str, str, str], bool]


class DeliveryRunner:
    def __init__(self, queue: DeliveryQueue, deliver_fn: DeliverFn) -> None:
        self.queue = queue
        self.deliver_fn = deliver_fn

    def process_once(self, now: datetime | None = None) -> dict[str, Any]:
        now = _coerce_datetime(now) or utc_now()
        stats = {
            "pending": 0,
            "processed": 0,
            "delivered": 0,
            "retried": 0,
            "failed": 0,
            "expired": 0,
            "skipped": 0,
        }

        for delivery in self.queue.load_pending(now=now):
            stats["pending"] += 1
            if delivery.expires_at is not None and delivery.expires_at <= now:
                self.queue.expire(delivery.id, now=now)
                stats["expired"] += 1
                continue
            if delivery.next_retry_at > now:
                stats["skipped"] += 1
                continue

            stats["processed"] += 1
            try:
                delivered = self.deliver_fn(delivery.channel, delivery.to, delivery.text)
            except Exception as exc:  # pragma: no cover - exact channel errors vary.
                self.queue.fail(delivery.id, str(exc), now=now)
                stats["failed"] += 1
                continue

            if delivered:
                self.queue.ack(delivery.id)
                stats["delivered"] += 1
            else:
                self.queue.fail(delivery.id, "deliver_fn returned false", now=now)
                stats["retried"] += 1

        return stats

