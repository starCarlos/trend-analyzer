from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Callable

from app.models import utcnow
from app.schemas import CollectTriggerResponse


@dataclass(slots=True)
class SchedulerSnapshot:
    enabled: bool
    running: bool
    interval_seconds: int
    initial_delay_seconds: int
    period: str
    run_backfill_now: bool
    iteration_count: int
    last_started_at: str | None
    last_finished_at: str | None
    last_status: str
    last_error: str | None
    last_triggered_count: int


class CollectionScheduler:
    def __init__(
        self,
        *,
        job_runner: Callable[..., CollectTriggerResponse],
        enabled: bool,
        interval_seconds: int,
        initial_delay_seconds: int,
        period: str,
        run_backfill_now: bool,
    ) -> None:
        self.job_runner = job_runner
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.initial_delay_seconds = initial_delay_seconds
        self.period = period
        self.run_backfill_now = run_backfill_now

        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._iteration_count = 0
        self._last_started_at = None
        self._last_finished_at = None
        self._last_status = "idle"
        self._last_error = None
        self._last_triggered_count = 0

    def start(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(target=self._run_loop, name="trendscope-collector", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def run_once(self) -> CollectTriggerResponse:
        started_at = utcnow()
        with self._lock:
            self._iteration_count += 1
            self._last_started_at = started_at
            self._last_status = "running"
            self._last_error = None

        try:
            response = self.job_runner(
                query=None,
                tracked_only=True,
                period=self.period,
                run_backfill_now=self.run_backfill_now,
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            finished_at = utcnow()
            with self._lock:
                self._last_finished_at = finished_at
                self._last_status = "failed"
                self._last_error = str(exc)
                self._last_triggered_count = 0
            raise

        finished_at = utcnow()
        with self._lock:
            self._last_finished_at = finished_at
            self._last_status = "success"
            self._last_error = None
            self._last_triggered_count = response.triggered_count

        return response

    def snapshot(self) -> SchedulerSnapshot:
        with self._lock:
            return SchedulerSnapshot(
                enabled=self.enabled,
                running=bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set()),
                interval_seconds=self.interval_seconds,
                initial_delay_seconds=self.initial_delay_seconds,
                period=self.period,
                run_backfill_now=self.run_backfill_now,
                iteration_count=self._iteration_count,
                last_started_at=self._last_started_at.isoformat() if self._last_started_at else None,
                last_finished_at=self._last_finished_at.isoformat() if self._last_finished_at else None,
                last_status=self._last_status,
                last_error=self._last_error,
                last_triggered_count=self._last_triggered_count,
            )

    def _run_loop(self) -> None:
        if self.initial_delay_seconds > 0 and self._stop_event.wait(self.initial_delay_seconds):
            return

        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                pass

            if self._stop_event.wait(self.interval_seconds):
                return
