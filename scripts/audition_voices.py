from voice_agent.config import get_settings

VOICES = ["Puck", "Kore", "Charon", "Zephyr", "Aoede"]


def main() -> None:
    settings = get_settings()
    print("Gemini Live voice candidates for live-call audition:")
    for voice in VOICES:
        marker = " (current)" if voice == settings.gemini_live_voice else ""
        print(f"- {voice}{marker}")
    print("\nSet GEMINI_LIVE_VOICE to one of these values and run a short live test call.")


if __name__ == "__main__":
    main()
