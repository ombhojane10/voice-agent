# Exotel AgentStream Setup

## The key idea

For outbound AI calls, do not use the existing MandiPlus `/exotel/voice` endpoint. That flow returns
a human `<Dial>`, so the callee hears ringing while Exotel tries to connect another phone number.

The correct flow is:

```text
Exotel Calls/connect
  From=<customer phone>
  CallerId=<ExoPhone>
  Url=http://my.exotel.com/<account_sid>/exoml/start_voice/<app_id>
  no To parameter

Customer answers
  -> Exotel executes the App Bazaar flow
  -> Voicebot Applet opens WSS to voice-agent
  -> voice-agent bridges audio to LiveKit/Gemini
```

This is an outbound call. `From` is the customer's phone number because Exotel's API names the first
leg as `From`. `CallerId` is the Exotel number shown to the customer.

## Dashboard setup

1. Open `https://my.exotel.com`.
2. Go to `App Bazaar` / `Call Flows`.
3. Create a new app/flow, for example `Mandi Gemini Voicebot`.
4. Add a `Voicebot Applet` for bidirectional streaming.
5. In the Voicebot Applet `URL` field, use one of:
   - Static: `wss://<voice-agent-domain>/ws/exotel/agentstream`
   - Dynamic: `https://<voice-agent-domain>/exotel/agentstream-url`
6. Start with sample rate `8000`, because PSTN and the current bridge are configured for 8 kHz PCM.
7. Enable recording only for QA/compliance if needed.
8. Set the next applet to `Hangup` or a short fallback. Do not add a human `Connect` applet for the
   initial AI test.
9. Save the app/flow.
10. Copy the app id from `App Bazaar > My Apps` or from the flow URL. It is the value used in:

```text
http://my.exotel.com/<account_sid>/exoml/start_voice/<app_id>
```

## Required env

In `voice-agent/.env`:

```env
EXOTEL_AI_CALLER_ID=<optional-new-exophone-for-ai-calls>
EXOTEL_AGENTSTREAM_APP_ID=<app_id>
EXOTEL_AGENTSTREAM_FLOW_URL=http://my.exotel.com/oneroot3/exoml/start_voice/<app_id>
PUBLIC_BASE_URL=https://<voice-agent-domain>
```

If `EXOTEL_AI_CALLER_ID` is blank, the agent falls back to `EXOTEL_CALLER_ID`.

In `mandiplus` production env, add these only after the backend has code that triggers AI voice
calls:

```env
VOICE_AGENT_BASE_URL=https://<voice-agent-domain>
EXOTEL_AGENTSTREAM_APP_ID=<app_id>
EXOTEL_AGENTSTREAM_FLOW_URL=http://my.exotel.com/oneroot3/exoml/start_voice/<app_id>
```

## Correct outbound API call

```bash
curl -X POST "https://api.exotel.com/v1/Accounts/oneroot3/Calls/connect" \
  -u "$EXOTEL_API_KEY:$EXOTEL_API_TOKEN" \
  -d "From=+919876543210" \
  -d "CallerId=$EXOTEL_AI_CALLER_ID" \
  -d "Url=http://my.exotel.com/oneroot3/exoml/start_voice/$EXOTEL_AGENTSTREAM_APP_ID" \
  -d "CallType=trans"
```

Do not send `To` in this request. `To` switches the request toward the two-number connect behavior.

## Recommended production isolation

Use a new ExoPhone for AI outbound calls if possible:

- Existing number remains attached to current inbound/support flows.
- New number becomes the caller ID for AI campaigns.
- Missed calls/callbacks to the new number can route to the AI Voicebot Applet or a separate fallback.
- Call recordings, status callbacks, and analytics are easier to separate.

## What can be automated

The API keys can place calls and poll call status once the app/flow exists. Public Exotel docs do not
show an API for creating the App Bazaar Voicebot flow itself. Treat the flow/app id as a dashboard
configuration step unless Exotel support enables a private App Builder API for the account.
