from __future__ import annotations

import logging
import os

from .config import get_settings
from .prompts import build_prompt
from .tools import AGENT_TOOLS

logger = logging.getLogger(__name__)


class MandiVoiceAgent:
    """Thin wrapper so the prompt/tools are testable outside LiveKit worker startup."""

    def __init__(self, caller_phone: str | None = None) -> None:
        self.caller_phone = caller_phone

    @property
    def instructions(self) -> str:
        return build_prompt(self.caller_phone)


async def entrypoint(ctx):
    from livekit.agents import Agent, AgentSession, RoomInputOptions
    from livekit.plugins import google

    settings = get_settings()
    caller_phone = None
    if getattr(ctx, "job", None) and getattr(ctx.job, "metadata", None):
        caller_phone = ctx.job.metadata

    room_name = getattr(ctx.room, "name", "unknown")
    instructions = build_prompt(caller_phone)
    logger.info(
        "Mandi voice agent entrypoint starting room=%s model=%s voice=%s",
        room_name,
        settings.gemini_live_model,
        settings.gemini_live_voice,
    )

    await ctx.connect()
    logger.info("Mandi voice agent connected to room=%s", room_name)

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            instructions=instructions,
            model=settings.gemini_live_model,
            voice=settings.gemini_live_voice,
            temperature=0.4,
            language="hi-IN",
        )
    )
    agent = Agent(
        instructions=instructions,
        tools=AGENT_TOOLS,
    )
    logger.info("Mandi voice agent session starting room=%s", room_name)
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )
    logger.info("Mandi voice agent session started room=%s", room_name)
    handle = session.generate_reply(
        instructions=(
            "Immediately greet the caller in natural Hindi/Hinglish. Say you are the "
            "MandiPlus AI assistant, ask how you can help, and keep it under two sentences."
        ),
        allow_interruptions=True,
    )
    logger.info("Mandi voice agent greeting queued room=%s handle=%s", room_name, handle)


def main() -> None:
    from livekit import agents
    from livekit.agents import cli

    settings = get_settings()
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=settings.livekit_agent_name,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )


if __name__ == "__main__":
    main()
