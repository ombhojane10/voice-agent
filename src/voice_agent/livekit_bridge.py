from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from .audio_bridge import resample_pcm16_mono
from .config import Settings
from .metrics import log_event

logger = logging.getLogger(__name__)


class LiveKitAudioBridge:
    """Raw LiveKit media bridge for Exotel AgentStream.

    The gateway publishes caller audio as one local track and subscribes to remote audio from the
    LiveKit agent. The agent itself is run by `voice_agent.agent`.
    """

    def __init__(self, settings: Settings, room_name: str, participant_identity: str) -> None:
        self.settings = settings
        self.room_name = room_name
        self.participant_identity = participant_identity
        self._room = None
        self._audio_source = None
        self._outbound: asyncio.Queue[bytes] = asyncio.Queue(maxsize=8)
        self._reader_tasks: set[asyncio.Task] = set()
        self._published_frames = 0
        self._agent_audio_frames = 0

    async def connect(self) -> None:
        try:
            from livekit import api, rtc
        except Exception as exc:  # pragma: no cover - depends on optional runtime deps.
            raise RuntimeError("LiveKit packages are not installed. Run `uv sync`.") from exc

        await self._ensure_room()

        token = (
            api.AccessToken(self.settings.livekit_api_key, self.settings.livekit_api_secret)
            .with_identity(self.participant_identity)
            .with_name("Exotel caller bridge")
            .with_grants(api.VideoGrants(room_join=True, room=self.room_name))
            .to_jwt()
        )

        self._room = rtc.Room()
        self._room.on("track_subscribed", self._on_track_subscribed)
        await self._room.connect(self.settings.livekit_url, token)

        self._audio_source = rtc.AudioSource(
            sample_rate=self.settings.livekit_sample_rate,
            num_channels=self.settings.channels,
        )
        track = rtc.LocalAudioTrack.create_audio_track("exotel-caller-audio", self._audio_source)
        await self._room.local_participant.publish_track(track)
        log_event(
            "livekit_bridge_connected",
            room=self.room_name,
            identity=self.participant_identity,
        )

    async def _ensure_room(self) -> None:
        from livekit import api

        client = api.LiveKitAPI(
            url=self.settings.livekit_url,
            api_key=self.settings.livekit_api_key,
            api_secret=self.settings.livekit_api_secret,
        )
        try:
            try:
                room = await client.room.create_room(
                    api.CreateRoomRequest(name=self.room_name, empty_timeout=300)
                )
                log_event("livekit_room_created", room=getattr(room, "name", self.room_name))
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    raise
                log_event("livekit_room_exists", room=self.room_name)
        finally:
            await client.aclose()

    async def dispatch_agent(self, metadata: str = "") -> None:
        if not self.settings.livekit_explicit_dispatch or not self.settings.livekit_agent_name:
            return

        from livekit import api

        client = api.LiveKitAPI(
            url=self.settings.livekit_url,
            api_key=self.settings.livekit_api_key,
            api_secret=self.settings.livekit_api_secret,
        )
        try:
            dispatch = await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=self.settings.livekit_agent_name,
                    room=self.room_name,
                    metadata=metadata,
                )
            )
            log_event(
                "livekit_agent_dispatched",
                room=self.room_name,
                agent_name=self.settings.livekit_agent_name,
                dispatch_id=getattr(dispatch, "id", ""),
                dispatch_state=str(getattr(dispatch, "state", "")),
            )
            await asyncio.sleep(0.5)
            dispatches = await client.agent_dispatch.list_dispatch(self.room_name)
            log_event(
                "livekit_agent_dispatch_checked",
                room=self.room_name,
                dispatch_count=len(dispatches),
                dispatches=[
                    {
                        "id": getattr(item, "id", ""),
                        "agent_name": getattr(item, "agent_name", ""),
                        "jobs": len(getattr(getattr(item, "state", None), "jobs", [])),
                    }
                    for item in dispatches
                ],
            )
        finally:
            await client.aclose()

    async def disconnect(self) -> None:
        for task in list(self._reader_tasks):
            task.cancel()
        await asyncio.gather(*self._reader_tasks, return_exceptions=True)
        self._reader_tasks.clear()
        if self._room is not None:
            await self._room.disconnect()
        log_event("livekit_bridge_disconnected", room=self.room_name)

    async def publish_caller_pcm(self, pcm_8k: bytes) -> None:
        if self._audio_source is None:
            return
        from livekit import rtc

        pcm_livekit = resample_pcm16_mono(
            pcm_8k,
            source_rate=self.settings.inbound_sample_rate,
            target_rate=self.settings.livekit_sample_rate,
        )
        frame = rtc.AudioFrame(
            data=pcm_livekit,
            sample_rate=self.settings.livekit_sample_rate,
            num_channels=self.settings.channels,
            samples_per_channel=len(pcm_livekit) // (2 * self.settings.channels),
        )
        await self._audio_source.capture_frame(frame)
        self._published_frames += 1
        if self._published_frames == 1 or self._published_frames % 100 == 0:
            log_event(
                "livekit_caller_audio_published",
                room=self.room_name,
                bytes=len(pcm_livekit),
                frames=self._published_frames,
            )

    async def outbound_pcm(self) -> AsyncIterator[bytes]:
        while True:
            pcm_livekit = await self._outbound.get()
            yield resample_pcm16_mono(
                pcm_livekit,
                source_rate=self.settings.livekit_sample_rate,
                target_rate=self.settings.inbound_sample_rate,
            )

    def _on_track_subscribed(self, track, publication, participant) -> None:
        from livekit import rtc

        identity = getattr(participant, "identity", "")
        log_event(
            "livekit_track_subscribed",
            room=self.room_name,
            participant=identity,
            kind=str(getattr(track, "kind", "")),
            publication_sid=getattr(publication, "sid", None),
        )
        if getattr(track, "kind", None) != rtc.TrackKind.KIND_AUDIO:
            return
        if identity == self.participant_identity:
            return
        task = asyncio.create_task(self._read_agent_audio(track, identity))
        self._reader_tasks.add(task)
        task.add_done_callback(self._reader_tasks.discard)

    async def _read_agent_audio(self, track, participant_identity: str) -> None:
        from livekit import rtc

        stream = rtc.AudioStream(track)
        log_event("agent_audio_subscribed", room=self.room_name, participant=participant_identity)
        async for event in stream:
            frame = event.frame
            data = bytes(frame.data)
            self._agent_audio_frames += 1
            if self._agent_audio_frames == 1 or self._agent_audio_frames % 100 == 0:
                log_event(
                    "agent_audio_frame_received",
                    room=self.room_name,
                    participant=participant_identity,
                    bytes=len(data),
                    frames=self._agent_audio_frames,
                )
            if self._outbound.full():
                try:
                    self._outbound.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await self._outbound.put(data)
