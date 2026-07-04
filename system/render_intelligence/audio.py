"""Audio planning: music level/fades, SFX level, loudness target.

Values snapshot the config so render_plan.json is a complete, auditable
record of what the mix will do. Sidechain ducking is planned (duck.enabled)
but off by default — the current static music level under the voice is the
compatible behavior.
"""
from .models import AudioPlan


def plan(cfg: dict, reports: dict) -> AudioPlan:
    r = (cfg.get("render") or {}).get("audio") or {}
    return AudioPlan(
        music_volume=float((cfg.get("music") or {}).get("volume", 0.10)),
        music_fade_in_s=float(r.get("music_fade_in_s", 1.5)),
        music_fade_out_s=float(r.get("music_fade_out_s", 3.0)),
        sfx_volume=float((cfg.get("sfx") or {}).get("volume", 0.45)),
        loudnorm=bool((cfg.get("audio") or {}).get("loudnorm", True)),
        duck={"enabled": bool(r.get("duck", False))},
    )
