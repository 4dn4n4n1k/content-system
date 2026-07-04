"""Cut + SFX planning.

Every boundary becomes a CutPlan; the audible treatment (whoosh before the
cut, impact when a card lands, pop when a meme slams) becomes explicit
SfxEvents instead of hardcoded assembler logic. Defaults reproduce the
historical sound exactly (offsets/gains configurable under render.cut_sfx).

Transition *types* beyond a hard cut aren't renderable yet — critic
recommendations (whips etc.) are attached to their cut and echoed in notes
so no advice is lost.
"""
import re

from .models import CutPlan, SfxEvent, ShotRender

_WHIP_RE = re.compile(r"whip transition", re.IGNORECASE)


def plan(shots: list[ShotRender], cfg: dict, reports: dict
         ) -> tuple[list[CutPlan], list[SfxEvent], list[str]]:
    c = (cfg.get("render") or {}).get("cut_sfx") or {}
    whoosh_gain = float(c.get("whoosh_gain", 0.7))
    whoosh_offset = float(c.get("whoosh_offset_s", -0.12))
    impact_delay = float(c.get("impact_delay_s", 0.2))
    impact_gain = float(c.get("impact_gain", 1.0))
    pop_delay = float(c.get("pop_delay_s", 0.55))
    pop_gain = float(c.get("pop_gain", 1.0))

    whips: dict[int, str] = {}
    for f in (reports.get("timeline") or {}).get("findings", []):
        if f.get("category") == "transitions" and _WHIP_RE.search(f.get("message", "")):
            if f.get("shot") is not None:
                whips[f["shot"]] = f["message"]

    cuts: list[CutPlan] = []
    events: list[SfxEvent] = []
    notes: list[str] = []

    for prev, s in zip(shots, shots[1:]):
        cut = CutPlan(at_s=s.start, from_n=prev.n, to_n=s.n)
        if s.n in whips:
            cut.recommendation = "whip transition (timeline critic)"
            notes.append(f"cut {prev.n}->{s.n}: whip transition recommended — "
                         f"not renderable yet, kept as hard cut")
        cuts.append(cut)
        events.append(SfxEvent(t=s.start + whoosh_offset, name="whoosh",
                               gain=whoosh_gain, reason=f"cut into shot {s.n}"))

    for s in shots:
        if s.type == "diagram":
            events.append(SfxEvent(t=s.start + impact_delay, name="impact",
                                   gain=impact_gain, reason=f"card lands (shot {s.n})"))
        elif s.type == "meme":
            events.append(SfxEvent(t=s.start + pop_delay, name="pop",
                                   gain=pop_gain, reason=f"meme slam (shot {s.n})"))

    events.sort(key=lambda e: e.t)
    return cuts, events, notes
