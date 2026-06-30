import pytest

from voice_agent.config import Settings
from voice_agent.outbound import build_exotel_call_payload, normalize_india_phone


def test_normalize_india_phone_accepts_10_digit_number():
    assert normalize_india_phone("9876543210") == "9876543210"


def test_normalize_india_phone_accepts_91_prefixed_number():
    assert normalize_india_phone("+91 98765 43210") == "9876543210"


def test_normalize_india_phone_rejects_invalid_number():
    with pytest.raises(ValueError):
        normalize_india_phone("123")


def test_build_exotel_call_payload_uses_agentstream_fields():
    settings = Settings(
        _env_file=None,
        public_base_url="https://voice.example.com",
        exotel_caller_id="08047492990",
        exotel_ai_caller_id="08041234567",
        exotel_account_sid="oneroot3",
        exotel_agentstream_app_id="926",
        exotel_status_callback_url="",
    )

    payload = build_exotel_call_payload(settings, "9876543210")

    assert payload == {
        "From": "9876543210",
        "CallerId": "08041234567",
        "Url": "http://my.exotel.com/oneroot3/exoml/start_voice/926",
        "CallType": "trans",
        "Record": "true",
        "StatusCallback": "",
    }


def test_build_exotel_call_payload_falls_back_to_existing_caller_id():
    settings = Settings(
        _env_file=None,
        public_base_url="https://voice.example.com",
        exotel_caller_id="08047492990",
        exotel_account_sid="oneroot3",
        exotel_agentstream_app_id="926",
        exotel_status_callback_url="",
    )

    payload = build_exotel_call_payload(settings, "9876543210")

    assert payload["CallerId"] == "08047492990"
