"""Timeline foundation: joins timing.json + shotlist.json into ShotRender
skeletons, computes the energy curve and pattern-interrupt map that the
other sub-planners key their decisions off.

Energy is a 0..1 heuristic per shot: shot type sets the base (cards and
memes are beats, b-roll is flow), shorter shots read more energetic, and
the hook window gets a boost. Configurable under render.energy.
"""
from ..util import shot_asset
from .models import CameraPlan, MotionPlan, ShotRender

_BASE_ENERGY = {"meme": 0.9, "diagram": 0.75, "ai": 0.6, "stock": 0.55}


def build_shots(project, timing: dict, shots_by_n: dict, cfg: dict) -> list[ShotRender]:
    fps = cfg["video"]["fps"]
    e_cfg = (cfg.get("render") or {}).get("energy") or {}
    hook_boost = float(e_cfg.get("hook_boost", 0.15))
    hook_window = float(e_cfg.get("hook_window_s", 30))

    shots: list[ShotRender] = []
    order = timing["shots"]
    for i, t in enumerate(order):
        shot = shots_by_n[t["n"]]
        end = order[i + 1]["start"] if i + 1 < len(order) else timing["duration"]
        f0, f1 = round(t["start"] * fps), round(end * fps)
        if f1 - f0 < 2:
            continue
        duration = (f1 - f0) / fps
        asset = shot_asset(project, shot)
        kind = "image" if asset.suffix.lower() == ".png" else "video"

        energy = _BASE_ENERGY.get(shot["type"], 0.6)
        energy += max(min((8 - duration) / 20, 0.2), -0.2)
        if t["start"] < hook_window:
            energy += hook_boost
        energy = max(0.0, min(energy, 1.0))

        shots.append(ShotRender(
            n=t["n"], type=shot["type"], kind=kind, start=t["start"],
            duration=duration, frames=f1 - f0, energy=energy,
            camera=CameraPlan(), motion=MotionPlan()))
    return shots


def energy_curve(shots: list[ShotRender]) -> list[dict]:
    return [{"t": round(s.start, 2), "energy": round(s.energy, 2)} for s in shots]


def pattern_interrupts(shots: list[ShotRender]) -> list[float]:
    return [s.start for s in shots if s.type in ("diagram", "meme")]


def interrupt_notes(shots: list[ShotRender], duration: float, cfg: dict) -> list[str]:
    """Long gaps without an interrupt — surfaced as notes (the critic warns
    about these too; here they inform pacing-aware future renderers)."""
    gap_limit = float(((cfg.get("render") or {}).get("energy") or {})
                      .get("interrupt_gap_s", 60))
    notes = []
    marks = [0.0] + pattern_interrupts(shots) + [duration]
    for a, b in zip(marks, marks[1:]):
        if b - a > gap_limit:
            notes.append(f"{b - a:.0f}s stretch from {a:.0f}s without a pattern "
                         f"interrupt — energy will sag here")
    return notes
