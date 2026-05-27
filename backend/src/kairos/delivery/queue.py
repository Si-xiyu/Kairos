from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from kairos.config import KairosPaths


BACKOFF_SECONDS = (5, 25, 120, 600)
MAX_RETRIES = 5


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    parsed = datetime.fromisoformat(value)
    return _coerce_datetime(parsed)


@dataclass(frozen=True)
class QueuedDelivery:
    id: str
    channel: str
    to: str
    text: str
    enqueued_at: datetime
    next_retry_at: datetime
    retry_count: int = 0
    last_error: str | None = None
    expires_at: datetime | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["enqueued_at"] = _datetime_to_json(self.enqueued_at)
        data["next_retry_at"] = _datetime_to_json(self.next_retry_at)
        data["expires_at"] = _datetime_to_json(self.expires_at)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "QueuedDelivery":
        return cls(
            id=str(data["id"]),
            channel=str(data["channel"]),
            to=str(data["to"]),
            text=str(data["text"]),
            enqueued_at=_datetime_from_json(data["enqueued_at"]) or utc_now(),
            next_retry_at=_datetime_from_json(data["next_retry_at"]) or utc_now(),
            retry_count=int(data.get("retry_count", 0)),
            last_error=data.get("last_error"),
            expires_at=_datetime_from_json(data.get("expires_at")),
        )

    def with_failure(self, error: str, now: datetime) -> "QueuedDelivery":
        retry_count = self.retry_count + 1
        backoff = BACKOFF_SECONDS[min(retry_count - 1, len(BACKOFF_SECONDS) - 1)]
        return QueuedDelivery(
            id=self.id,
            channel=self.channel,
            to=self.to,
            text=self.text,
            enqueued_at=self.enqueued_at,
            next_retry_at=now + timedelta(seconds=backoff),
            retry_count=retry_count,
            last_error=error,
            expires_at=self.expires_at,
        )


class DeliveryQueue:
    def __init__(self, paths: KairosPaths) -> None:
        self.pending_dir = paths.delivery_pending
        self.failed_dir = paths.delivery_failed
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(
        self,
        channel: str,
        to: str,
        text: str,
        expires_at: datetime | None = None,
        now: datetime | None = None,
    ) -> str:
        now = _coerce_datetime(now) or utc_now()
        delivery = QueuedDelivery(
            id=uuid4().hex,
            channel=channel,
            to=to,
            text=text,
            enqueued_at=now,
            next_retry_at=now,
            expires_at=_coerce_datetime(expires_at),
        )
        self._write_atomic(self._pending_path(delivery.id), delivery)
        return delivery.id

    def load_pending(self, now: datetime | None = None) -> list[QueuedDelivery]:
        deliveries: list[QueuedDelivery] = []
        for path in self.pending_dir.glob("*.json"):
            if path.name.startswith(".tmp."):
                continue
            deliveries.append(self._read(path))
        return sorted(deliveries, key=lambda delivery: delivery.enqueued_at)

    def ack(self, delivery_id: str) -> None:
        path = self._pending_path(delivery_id)
        if path.exists():
            path.unlink()

    def fail(
        self,
        delivery_id: str,
        error: str,
        now: datetime | None = None,
    ) -> None:
        now = _coerce_datetime(now) or utc_now()
        path = self._pending_path(delivery_id)
        if not path.exists():
            return

        failed_delivery = self._read(path).with_failure(error, now)
        if failed_delivery.retry_count >= MAX_RETRIES:
            self._write_atomic(self._failed_path(delivery_id), failed_delivery)
            path.unlink()
            return

        self._write_atomic(path, failed_delivery)

    def expire(self, delivery_id: str, now: datetime | None = None) -> None:
        now = _coerce_datetime(now) or utc_now()
        path = self._pending_path(delivery_id)
        if not path.exists():
            return
        delivery = self._read(path)
        expired = QueuedDelivery(
            id=delivery.id,
            channel=delivery.channel,
            to=delivery.to,
            text=delivery.text,
            enqueued_at=delivery.enqueued_at,
            next_retry_at=now,
            retry_count=delivery.retry_count,
            last_error="expired",
            expires_at=delivery.expires_at,
        )
        self._write_atomic(self._failed_path(delivery_id), expired)
        path.unlink()

    def _pending_path(self, delivery_id: str) -> Path:
        return self.pending_dir / f"{delivery_id}.json"

    def _failed_path(self, delivery_id: str) -> Path:
        return self.failed_dir / f"{delivery_id}.json"

    def _read(self, path: Path) -> QueuedDelivery:
        return QueuedDelivery.from_json(json.loads(path.read_text(encoding="utf-8")))

    def _write_atomic(self, target: Path, delivery: QueuedDelivery) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".tmp.{target.stem}.{uuid4().hex}.json"
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(delivery.to_json(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp, target)
