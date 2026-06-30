# MandiPlus Voice Agent

Realtime Hindi/Hinglish calling agent for Mandi workflows using Exotel AgentStream,
LiveKit Agents, and Gemini Live native audio.

## Why this shape

The v1 path optimizes for latency and interruption:

- Exotel AgentStream handles the India PSTN leg.
- LiveKit carries realtime media and agent orchestration when we need rooms, dispatch, monitoring,
  human handoff, or future SIP/browser participants.
- Gemini Live native audio avoids a separate STT -> LLM -> TTS cascade.
- The agent prompt keeps turns short, asks one question at a time, and mirrors the caller's language.

Important: LiveKit is not strictly required for an Exotel-only calling agent. For the absolute
lowest-latency phone-only path, the next architecture to test is a direct Exotel AgentStream <->
Gemini Live bridge. Keep LiveKit when we want production orchestration: agent worker lifecycle,
room observability, recordings, handoff, multi-participant calls, browser testing, and future SIP.

Gemini Live voices are named global voices, not explicit `hi-IN` voices. This repo defaults to
`Puck` for low-latency native audio and includes a voice audition helper. If native voice quality is
not Indian enough, the documented v2 path is a cascaded Google Cloud TTS / Chirp Indian-locale voice
connector.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

Fill `.env` with LiveKit, Google, and Exotel credentials. Keep real test numbers only in local
`.env`.

To copy reusable values from the sibling Mandi repos without printing secrets:

```bash
uv run python scripts/sync_env_from_mandi.py
```

This fills Gemini and Exotel values from `../mandiplus/.env` and `../bot/.env` when present. LiveKit
credentials are not present in the current sibling repos, so they still need to be added manually if
you use the LiveKit path.

## Run locally

Start the Exotel AgentStream gateway:

```bash
uv run voice-agent-api
```

Start the LiveKit worker in another terminal:

```bash
uv run voice-agent-worker dev
```

For Render, deploy two services:

- Web service: `uv run voice-agent-api`
- Background worker: `uv run voice-agent-worker start`

Set `PUBLIC_BASE_URL` to the Render web service URL, for example:

```env
PUBLIC_BASE_URL=https://voice-agent-api.onrender.com
```

Exotel should point to:

```text
wss://voice-agent-api.onrender.com/ws/exotel/agentstream
```

Expose the API with a tunnel and configure Exotel AgentStream to connect to:

```text
wss://YOUR_PUBLIC_BASE_URL/ws/exotel/agentstream
```

For outbound calls, create an Exotel Call Flow that contains a Voicebot Applet. In that applet, use
either the static WSS URL above or the dynamic resolver:

```text
https://YOUR_PUBLIC_BASE_URL/exotel/agentstream-url
```

Then set `EXOTEL_AGENTSTREAM_APP_ID` to the flow/app id. Exotel outbound voicebot calls must use the
flow URL (`http://my.exotel.com/{sid}/exoml/start_voice/{app_id}`); using the existing
`https://api.mandiplus.com/exotel/voice` human-dial flow will make the caller hear a ringing tone
while Exotel tries to dial a human agent.

For production isolation, set `EXOTEL_AI_CALLER_ID` to a dedicated ExoPhone for AI outbound calls.
If it is blank, the app falls back to `EXOTEL_CALLER_ID`.

## Manual test call

Only run this after confirming caller ID, consent, and Exotel billing:

```bash
uv run python scripts/make_test_call.py --to "$TEST_CALL_TO"
```

## Voice audition

```bash
uv run python scripts/audition_voices.py
```

This prints the native Gemini Live voice candidates to test in live calls:
`Puck`, `Kore`, `Charon`, `Zephyr`, and `Aoede`.

## Test

```bash
uv run pytest
uv run ruff check .
```

## Latency targets

- p50 first agent audio after caller turn end: under 1.2s
- p95 first agent audio after caller turn end: under 2.5s
- barge-in audio cutoff: under 250ms

The gateway emits structured timing logs for Exotel media receipt, LiveKit publish, first outbound
audio, interruption, and buffer clearing.
