"""Timeline Critic orchestrator.

Builds the timeline (script.md × shotlist.json × timing.json when present),
runs every registered analyzer, adds retention-risk analysis, scores the
result, and writes timeline_report.{json,md}.

Plugin registry: an analyzer is any callable
    (timeline: Timeline, script_text: str, rules: dict) -> list[Finding]
registered via `register()`. Future LLM reviewers, vision reviewers, or a
YouTube-analytics feedback pass implement the same signature and simply
register themselves — nothing else changes.

Read-only by contract: this package never edits script.md or shotlist.json.
"""
import re
import sys
from pathlib import Path

from ..util import load_config, load_shotlist, read_json, resolve_project
from . import diversity, pacing, transitions
from . import narrative as narrative_mod
from .models import CriticReport, Finding, ShotInfo, Timeline
from .report import write_json, write_markdown
from .rules import PAYOFF_PATTERN, load_rules

MARKER_RE = re.compile(r"\[SHOT\s+(\d+)\]", re.IGNORECASE)

_SCORED_CATEGORIES = ("hook", "pacing", "diversity", "narrative", "retention")
_PENALTY = {"critical": 25, "warning": 10, "suggestion": 3, "strength": 0}
_BONUS = 3  # strengths claw back a little

ANALYZERS = [pacing.analyze, diversity.analyze, narrative_mod.analyze,
             transitions.analyze]


def register(analyzer) -> None:
    """Add a reviewer plugin (LLM/vision/analytics) — same signature."""
    ANALYZERS.append(analyzer)


# ── timeline construction ────────────────────────────────────────────────────

def _visual_text(shot: dict) -> str:
    if shot["type"] == "ai":
        return shot.get("prompt", "").lower()
    if shot["type"] == "stock":
        return shot.get("query", "").lower()
    if shot["type"] == "meme":
        return f"{shot.get('template', '')} {shot.get('top', '')} {shot.get('bottom', '')}".lower()
    fields = " ".join(str(v) for v in (shot.get("fields") or {}).values())
    return f"{shot.get('template', '')} {fields}".lower()


def build_timeline(project: Path, rules: dict) -> tuple[Timeline, str]:
    script_path = project / "script.md"
    if not script_path.exists():
        sys.exit(f"Missing {script_path} — the critic reviews script + shot list.")
    shots_by_n = {s["n"]: s for s in load_shotlist(project)["shots"]}

    # Walk the script: track the nearest heading, split narration by marker.
    section = ""
    segments: list[tuple[int, str, str]] = []   # (n, section, narration)
    current_n: int | None = None
    buffer: list[str] = []
    plain: list[str] = []

    def flush():
        if current_n is not None:
            segments.append((current_n, section_at_marker[current_n], " ".join(buffer)))

    section_at_marker: dict[int, str] = {}
    for line in script_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        if stripped.startswith(("<!--", ">")):
            continue
        plain.append(line)
        pos = 0
        for m in MARKER_RE.finditer(line):
            text_before = line[pos:m.start()].strip()
            if text_before:
                buffer.append(text_before)
            flush()
            current_n = int(m.group(1))
            section_at_marker[current_n] = section
            buffer = []
            pos = m.end()
        tail = line[pos:].strip()
        if tail:
            buffer.append(tail)
    flush()

    script_text = MARKER_RE.sub(" ", "\n".join(plain))

    # Durations: measured (timing.json) or estimated from narration length.
    timing_path = project / "timing.json"
    timing = read_json(timing_path) if timing_path.exists() else None
    wpm = rules["wpm"]

    infos: list[ShotInfo] = []
    starts = {t["n"]: t["start"] for t in (timing or {}).get("shots", [])}
    cursor = 0.0
    ordered = [seg for seg in segments if seg[0] in shots_by_n]
    for i, (n, sec, narration) in enumerate(ordered):
        shot = shots_by_n[n]
        words = len(narration.split())
        if timing and n in starts:
            start = starts[n]
            nxt = ordered[i + 1][0] if i + 1 < len(ordered) else None
            end = starts.get(nxt, timing["duration"]) if nxt is not None else timing["duration"]
            duration = max(end - start, 0.5)
        else:
            start = cursor
            duration = max(words / wpm * 60, 2.5)
        cursor = start + duration
        infos.append(ShotInfo(
            n=n, type=shot["type"], template=shot.get("template"),
            visual_text=_visual_text(shot), narration=narration, words=words,
            section=sec, start=round(start, 2), duration=round(duration, 2)))

    missing = sorted(set(shots_by_n) - {n for n, _, _ in ordered})
    if missing:
        print(f"  note: shot(s) {missing} exist in shotlist.json but have no "
              f"[SHOT n] marker in script.md — excluded from the timeline")

    source = "timing.json" if timing else "estimated"
    seen_sections: list[str] = []
    for s in infos:
        if s.section and s.section not in seen_sections:
            seen_sections.append(s.section)
    return Timeline(shots=infos, total=round(cursor, 1), source=source,
                    sections=seen_sections), script_text


