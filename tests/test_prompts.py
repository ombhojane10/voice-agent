from voice_agent.prompts import MANDI_VOICE_PROMPT, SUPPORTED_LANGUAGE_HINTS, build_prompt


def test_prompt_starts_hindi_hinglish_and_mirrors_indian_languages():
    prompt = MANDI_VOICE_PROMPT.lower()
    assert "start in natural hindi/hinglish" in prompt
    for language in ["marathi", "gujarati", "tamil", "telugu", "kannada", "punjabi", "bengali"]:
        assert language in prompt


def test_prompt_keeps_replies_short_and_interruptible():
    prompt = MANDI_VOICE_PROMPT.lower()
    assert "one or two short spoken sentences" in prompt
    assert "if interrupted, stop speaking immediately" in prompt


def test_supported_language_hints_include_v1_languages():
    assert SUPPORTED_LANGUAGE_HINTS["hi"] == "Hindi/Hinglish"
    assert SUPPORTED_LANGUAGE_HINTS["gu"] == "Gujarati"
    assert SUPPORTED_LANGUAGE_HINTS["te"] == "Telugu"


def test_build_prompt_can_include_known_caller_phone():
    prompt = build_prompt("919999999999")
    assert "Known caller phone" in prompt
    assert "919999999999" in prompt
