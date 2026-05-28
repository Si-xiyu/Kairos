from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any


TickFn = Callable[[], dict[str, Any]]


@dataclass
class DaemonStatus:
    running: bool = False
    interval_seconds: float = 60.0
    tick_count: int = 0
    last_tick_at: str | None = None
    last_result: dict[str, Any] | None = None
    last_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "tick_count": self.tick_count,
            "last_tick_at": self.last_tick_at,
            "last_result": self.last_result,
            "last_error": self.last_error,
        }


class BackgroundDaemon:
    def __init__(self, tick_fn: TickFn, interval_seconds: float = 60.0) -> None:
        self.tick_fn = tick_fn
        self.status = DaemonStatus(interval_seconds=interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self.status.running = True
                return self.status.to_json()
            self._stop.clear()
            self.status.running = True
            self._thread = threading.Thread(target=self._run, name="kairos-daemon", daemon=True)
            self._thread.start()
            return self.status.to_json()

    def stop(self, timeout: float = 5.0) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        with self._lock:
            self.status.running = bool(thread is not None and thread.is_alive())
            if not self.status.running:
                self._thread = None
            return self.status.to_json()

    def tick_once(self) -> dict[str, Any]:
        return self._tick()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and not self._thread.is_alive():
                self.status.running = False
                self._thread = None
            return self.status.to_json()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(self.status.interval_seconds)
        with self._lock:
            self.status.running = False

    def _tick(self) -> dict[str, Any]:
        try:
            result = self.tick_fn()
            error = None
        except Exception as exc:
            result = None
            error = str(exc)
        with self._lock:
            self.status.tick_count += 1
            self.status.last_tick_at = datetime.now(timezone.utc).isoformat()
            self.status.last_result = result
            self.status.last_error = error
            return self.status.to_json()
