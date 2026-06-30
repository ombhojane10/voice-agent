from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "voice-agent" / ".env"
EXAMPLE = ROOT / "voice-agent" / ".env.example"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    mandiplus = parse_env(ROOT / "mandiplus" / ".env")
    bot = parse_env(ROOT / "bot" / ".env")
    frontend = parse_env(ROOT / "frontend" / ".env.local")
    app = parse_env(ROOT / "app" / ".env")
    existing = parse_env(TARGET) if TARGET.exists() else parse_env(EXAMPLE)

    mapped = {
        "GOOGLE_API_KEY": mandiplus.get("GEMINI_API_KEY") or bot.get("GEMINI_API_KEY"),
        "EXOTEL_ACCOUNT_SID": mandiplus.get("EXOTEL_ACCOUNT_SID"),
        "EXOTEL_API_KEY": mandiplus.get("EXOTEL_API_USERNAME_APIKEY"),
        "EXOTEL_API_TOKEN": mandiplus.get("EXOTEL_API_TOKEN"),
        "EXOTEL_SUBDOMAIN": mandiplus.get("EXOTEL_SUBDOMAIN"),
        "EXOTEL_CALLER_ID": mandiplus.get("EXOTEL_EXOPHONE"),
        "PUBLIC_BASE_URL": (
            bot.get("PUBLIC_APP_URL")
            or frontend.get("NEXT_PUBLIC_API_BASE_URL")
            or app.get("EXPO_PUBLIC_MANDI_API_BASE_URL")
        ),
    }

    placeholders = {
        "",
        "replace-me",
        "https://your-tunnel.example.com",
        "wss://your-livekit-project.livekit.cloud",
    }
    for key, value in mapped.items():
        if value and existing.get(key, "") in placeholders:
            existing[key] = value

    for key, value in parse_env(EXAMPLE).items():
        existing.setdefault(key, value)

    sections = {
        "Runtime": ["ENV", "LOG_LEVEL", "PUBLIC_BASE_URL"],
        "LiveKit": [
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
            "LIVEKIT_AGENT_NAME",
            "LIVEKIT_EXPLICIT_DISPATCH",
            "LIVEKIT_ROOM_PREFIX",
        ],
        "Gemini Live": ["GOOGLE_API_KEY", "GEMINI_LIVE_MODEL", "GEMINI_LIVE_VOICE"],
        "Exotel": [
            "EXOTEL_ACCOUNT_SID",
            "EXOTEL_API_KEY",
            "EXOTEL_API_TOKEN",
            "EXOTEL_SUBDOMAIN",
            "EXOTEL_CALLER_ID",
            "EXOTEL_AI_CALLER_ID",
            "EXOTEL_AGENTSTREAM_APP_ID",
            "EXOTEL_AGENTSTREAM_FLOW_URL",
            "EXOTEL_STATUS_CALLBACK_URL",
        ],
        "Local-only manual testing. Do not commit real customer numbers.": ["TEST_CALL_TO"],
    }

    lines: list[str] = []
    seen: set[str] = set()
    for section, keys in sections.items():
        lines.append(f"# {section}")
        for key in keys:
            seen.add(key)
            lines.append(f"{key}={existing.get(key, '')}")
        lines.append("")
    for key, value in existing.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    TARGET.write_text("\n".join(lines).rstrip() + "\n")
    filled = [key for key, value in mapped.items() if value]
    missing_livekit = [
        key
        for key in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
        if existing.get(key, "") in placeholders
    ]
    print("updated .env")
    print("filled_keys=" + ",".join(filled))
    print("missing_livekit=" + ",".join(missing_livekit))


if __name__ == "__main__":
    main()
