"""Motion planning: zoom punches on long b-roll holds.

A punch is an instant scale step mid-shot — the classic re-energizer for a
hold that outstays its welcome. Sources: any b-roll shot at or past the
configured length gets one at its midpoint; explicit zoom-punch
recommendations from the Timeline Critic's report are honored too.
"""
import re

from .models import MotionPlan, ShotRender

_PUNCH_RE = re.compile(r"zoom punch", re.IGNORECASE)


def plan(shots: list[ShotRender], cfg: dict, reports: dict) -> None:
    m = (cfg.get("render") or {}).get("motion") or {}
    enabled = bool(m.get("zoom_punch", True))
    min_s = float(m.get("punch_min_shot_s", 10))
    scale = float(m.get("punch_scale", 1.08))

    critic_punches: set[int] = set()
    for f in (reports.get("timeline") or {}).get("findings", []):
        if f.get("category") == "transitions" and _PUNCH_RE.search(f.get("message", "")):
            if f.get("shot") is not None:
                critic_punches.add(f["shot"])

    if not enabled:
        return
    for s in shots:
        if s.kind != "video" or s.type in ("diagram", "meme"):
            continue  # cards/memes carry their own animation
        if s.duration >= min_s:
            s.motion = MotionPlan(zoom_punch_at_s=s.duration / 2,
                                  zoom_punch_scale=scale,
                                  reason=f"{s.duration:.0f}s hold >= {min_s:.0f}s")
        elif s.n in critic_punches and s.duration >= 4:
            s.motion = MotionPlan(zoom_punch_at_s=s.duration / 2,
                                  zoom_punch_scale=scale,
                                  reason="timeline critic recommendation")
