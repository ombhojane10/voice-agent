# Latency And Voice Notes

## v1 default

Use Gemini Live native audio through LiveKit:

- model: `gemini-2.5-flash-native-audio-preview-12-2025`
- fallback override: `gemini-3.1-flash-live-preview`
- voice: `Puck`

The native path is preferred because every extra STT/TTS/network hop is audible on PSTN calls.

## Do we need LiveKit with Exotel?

No, not for a phone-only proof of concept. Exotel AgentStream can be the media socket, and a gateway
can talk directly to Gemini Live. That path has fewer network hops and should be benchmarked if
latency is the only priority.

LiveKit is worth keeping when we need production orchestration: room lifecycle, worker dispatch,
recording, browser testing, analytics, human handoff, multi-participant support, or a future SIP
connector. Treat it as the voice-agent control plane, not as a requirement imposed by Exotel.

## Exotel outbound gotcha

Do not point outbound tests at the existing MandiPlus `/exotel/voice` endpoint. That endpoint returns
a human `<Dial>` flow, so the callee hears ringing while Exotel tries to connect the second leg. For
AI calls, Exotel must connect the callee to a Call Flow that contains the Voicebot Applet. The
outbound request should set `Url=http://my.exotel.com/{sid}/exoml/start_voice/{app_id}`.

## Indian voices

Gemini Live native voices are named voices rather than locale-specific `hi-IN` voices. Gemini TTS
supports many Indian languages, and Google Cloud TTS exposes explicit Indian locale voices such as
Hindi, Gujarati, Marathi, Tamil, Telugu, and Bengali. If native Gemini Live sounds too global, add a
second connector that uses Cloud TTS/Chirp for the outbound audio leg and measure the latency tradeoff
before making it default.

## Practical latency rules

- Warm the LiveKit room and agent before placing outbound calls.
- Keep only the current Exotel media frame in memory unless resampling needs a small carry buffer.
- Send short answers: one or two spoken sentences, one question.
- Clear outbound audio immediately on caller barge-in.
- Defer backend tool calls until after collecting the minimum required fields.
- Keep metrics around first audio, frame forwarding, and interruption cutoff.
