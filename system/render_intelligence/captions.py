"""Caption planning: on/off + per-shot emphasis metadata.

Emphasis marks shots where the words ARE the moment (stat/claim beats found
by the Creative Director) so future caption renderers can scale/color them
harder. The current .ass pipeline renders uniformly; emphasis is carried in
the plan so upgrading captions later is a renderer change only.
"""
from .models import ShotRender


def plan(shots: list[ShotRender], cfg: dict, reports: dict) -> bool:
    enabled = bool((cfg.get("captions") or {}).get("enabled", True))

    stat_times = [
        op["at_s"] for op in (reports.get("creative") or {}).get("visual_opportunities", [])
        if op.get("kind") == "stat_card" and op.get("confidence", 0) >= 0.8
    ]
    for s in shots:
        end = s.start + s.duration
        if any(s.start <= t < end for t in stat_times):
            s.caption_emphasis = "high"
    return enabled
