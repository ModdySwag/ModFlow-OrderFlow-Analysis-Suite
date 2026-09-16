"""The trade-audio samples and their config contract.

Four WAVs ship in `desktop/ui/audio/`; `scripts/make_alert_sounds.py` generates them from nothing
but the standard library. These tests are the receipt: the files exist, are the format the browser
can play, are four *different* sounds, sit inside sane loudness/duration bounds, are reproducible
byte-for-byte from the generator, and the config block that turns them on is clamped on the way in.
"""

from __future__ import annotations

import importlib.util
import struct
import tempfile
import wave
from pathlib import Path

from orderflow_system.desktop import config_store, param_registry

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "orderflow_system" / "desktop" / "ui" / "audio"
GENERATOR = ROOT / "scripts" / "make_alert_sounds.py"

SAMPLES = ("alert-buy.wav", "alert-sell.wav", "alert-buy-hard.wav", "alert-sell-hard.wav")
SOFT = ("alert-buy.wav", "alert-sell.wav")


def _read(path: Path) -> tuple[wave._wave_params, list[int]]:
    with wave.open(str(path), "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    return params, list(struct.unpack("<%dh" % (len(frames) // 2), frames))


# ── the files ───────────────────────────────────────────────────────────────

def test_four_samples_ship_next_to_the_ui():
    present = sorted(p.name for p in AUDIO_DIR.glob("*.wav"))
    assert present == sorted(SAMPLES), present


def test_every_sample_is_a_playable_mono_pcm_wav():
    for name in SAMPLES:
        params, _ = _read(AUDIO_DIR / name)
        assert params.nchannels == 1, name
        assert params.sampwidth == 2, name
        assert params.framerate == 44100, name


def test_the_samples_are_four_different_sounds():
    payloads = {name: (AUDIO_DIR / name).read_bytes() for name in SAMPLES}
    assert len(set(payloads.values())) == 4, "two samples are byte-identical"


def test_the_sounds_are_audible_and_not_clipped():
    for name in SAMPLES:
        _, samples = _read(AUDIO_DIR / name)
        peak = max(abs(s) for s in samples)
        assert 8_000 <= peak <= 32767, f"{name}: peak {peak}"
        # nothing at all in the second half would mean a broken generator
        assert any(s != 0 for s in samples[len(samples) // 2:]), name


def test_the_soft_blip_is_short_and_the_alert_is_longer():
    for name in SOFT:
        params, _ = _read(AUDIO_DIR / name)
        dur = params.nframes / params.framerate
        assert 0.03 <= dur <= 0.15, f"{name}: {dur:.3f}s"
    for name in ("alert-buy-hard.wav", "alert-sell-hard.wav"):
        params, _ = _read(AUDIO_DIR / name)
        dur = params.nframes / params.framerate
        assert 0.15 <= dur <= 0.4, f"{name}: {dur:.3f}s"


def test_the_buy_and_sell_blips_are_mirrors_of_each_other():
    """Same envelope and length, different pitch — the pair a trader learns to read by ear."""
    (pb, buy), (ps, sell) = _read(AUDIO_DIR / "alert-buy.wav"), _read(AUDIO_DIR / "alert-sell.wav")
    assert pb.nframes == ps.nframes
    # the buy blip rings higher: count zero crossings in the last 20 ms
    tail_buy = buy[int(len(buy) * 0.8):]
    tail_sell = sell[int(len(sell) * 0.8):]
    crossings = lambda xs: sum(1 for i in range(1, len(xs)) if (xs[i - 1] < 0) != (xs[i] < 0))
    assert crossings(tail_buy) > crossings(tail_sell), (crossings(tail_buy), crossings(tail_sell))


def test_the_hard_alerts_are_rising_and_falling_pairs():
    """Two tones each: the buy alert steps up, the sell alert steps down."""
    def tone_centroid(samples: list[int], lo: float, hi: float) -> float:
        seg = samples[int(len(samples) * lo):int(len(samples) * hi)]
        crossings = sum(1 for i in range(1, len(seg)) if (seg[i - 1] < 0) != (seg[i] < 0))
        return crossings / max(1e-9, len(seg))

    _, buy = _read(AUDIO_DIR / "alert-buy-hard.wav")
    _, sell = _read(AUDIO_DIR / "alert-sell-hard.wav")
    assert tone_centroid(buy, 0.05, 0.4) < tone_centroid(buy, 0.55, 0.95), "buy alert is not rising"
    assert tone_centroid(sell, 0.05, 0.4) > tone_centroid(sell, 0.55, 0.95), "sell alert is not falling"


def test_the_shipped_samples_are_reproducible_from_the_generator():
    """The generator is the artefact's source of truth — the files on disk must match a fresh run."""
    spec = importlib.util.spec_from_file_location("make_alert_sounds", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as tmp:
        mod.OUT = Path(tmp)
        mod.build()
        for name in SAMPLES:
            assert (Path(tmp) / name).read_bytes() == (AUDIO_DIR / name).read_bytes(), \
                f"{name} differs from a fresh generator run"


# ── the config contract ─────────────────────────────────────────────────────

def test_the_audio_block_is_off_by_default():
    audio = config_store.default_config()["audio"]
    assert audio["enabled"] is False, "a surprise noise is worse than a missing feature"
    assert set(audio) == {"enabled", "volume", "min_size", "hard_multiple", "hard_enabled",
                          "active_symbol_only", "overlap_window_ms", "overlap_floor"}


def test_hostile_audio_values_are_clamped_by_the_store():
    cfg = config_store.default_config()
    cfg["audio"] = {"enabled": "yes please", "volume": 99, "min_size": -5,
                    "hard_multiple": 0, "hard_enabled": "maybe",
                    "active_symbol_only": None, "overlap_window_ms": 10 ** 9,
                    "overlap_floor": -1}
    cfg = config_store._sanitise(cfg)
    audio = cfg["audio"]
    assert audio["enabled"] is False            # only a real True turns it on
    assert audio["volume"] == 1.0
    assert audio["min_size"] == 0.0
    assert audio["hard_multiple"] == 1.0
    assert audio["hard_enabled"] is True        # "maybe" is not a real False
    assert audio["active_symbol_only"] is True
    assert audio["overlap_window_ms"] == 5000
    assert audio["overlap_floor"] == 0.01


def test_a_missing_audio_block_is_rebuilt_by_the_store():
    cfg = config_store.default_config()
    cfg.pop("audio")
    assert config_store._sanitise(cfg)["audio"]["enabled"] is False


def test_every_audio_leaf_is_a_registered_display_variable():
    """The Tape view's Chart menu is built from the registry — an unregistered leaf would be a
    setting with no way to reach it (and the registry test would fail, loudly)."""
    audio_paths = {p for p in param_registry.BY_PATH if p.startswith("audio.")}
    assert audio_paths == {f"audio.{k}" for k in config_store.default_config()["audio"]}
    views = {param_registry.BY_PATH[p].view for p in audio_paths}
    assert views == {"tape"}, views
