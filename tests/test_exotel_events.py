import base64

from voice_agent.exotel_events import build_clear_event, build_media_event, parse_exotel_event


def test_parse_connected_event():
    event = parse_exotel_event({"event": "connected", "stream_sid": "s1"})
    assert event.event == "connected"
    assert event.stream_sid == "s1"


def test_parse_start_event_with_call_sid():
    event = parse_exotel_event(
        {"event": "start", "start": {"streamSid": "s1", "callSid": "c1"}}
    )
    assert event.event == "start"
    assert event.stream_sid == "s1"
    assert event.call_sid == "c1"


def test_parse_media_decodes_payload():
    payload = b"\x01\x02\x03\x04"
    event = parse_exotel_event(
        {"event": "media", "stream_sid": "s1", "media": {"payload": base64.b64encode(payload)}}
    )
    assert event.is_media
    assert event.payload == payload


def test_parse_dtmf_mark_clear_stop():
    assert parse_exotel_event({"event": "dtmf", "dtmf": {"digit": "1"}}).dtmf_digit == "1"
    assert parse_exotel_event({"event": "mark", "mark": {"name": "m1"}}).mark_name == "m1"
    assert parse_exotel_event({"event": "clear"}).event == "clear"
    assert parse_exotel_event({"event": "stop"}).event == "stop"


def test_build_outbound_events():
    media = build_media_event("s1", b"abc")
    assert media["event"] == "media"
    assert media["stream_sid"] == "s1"
    assert base64.b64decode(media["media"]["payload"]) == b"abc"
    assert build_clear_event("s1") == {"event": "clear", "stream_sid": "s1"}
