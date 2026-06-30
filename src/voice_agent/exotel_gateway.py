from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .audio_bridge import OutboundAudioBuffer, pcm16_duration_ms, pcm16_rms
from .config import Settings, get_settings
from .exotel_events import build_clear_event, build_media_event, parse_exotel_event
from .livekit_bridge import LiveKitAudioBridge
from .metrics import CallMetrics, log_event, now_ms

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="MandiPlus Voice Agent Gateway", version="0.1.0")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok"}

    @app.head("/")
    async def root_head() -> None:
        return None

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/exotel/agentstream-url")
    async def agentstream_url() -> dict[str, str]:
        return {"url": settings.agentstream_ws_url}

    @app.websocket("/ws/exotel/agentstream")
    async def exotel_agentstream(websocket: WebSocket) -> None:
        await websocket.accept()

        call_id = f"pending-{uuid4().hex[:8]}"
        room_name = f"{settings.livekit_room_prefix}-{uuid4().hex[:10]}"
        bridge = LiveKitAudioBridge(
            settings=settings,
            room_name=room_name,
            participant_identity=f"exotel-{uuid4().hex[:8]}",
        )
        outbound_buffer = OutboundAudioBuffer(max_frames=1)
        metrics = CallMetrics(call_id=call_id)
        stream_sid: str | None = None
        sender_task: asyncio.Task | None = None
        agent_dispatched = False
        outbound_remainder = bytearray()
        outbound_chunk = 1
        outbound_timestamp_ms = 0
        outbound_sequence_number = 1
        media_events_seen = 0
        outbound_frames_sent = 0
        last_outbound_sent_ms: int | None = None
        speech_frames_during_agent = 0
        interruption_clear_sent = False

        async def send_agent_audio() -> None:
            nonlocal interruption_clear_sent
            nonlocal last_outbound_sent_ms
            nonlocal outbound_chunk
            nonlocal outbound_frames_sent
            nonlocal outbound_sequence_number
            nonlocal outbound_timestamp_ms
            if stream_sid is None:
                return
            try:
                async for pcm_8k in bridge.outbound_pcm():
                    outbound_remainder.extend(pcm_8k)
                    while len(outbound_remainder) >= settings.exotel_outbound_frame_bytes:
                        frame = bytes(outbound_remainder[: settings.exotel_outbound_frame_bytes])
                        del outbound_remainder[: settings.exotel_outbound_frame_bytes]
                        outbound_buffer.push(frame)
                        buffered_frame = outbound_buffer.pop()
                        if not buffered_frame:
                            continue
                        metrics.mark_first_outbound()
                        await websocket.send_json(
                            build_media_event(
                                stream_sid,
                                buffered_frame,
                                chunk=outbound_chunk,
                                timestamp_ms=outbound_timestamp_ms,
                                sequence_number=outbound_sequence_number,
                            )
                        )
                        outbound_frames_sent += 1
                        last_outbound_sent_ms = now_ms()
                        if outbound_frames_sent == 1 or outbound_frames_sent % 50 == 0:
                            log_event(
                                "exotel_agent_audio_sent",
                                call_id=call_id,
                                bytes=len(buffered_frame),
                                chunk=outbound_chunk,
                                frame_duration_ms=pcm16_duration_ms(
                                    buffered_frame,
                                    sample_rate=settings.inbound_sample_rate,
                                    channels=settings.channels,
                                ),
                                stream_sid=stream_sid,
                            )
                        outbound_chunk += 1
                        outbound_sequence_number += 1
                        outbound_timestamp_ms += pcm16_duration_ms(
                            buffered_frame,
                            sample_rate=settings.inbound_sample_rate,
                            channels=settings.channels,
                        )
            except asyncio.CancelledError:
                raise
            except WebSocketDisconnect:
                log_event("exotel_agent_audio_sender_disconnected", call_id=call_id)
            except Exception as exc:
                logger.exception("Agent audio sender failed: %s", exc)
                log_event(
                    "exotel_agent_audio_sender_failed",
                    call_id=call_id,
                    error=exc.__class__.__name__,
                )

        try:
            await bridge.connect()
            log_event("exotel_ws_connected", room=room_name)

            while True:
                message = await websocket.receive_json()
                event = parse_exotel_event(message)

                if event.call_sid and call_id.startswith("pending-"):
                    call_id = event.call_sid
                    metrics.call_id = call_id
                if event.stream_sid and stream_sid is None:
                    stream_sid = event.stream_sid
                    if sender_task is None:
                        sender_task = asyncio.create_task(send_agent_audio())
                    if not agent_dispatched:
                        try:
                            await bridge.dispatch_agent(metadata=call_id)
                        except Exception as exc:
                            logger.exception("LiveKit agent dispatch failed: %s", exc)
                            log_event(
                                "livekit_agent_dispatch_failed",
                                room=room_name,
                                call_id=call_id,
                                error=exc.__class__.__name__,
                            )
                        agent_dispatched = True

                metrics.increment(event.event)
                if event.event != "media":
                    log_event(
                        "exotel_event_received",
                        call_id=call_id,
                        room=room_name,
                        event=event.event,
                        stream_sid=event.stream_sid,
                    )

                if event.is_media:
                    media_events_seen += 1
                    metrics.mark_first_inbound()
                    await bridge.publish_caller_pcm(event.payload)
                    if media_events_seen == 1 or media_events_seen % 100 == 0:
                        log_event(
                            "exotel_media_forwarded",
                            call_id=call_id,
                            bytes=len(event.payload),
                            frames=media_events_seen,
                        )

                    rms = pcm16_rms(event.payload)
                    agent_audio_recent = (
                        last_outbound_sent_ms is not None
                        and now_ms() - last_outbound_sent_ms
                        <= settings.exotel_barge_in_window_ms
                    )
                    is_speech_during_agent = (
                        agent_audio_recent and rms >= settings.exotel_barge_in_rms_threshold
                    )
                    if is_speech_during_agent:
                        speech_frames_during_agent += 1
                    else:
                        speech_frames_during_agent = 0
                        interruption_clear_sent = False

                    if (
                        stream_sid
                        and agent_audio_recent
                        and not interruption_clear_sent
                        and speech_frames_during_agent >= settings.exotel_barge_in_min_frames
                    ):
                        cleared = outbound_buffer.clear()
                        remainder_bytes = len(outbound_remainder)
                        outbound_remainder.clear()
                        await websocket.send_json(build_clear_event(stream_sid))
                        interruption_clear_sent = True
                        log_event(
                            "caller_speech_barge_in_detected",
                            call_id=call_id,
                            rms=round(rms, 2),
                            cleared_frames=cleared,
                            cleared_remainder_bytes=remainder_bytes,
                        )
                elif event.event == "dtmf":
                    cleared = outbound_buffer.clear()
                    remainder_bytes = len(outbound_remainder)
                    outbound_remainder.clear()
                    if stream_sid:
                        await websocket.send_json(build_clear_event(stream_sid))
                    log_event(
                        "caller_interruption_detected",
                        call_id=call_id,
                        digit=event.dtmf_digit,
                        cleared_frames=cleared,
                        cleared_remainder_bytes=remainder_bytes,
                    )
                elif event.event == "clear":
                    cleared = outbound_buffer.clear()
                    remainder_bytes = len(outbound_remainder)
                    outbound_remainder.clear()
                    log_event(
                        "outbound_audio_cleared",
                        call_id=call_id,
                        cleared_frames=cleared,
                        cleared_remainder_bytes=remainder_bytes,
                    )
                elif event.event == "stop":
                    break

        except WebSocketDisconnect:
            log_event("exotel_ws_disconnected", call_id=call_id)
        except RuntimeError as exc:
            if "WebSocket is not connected" not in str(exc):
                raise
            log_event("exotel_ws_disconnected", call_id=call_id)
        finally:
            if sender_task is not None:
                sender_task.cancel()
                await asyncio.gather(sender_task, return_exceptions=True)
            await bridge.disconnect()
            log_event("call_finished", call_id=call_id, counters=metrics.counters)

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    import uvicorn

    uvicorn.run(
        "voice_agent.exotel_gateway:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    main()
