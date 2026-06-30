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

    await ctx.connect()

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=settings.gemini_live_model,
            voice=settings.gemini_live_voice,
            temperature=0.4,
        )
    )
    agent = Agent(
        instructions=build_prompt(caller_phone),
        tools=AGENT_TOOLS,
    )
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )
    logger.info("Mandi voice agent started in room=%s", getattr(ctx.room, "name", "unknown"))
    session.generate_reply(
        instructions=(
            "Immediately greet the caller in natural Hindi/Hinglish. Say you are the "
            "MandiPlus AI assistant, ask how you can help, and keep it under two sentences."
        ),
        allow_interruptions=True,
    )


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
