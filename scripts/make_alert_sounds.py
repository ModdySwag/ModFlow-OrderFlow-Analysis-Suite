#!/usr/bin/env python3
"""Generate the trade-audio alert samples (stdlib only — reproducible, no third-party audio).

Four short WAVs, in the register traders already know from their terminals: a soft single blip for
an ordinary print, and a two-tone "alert" (the classic rising/falling terminal chime) for the loud
ones. Every sample is generated here — nothing is sampled from any product, so the files carry no
licence question. Run from the repo root:

    .venv/Scripts/python.exe scripts/make_alert_sounds.py

Writes `orderflow_system/desktop/ui/audio/*.wav` (44.1 kHz, mono, 16-bit PCM), which the frozen
build already ships because `build_exe.py --add-data`s the whole `ui/` directory.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "orderflow_system" / "desktop" / "ui" / "audio"
SR = 44100

#: peak amplitude of the finished files — loud enough to hear over a quiet room, 6 dB under full
#: scale so nothing clips when a browser mixes several at once
PEAK = 0.5


def _bell(freq: float, dur: float, *, amp: float = 1.0, decay: float = 14.0,
          harmonics: tuple[float, ...] = (1.0, 0.32, 0.10)) -> list[float]:
    """A struck bell: harmonics over an exponential decay, 4 ms attack (no click on start)."""
    n = int(SR * dur)
    out = []
    attack = max(1, int(SR * 0.004))
    for i in range(n):
        t = i / SR
        env = math.exp(-decay * t)
        if i < attack:
            env *= i / attack
        value = 0.0
        for k, weight in enumerate(harmonics, start=1):
            value += weight * math.sin(2 * math.pi * freq * k * t)
        out.append(amp * env * value / sum(harmonics))
    return out


def _tick(dur: float = 0.014, *, amp: float = 0.9, rng: random.Random | None = None) -> list[float]:
    """A tape-print tick: a short filtered noise transient (this is the 'data' character)."""
    rng = rng or random.Random(7)
    n = int(SR * dur)
    out = []
    last = 0.0
    for i in range(n):
        env = math.exp(-90.0 * (i / SR))
        noise = rng.uniform(-1.0, 1.0)
        last = 0.55 * last + 0.45 * noise          # a one-pole low-pass: less hiss, more thock
        out.append(amp * env * last)
    return out


def _mix(*parts: list[float], offsets: tuple[int, ...] | None = None) -> list[float]:
    offs = offsets or tuple(0 for _ in parts)
    length = max((o + len(p)) for o, p in zip(offs, parts))
    out = [0.0] * length
    for off, part in zip(offs, parts):
        for i, value in enumerate(part):
            out[off + i] += value
    return out


def _fade(samples: list[float], ms: float = 3.0) -> list[float]:
    """No click at the very end: a 3 ms release ramp to zero."""
    n = max(1, int(SR * ms / 1000.0))
    if len(samples) <= 2 * n:
        return samples
    for i in range(n):
        samples[-1 - i] *= i / n
    return samples


def _normalise(samples: list[float], peak: float = PEAK) -> list[float]:
    top = max((abs(v) for v in samples), default=0.0)
    if top <= 0:
        return samples
    gain = peak / top
    return [v * gain for v in samples]


def _write(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames)
    try:
        shown = path.relative_to(ROOT)
    except ValueError:            # a caller (the tests) may point OUT at a scratch directory
        shown = path
    print(f"wrote {shown} ({len(samples) / SR * 1000:.0f} ms, {path.stat().st_size} bytes)")


def build() -> None:
    # ordinary print — a soft blip with the tape tick in front of it
    buy = _fade(_normalise(_mix(_tick(), _bell(1180.0, 0.09), offsets=(0, 0))))
    sell = _fade(_normalise(_mix(_tick(amp=0.8), _bell(880.0, 0.09), offsets=(0, 0))))
    # the loud one — a two-tone terminal alert: rising for buys, falling for sells
    buy_hard = _fade(_normalise(_mix(
        _bell(1046.5, 0.11, decay=11.0),
        _bell(1568.0, 0.15, decay=11.0),
        offsets=(0, int(SR * 0.075)),
    )))
    sell_hard = _fade(_normalise(_mix(
        _bell(1568.0, 0.11, decay=11.0),
        _bell(1046.5, 0.15, decay=11.0),
        offsets=(0, int(SR * 0.075)),
    )))

    _write(OUT / "alert-buy.wav", buy)
    _write(OUT / "alert-sell.wav", sell)
    _write(OUT / "alert-buy-hard.wav", buy_hard)
    _write(OUT / "alert-sell-hard.wav", sell_hard)


if __name__ == "__main__":
    build()
