from array import array

from voice_agent.audio_bridge import OutboundAudioBuffer, resample_pcm16_mono


def pcm(samples):
    return array("h", samples).tobytes()


def test_resample_up_and_down_keeps_pcm16_shape():
    source = pcm([0, 1000, -1000, 0] * 20)
    up = resample_pcm16_mono(source, 8000, 48000)
    down = resample_pcm16_mono(up, 48000, 8000)

    assert len(up) == len(source) * 6
    assert abs(len(down) - len(source)) <= 2


def test_resample_rejects_odd_length_payload():
    try:
        resample_pcm16_mono(b"\x00", 8000, 48000)
    except ValueError as exc:
        assert "PCM16" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_outbound_buffer_keeps_latest_frame_and_clears():
    buffer = OutboundAudioBuffer(max_frames=1)
    buffer.push(b"old")
    buffer.push(b"new")

    assert buffer.pop() == b"new"
    buffer.push(b"a")
    buffer.push(b"b")
    assert buffer.clear() == 1
    assert buffer.pop() is None
