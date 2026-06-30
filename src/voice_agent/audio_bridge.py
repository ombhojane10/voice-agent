from __future__ import annotations

import sys
from array import array
from collections import deque
from dataclasses import dataclass, field

PCM16_MIN = -32768
PCM16_MAX = 32767


def _pcm16_to_samples(pcm: bytes) -> array:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _samples_to_pcm16(samples: array) -> bytes:
    out = array("h", samples)
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


def resample_pcm16_mono(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    """Small-frame linear PCM16 resampler.

    Exotel commonly sends 8 kHz mono PCM frames while LiveKit/Gemini paths are usually 48 kHz.
    This pure-Python resampler keeps the scaffold dependency-light; replace with libsoxr for
    production audio quality if needed.
    """
    if source_rate == target_rate or not pcm:
        return pcm
    if len(pcm) % 2 != 0:
        raise ValueError("PCM16 payload length must be even")

    source = _pcm16_to_samples(pcm)
    if not source:
        return b""

    target_len = max(1, round(len(source) * target_rate / source_rate))
    if len(source) == 1:
        return _samples_to_pcm16(array("h", [source[0]] * target_len))

    ratio = source_rate / target_rate
    target = array("h")
    for i in range(target_len):
        pos = i * ratio
        left_index = int(pos)
        right_index = min(left_index + 1, len(source) - 1)
        frac = pos - left_index
        sample = round(source[left_index] * (1.0 - frac) + source[right_index] * frac)
        target.append(max(PCM16_MIN, min(PCM16_MAX, sample)))
    return _samples_to_pcm16(target)


@dataclass
class OutboundAudioBuffer:
    max_frames: int = 1
    frames: deque[bytes] = field(default_factory=deque)

    def push(self, frame: bytes) -> None:
        if not frame:
            return
        self.frames.append(frame)
        while len(self.frames) > self.max_frames:
            self.frames.popleft()

    def pop(self) -> bytes | None:
        if not self.frames:
            return None
        return self.frames.popleft()

    def clear(self) -> int:
        count = len(self.frames)
        self.frames.clear()
        return count
