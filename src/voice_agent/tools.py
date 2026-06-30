from __future__ import annotations

import logging
from typing import Any

try:
    from livekit.agents import function_tool
except Exception:  # pragma: no cover - lets unit tests run without agent extras imported.
    def function_tool(func):  # type: ignore
        return func


logger = logging.getLogger(__name__)


@function_tool
async def lookup_customer_by_phone(phone: str) -> dict[str, Any]:
    """Look up a MandiPlus customer by phone number."""
    logger.info("lookup_customer_by_phone stub called for phone suffix=%s", phone[-4:])
    return {"found": False, "phone": phone, "message": "Customer lookup is not wired yet."}


@function_tool
async def create_followup(phone: str, language: str, intent: str, summary: str) -> dict[str, Any]:
    """Create a follow-up task for the operations team."""
    logger.info("create_followup stub called intent=%s language=%s", intent, language)
    return {
        "created": True,
        "phone": phone,
        "language": language,
        "intent": intent,
        "summary": summary,
    }


@function_tool
async def handoff_to_human(reason: str, summary: str) -> dict[str, Any]:
    """Request human handoff when the AI should not continue alone."""
    logger.info("handoff_to_human stub called reason=%s", reason)
    return {"handoff_requested": True, "reason": reason, "summary": summary}


@function_tool
async def record_call_outcome(outcome: str, summary: str, next_action: str) -> dict[str, Any]:
    """Record the call outcome for reporting and follow-up."""
    logger.info("record_call_outcome stub called outcome=%s", outcome)
    return {"recorded": True, "outcome": outcome, "summary": summary, "next_action": next_action}


AGENT_TOOLS = [
    lookup_customer_by_phone,
    create_followup,
    handoff_to_human,
    record_call_outcome,
]
