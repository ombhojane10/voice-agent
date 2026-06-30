import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("voice_agent.metrics")


def now_ms() -> int:
    return time.monotonic_ns() // 1_000_000


def log_event(name: str, **fields: Any) -> None:
    payload = {"event": name, "ts_ms": now_ms(), **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))


@contextmanager
def timed_span(name: str, **fields: Any):
    start = now_ms()
    try:
        yield
        log_event(name, duration_ms=now_ms() - start, status="ok", **fields)
    except Exception as exc:
        log_event(
            name,
            duration_ms=now_ms() - start,
            status="error",
            error=exc.__class__.__name__,
            **fields,
        )
        raise


@dataclass
class CallMetrics:
    call_id: str
    first_inbound_media_ms: int | None = None
    first_outbound_audio_ms: int | None = None
    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, key: str) -> None:
        self.counters[key] = self.counters.get(key, 0) + 1

    def mark_first_inbound(self) -> None:
        if self.first_inbound_media_ms is None:
            self.first_inbound_media_ms = now_ms()
            log_event("exotel_first_media_received", call_id=self.call_id)

    def mark_first_outbound(self) -> None:
        if self.first_outbound_audio_ms is None:
            self.first_outbound_audio_ms = now_ms()
            delta = None
            if self.first_inbound_media_ms is not None:
                delta = self.first_outbound_audio_ms - self.first_inbound_media_ms
            log_event("first_audio_sent_to_exotel", call_id=self.call_id, from_first_media_ms=delta)
