from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any

import httpx

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


def normalize_india_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        return digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    raise ValueError("Phone must be a 10-digit Indian number or 91-prefixed 12-digit number.")


def build_exotel_call_payload(settings: Settings, to_phone: str) -> dict[str, Any]:
    if not settings.agentstream_flow_url:
        raise ValueError(
            "EXOTEL_AGENTSTREAM_APP_ID or EXOTEL_AGENTSTREAM_FLOW_URL is required. "
            "Outbound AgentStream calls must connect the callee to an Exotel Call Flow "
            "that contains the Voicebot Applet."
        )
    return {
        "From": normalize_india_phone(to_phone),
        "CallerId": settings.outbound_ai_caller_id,
        "Url": settings.agentstream_flow_url,
        "CallType": "trans",
        "Record": "true",
        "StatusCallback": settings.exotel_status_callback_url or "",
    }


async def make_call(to_phone: str, dry_run: bool = False) -> dict[str, Any]:
    settings = get_settings()
    required = [
        settings.exotel_account_sid,
        settings.exotel_api_key,
        settings.exotel_api_token,
        settings.exotel_caller_id,
    ]
    if not all(required):
        raise RuntimeError("Exotel credentials and EXOTEL_CALLER_ID are required.")

    payload = build_exotel_call_payload(settings, to_phone)
    if dry_run:
        return {"dry_run": True, "url": settings.exotel_calls_url, "payload": payload}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            settings.exotel_calls_url,
            data={key: value for key, value in payload.items() if value},
            auth=(settings.exotel_api_key, settings.exotel_api_token),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:1000].replace("\n", " ")
            raise RuntimeError(
                f"Exotel call failed status={response.status_code} detail={detail}"
            ) from exc
        try:
            return response.json()
        except ValueError:
            return {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "text": response.text[:1000],
            }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Place an Exotel test call.")
    parser.add_argument(
        "--to",
        default=os.getenv("TEST_CALL_TO", ""),
        help="10-digit or 91-prefixed phone",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request payload without calling",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    if not args.to:
        raise SystemExit("Provide --to or TEST_CALL_TO in local .env")
    result = asyncio.run(make_call(args.to, dry_run=args.dry_run))
    print(result)


if __name__ == "__main__":
    main()
