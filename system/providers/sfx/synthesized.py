"""Placeholder SFX provider: synthesizes basic sounds with ffmpeg lavfi.

Usable but intentionally simple — the product workflow is to drop nicer
royalty-free files over the same names in sfx/; this provider never touches
existing files. A future FreesoundProvider etc. implements the same contract
by downloading instead of synthesizing.
"""
import subprocess
from pathlib import Path

from ..base.sfx import SAMPLE_RATE, SoundEffectProvider
from ..errors import PermanentFailure

_GENERATORS: dict[str, list[str]] = {
    # airy noise swish: fade in/out band-limited pink noise
    "whoosh": [
        "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:r=48000:a=0.8",
        "-af", "highpass=f=500,lowpass=f=5000,"
               "afade=t=in:st=0:d=0.22:curve=qsin,afade=t=out:st=0.22:d=0.28:curve=qsin",
    ],
    # low thud + tiny click transient
    "impact": [
        "-f", "lavfi", "-i", "sine=frequency=52:duration=0.7:r=48000",
        "-f", "lavfi", "-i", "anoisesrc=d=0.06:c=white:r=48000:a=0.4",
        "-filter_complex",
        "[0:a]afade=t=out:st=0.02:d=0.66:curve=exp,volume=2.0[low];"
        "[1:a]highpass=f=900,afade=t=out:st=0:d=0.06[click];"
        "[low][click]amix=inputs=2:duration=longest:normalize=0",
    ],
    # short cartoon-ish pop for meme entrances
    "pop": [
        "-f", "lavfi", "-i", "sine=frequency=300:duration=0.15:r=48000",
        "-af", "afade=t=out:st=0:d=0.15:curve=exp,volume=1.4",
    ],
}


class SynthesizedSfxProvider(SoundEffectProvider):
    name = "synthesized"

    def ensure(self, names: tuple[str, ...], dest_dir: Path) -> None:
        dest_dir.mkdir(exist_ok=True)
        for sound in names:
            dest = dest_dir / f"{sound}.wav"
            if dest.exists():
                continue
            args = _GENERATORS.get(sound)
            if args is None:
                raise PermanentFailure(f"no synthesis recipe for SFX '{sound}'", self.name)
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
                 "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dest)])
            if result.returncode != 0:
                raise PermanentFailure(f"failed to generate default SFX {sound}.wav", self.name)
            print(f"  generated default SFX: sfx/{sound}.wav (replace with your own pack anytime)")