# ── retention analysis (built-in reviewer) ───────────────────────────────────

def _retention(timeline: Timeline, script_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    r = rules["retention"]
    shots = timeline.shots

    # long static sequences (a single held shot is the worst offender)
    for s in shots:
        if s.duration >= r["static_sequence_s"]:
            findings.append(Finding(
                "critical", "retention",
                f"shot {s.n} is a {s.duration:.0f}s static stretch — "
                f"guaranteed drop-off zone", shot_n=s.n, at_s=s.start))

    # pattern-interrupt gaps
    last = 0.0
    for s in shots:
        if s.is_interrupt:
            gap = s.start - last
            if gap > r["interrupt_interval_s"]:
                findings.append(Finding(
                    "warning", "retention",
                    f"{gap:.0f}s of uninterrupted b-roll before shot {s.n} — "
                    f"add a stat/card/meme beat inside it", at_s=last))
            last = s.start
    if shots and timeline.total - last > r["interrupt_interval_s"]:
        findings.append(Finding(
            "warning", "retention",
            f"no pattern interrupt in the final {timeline.total - last:.0f}s",
            at_s=last))

    # promised reveals should pay off with a visual (card) soon after
    for s in shots:
        if PAYOFF_PATTERN.search(s.narration):
            window_end = s.start + r["payoff_window_s"]
            payoff = any(x.type == "diagram" and s.start <= x.start <= window_end
                         for x in shots)
            if not payoff:
                findings.append(Finding(
                    "suggestion", "retention",
                    f"shot {s.n} sets up a reveal ('{PAYOFF_PATTERN.search(s.narration).group(0)}') "
                    f"but no card/stat lands within {r['payoff_window_s']}s — "
                    f"give the payoff a visual", shot_n=s.n, at_s=s.start))

    return findings


# ── scoring + entry point ────────────────────────────────────────────────────

def _score(findings: list[Finding]) -> tuple[int, dict[str, int], int]:
    scores = {}
    for cat in _SCORED_CATEGORIES:
        score = 100
        for f in findings:
            if f.category != cat:
                continue
            score -= _PENALTY[f.severity]
            if f.severity == "strength":
                score = min(score + _BONUS, 100)
        scores[cat] = max(score, 0)
    overall = round(sum(scores.values()) / len(scores))
    risk = 0
    for f in findings:
        if f.category in ("hook", "pacing", "retention"):
            risk += {"critical": 20, "warning": 8, "suggestion": 2, "strength": -4}[f.severity]
    return overall, scores, min(max(risk, 0), 100)


def run(project_slug: str | None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    rules = load_rules(cfg)

    timeline, script_text = build_timeline(project, rules)
    print(f"Timeline: {len(timeline.shots)} shots, {timeline.total:.0f}s "
          f"({timeline.source})")

    findings: list[Finding] = []
    for analyze in ANALYZERS + [_retention]:
        findings.extend(analyze(timeline, script_text, rules))
    order = {"critical": 0, "warning": 1, "suggestion": 2, "strength": 3}
    findings.sort(key=lambda f: (order[f.severity], f.at_s if f.at_s is not None else 1e9))

    overall, scores, risk = _score(findings)
    report = CriticReport(overall=overall, retention_risk=risk,
                          category_scores=scores, findings=findings,
                          timeline=timeline)
    write_json(report, project / "timeline_report.json")
    write_markdown(report, project / "timeline_report.md")

    crit = report.by_severity("critical")
    warn = report.by_severity("warning")
    print(f"\nScore: {overall}/100  (retention risk {risk}/100)")
    print("  " + "  ".join(f"{k} {v}" for k, v in scores.items()))
    if crit:
        print(f"\n{len(crit)} CRITICAL:")
        for f in crit:
            print(f"  ! [{f.category}] {f.message}")
    print(f"{len(warn)} warning(s), "
          f"{len(report.by_severity('suggestion'))} suggestion(s), "
          f"{len(report.by_severity('strength'))} strength(s)")
    print(f"\nReport: {project / 'timeline_report.md'}")
    print("Revise script.md / shotlist.json and rerun, or proceed to `broll`.")
