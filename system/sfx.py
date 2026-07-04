"""Sound design: transition/impact SFX for the assembler.

Sounds live in sfx/ at the repo root (whoosh.wav, impact.wav, pop.wav —
48 kHz mono s16). The active SFX provider (config.yaml providers.sfx)
guarantees they exist; existing files are never touched, so dropping
replacements from any royalty-free pack over those filenames still works.

The assembler passes a list of (time_s, name, gain) events; build_track()
overlays them into one sfx_track.wav that gets mixed under the voiceover.
"""
import sys
import wave
from pathlib import Path

import numpy as np

from .providers.base.sfx import SAMPLE_RATE as SR
from .util import ROOT

SFX_DIR = ROOT / "sfx"
SOUNDS = ("whoosh", "impact", "pop")


def ensure_sfx() -> None:
    """Make sure all SFX files exist (via the configured provider)."""
    from .providers import ProviderError, ProviderFactory

    try:
        provider = ProviderFactory.get_sfx_provider()
        provider.check_ready()
        provider.ensure(SOUNDS, SFX_DIR)
    except ProviderError as e:
        sys.exit(str(e))


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getsampwidth() != 2:
            sys.exit(f"{path.name}: SFX files must be {SR} Hz 16-bit "
                     f"(got {w.getframerate()} Hz, {w.getsampwidth() * 8}-bit). "
                     f"Convert: ffmpeg -i in.wav -ar {SR} -ac 1 -c:a pcm_s16le out.wav")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1).astype(np.int16)
    return data.astype(np.int32)


def build_track(events: list[tuple[float, str, float]], duration: float, dest: Path) -> None:
    """Overlay events [(time_s, sfx_name, gain)] into a mono wav of `duration`."""
    track = np.zeros(int(duration * SR) + SR, dtype=np.int32)
    cache: dict[str, np.ndarray] = {}
    for t, name, gain in events:
        if name not in cache:
            cache[name] = _read(SFX_DIR / f"{name}.wav")
        data = cache[name]
        i0 = max(0, int(t * SR))
        seg = track[i0:i0 + len(data)]
        seg += (data[:len(seg)] * gain).astype(np.int32)
    track = np.clip(track, -32768, 32767).astype(np.int16)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(track.tobytes())
