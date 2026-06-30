from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

ExotelEventType = Literal["connected", "start", "media", "dtmf", "mark", "clear", "stop", "unknown"]


@dataclass(frozen=True)
class ExotelEvent:
    event: ExotelEventType
    raw: dict[str, Any]
    stream_sid: str | None = None
    call_sid: str | None = None
    sequence_number: str | int | None = None
    payload: bytes = b""
    dtmf_digit: str | None = None
    mark_name: str | None = None

    @property
    def is_media(self) -> bool:
        return self.event == "media" and bool(self.payload)


def parse_exotel_event(message: dict[str, Any]) -> ExotelEvent:
    event_name = str(message.get("event") or message.get("Event") or "unknown").lower()
    if event_name not in {"connected", "start", "media", "dtmf", "mark", "clear", "stop"}:
        event_name = "unknown"

    start = message.get("start") or {}
    media = message.get("media") or {}
    dtmf = message.get("dtmf") or {}
    mark = message.get("mark") or {}

    stream_sid = (
        message.get("stream_sid")
        or message.get("streamSid")
        or message.get("StreamSid")
        or start.get("stream_sid")
        or start.get("streamSid")
    )
    call_sid = (
        message.get("call_sid")
        or message.get("callSid")
        or message.get("CallSid")
        or start.get("call_sid")
        or start.get("callSid")
    )

    payload = b""
    if event_name == "media":
        encoded_payload = media.get("payload") or message.get("payload") or ""
        if encoded_payload:
            payload = base64.b64decode(encoded_payload)

    return ExotelEvent(
        event=event_name,  # type: ignore[arg-type]
        raw=message,
        stream_sid=stream_sid,
        call_sid=call_sid,
        sequence_number=message.get("sequenceNumber") or message.get("sequence_number"),
        payload=payload,
        dtmf_digit=dtmf.get("digit") or message.get("digit"),
        mark_name=mark.get("name") or message.get("name"),
    )


def build_media_event(
    stream_sid: str,
    pcm_payload: bytes,
    *,
    chunk: int | None = None,
    timestamp_ms: int | None = None,
    sequence_number: int | None = None,
) -> dict[str, Any]:
    media: dict[str, Any] = {"payload": base64.b64encode(pcm_payload).decode("ascii")}
    if chunk is not None:
        media["chunk"] = str(chunk)
    if timestamp_ms is not None:
        media["timestamp"] = str(timestamp_ms)
    event: dict[str, Any] = {
        "event": "media",
        "stream_sid": stream_sid,
        "streamSid": stream_sid,
        "media": media,
    }
    if sequence_number is not None:
        event["sequenceNumber"] = str(sequence_number)
    return {
        **event,
    }


def build_clear_event(stream_sid: str) -> dict[str, Any]:
    return {"event": "clear", "stream_sid": stream_sid}


def build_mark_event(stream_sid: str, name: str) -> dict[str, Any]:
    return {"event": "mark", "stream_sid": stream_sid, "mark": {"name": name}}
