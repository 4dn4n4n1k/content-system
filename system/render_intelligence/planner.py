"""Render Intelligence orchestrator.

build_plan() joins shotlist.json + timing.json (+ the two editorial reports
when present) and runs the sub-planners in order:

    timeline (energy) → camera → motion → transitions/SFX → captions → audio

ensure_plan() is what the assembler calls: it loads render_plan.json if it
is still valid for the current timing/assets, otherwise rebuilds it — so
`assemble` keeps working with zero extra operator steps.

Extensibility: sub-planners are (name, fn) entries in SUBPLANNERS with the
signature fn(shots, cfg, reports) mutating the ShotRender list (camera,
motion, captions) or returning plan parts (transitions, audio). A future AI
planner or vision-feedback pass registers via register() and runs after the
deterministic ones, refining their output — no interface changes.
"""
import json
import sys
from pathlib import Path

from ..util import load_config, load_shotlist, read_json, resolve_project, shot_asset
from . import audio as audio_mod
from . import camera, captions, motion, timeline
from . import transitions as transitions_mod
from .models import RenderPlan

SUBPLANNERS: list[tuple[str, callable]] = []  # extra registered planners


def register(name: str, fn) -> None:
    """Add a planner pass run after the built-in ones: fn(plan_dict, cfg, reports)."""
    SUBPLANNERS.append((name, fn))


def _load_reports(project: Path) -> dict:
    reports = {}
    for key, fname in (("creative", "creative_report.json"),
                       ("timeline", "timeline_report.json")):
        path = project / fname
        reports[key] = read_json(path) if path.exists() else None
    return reports


def build_plan(project: Path, cfg: dict) -> dict:
    timing_path = project / "timing.json"
    if not timing_path.exists():
        sys.exit("Missing timing.json — run `python pipeline.py align` first.")
    timing = read_json(timing_path)
    shots_by_n = {s["n"]: s for s in load_shotlist(project)["shots"]}
    for t in timing["shots"]:
        if t["n"] not in shots_by_n:
            sys.exit(f"timing.json references shot {t['n']} missing from shotlist.json")
    reports = _load_reports(project)

    shots = timeline.build_shots(project, timing, shots_by_n, cfg)
    camera.plan(shots, cfg, reports)
    motion.plan(shots, cfg, reports)
    cuts, events, notes = transitions_mod.plan(shots, cfg, reports)
    captions_enabled = captions.plan(shots, cfg, reports)
    audio_plan = audio_mod.plan(cfg, reports)
    notes += timeline.interrupt_notes(shots, timing["duration"], cfg)
    if reports["creative"] is None:
        notes.append("creative_report.json absent — caption emphasis defaulted")
    if reports["timeline"] is None:
        notes.append("timeline_report.json absent — critic recommendations not folded in")

    plan = RenderPlan(
        fps=cfg["video"]["fps"], duration=timing["duration"], shots=shots,
        cuts=cuts, events=events, audio=audio_plan,
        captions_enabled=captions_enabled,
        energy_curve=timeline.energy_curve(shots),
        pattern_interrupts=timeline.pattern_interrupts(shots), notes=notes,
    ).to_dict()

    for name, fn in SUBPLANNERS:  # registered refiners (AI/vision, future)
        fn(plan, cfg, reports)
    return plan


def _stale(plan: dict, project: Path, timing: dict) -> str | None:
    if abs(plan.get("duration", -1) - timing["duration"]) > 0.05:
        return "timing changed"
    shots_by_n = {s["n"]: s for s in load_shotlist(project)["shots"]}
    for ps in plan.get("shots", []):
        shot = shots_by_n.get(ps["n"])
        if shot is None:
            return f"shot {ps['n']} no longer in shotlist"
        asset = shot_asset(project, shot)
        kind = "image" if asset.suffix.lower() == ".png" else "video"
        if kind != ps.get("kind"):
            return f"shot {ps['n']} asset changed ({ps.get('kind')} -> {kind})"
    return None


def ensure_plan(project: Path, cfg: dict) -> dict:
    """Load render_plan.json when valid; rebuild (and save) when missing/stale."""
    plan_path = project / "render_plan.json"
    timing = read_json(project / "timing.json")
    if plan_path.exists():
        plan = read_json(plan_path)
        reason = _stale(plan, project, timing)
        if reason is None:
            return plan
        print(f"render_plan.json is stale ({reason}) — replanning")
    else:
        print("No render_plan.json — planning now")
    plan = build_plan(project, cfg)
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan


def run(project_slug: str | None) -> None:
    from .report import summarize

    project = resolve_project(project_slug)
    cfg = load_config()
    plan = build_plan(project, cfg)
    dest = project / "render_plan.json"
    dest.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    summarize(plan)
    print(f"\nPlan: {dest}")
    print("`assemble` will follow this plan (it re-plans automatically if "
          "timing or assets change).")
