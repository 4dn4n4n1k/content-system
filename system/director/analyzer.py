"""Creative Director orchestrator.

Parses script.md into a ScriptDoc (sections → sentences with estimated
timestamps), runs every registered analyzer plus the visual-opportunity
scan, scores the result, and writes creative_report.{json,md}.

Plugin registry — same pattern as the Timeline Critic: an analyzer is any
callable `(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]`
added via `register()`. A future LLM creative reviewer registers itself and
neither this module nor report.py changes.

Read-only by contract: never edits script.md or research.md.
"""
import re
import sys
from pathlib import Path

from ..util import load_config, resolve_project
from . import clarity, curiosity, emotion, hook, visuals
from . import narrative as narrative_mod
from .models import DirectorReport, Finding, ScriptDoc, Section, Sentence
from .report import write_json, write_markdown
from .rules import load_rules

MARKER_RE = re.compile(r"\[SHOT\s+\d+\]", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

_SCORED = ("hook", "narrative", "clarity", "emotion", "curiosity", "visuals")
_PENALTY = {"critical": 25, "warning": 10, "suggestion": 3, "strength": 0}
_BONUS = 3

ANALYZERS = [hook.analyze, narrative_mod.analyze, clarity.analyze,
             emotion.analyze, curiosity.analyze, visuals.analyze]


def register(analyzer) -> None:
    """Add a creative reviewer plugin (e.g. a future LLM reviewer)."""
    ANALYZERS.append(analyzer)


def build_doc(script_path: Path, wpm: int) -> ScriptDoc:
    sections: list[Section] = []
    sentences: list[Sentence] = []
    current = Section(name="", start_s=0.0, words=0)
    cursor_words = 0
    index = 0

    for line in script_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current.sentences or current.name:
                sections.append(current)
            current = Section(name=stripped.lstrip("#").strip(),
                              start_s=cursor_words / wpm * 60, words=0)
            continue
        if stripped.startswith(("<!--", ">")) or not stripped:
            continue
        text = MARKER_RE.sub(" ", stripped).strip()
        if not text:
            continue
        for raw in SENTENCE_RE.split(text):
            raw = raw.strip()
            if not raw:
                continue
            words = len(raw.split())
            s = Sentence(index=index, text=raw, words=words,
                         start_s=cursor_words / wpm * 60, section=current.name)
            index += 1
            cursor_words += words
            current.words += words
            current.sentences.append(s)
            sentences.append(s)
    if current.sentences or current.name:
        sections.append(current)

    return ScriptDoc(sections=sections, sentences=sentences,
                     total_words=cursor_words,
                     est_duration=cursor_words / wpm * 60)


def _score(findings: list[Finding]) -> tuple[int, dict[str, int]]:
    scores = {}
    for cat in _SCORED:
        score = 100
        for f in findings:
            if f.category != cat:
                continue
            score -= _PENALTY[f.severity]
            if f.severity == "strength":
                score = min(score + _BONUS, 100)
        scores[cat] = max(score, 0)
    return round(sum(scores.values()) / len(scores)), scores


def run(project_slug: str | None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    rules = load_rules(cfg)

    script_path = project / "script.md"
    if not script_path.exists():
        sys.exit(f"Missing {script_path} — the director reviews the script.")
    research_path = project / "research.md"
    research_text = research_path.read_text(encoding="utf-8") if research_path.exists() else ""
    if not research_text:
        print("  note: no research.md — skipping unused-research checks")

    doc = build_doc(script_path, rules["wpm"])
    print(f"Script: {doc.total_words} words ~ {doc.est_duration / 60:.1f} min, "
          f"{len([s for s in doc.sections if s.name])} chapter(s)")

    findings: list[Finding] = []
    for analyze in ANALYZERS:
        findings.extend(analyze(doc, research_text, rules))
    order = {"critical": 0, "warning": 1, "suggestion": 2, "strength": 3}
    findings.sort(key=lambda f: (order[f.severity],
                                 f.at_s if f.at_s is not None else 1e9))
    visual_ops = visuals.analyze_opportunities(doc, rules)

    overall, scores = _score(findings)
    report = DirectorReport(overall=overall, category_scores=scores,
                            findings=findings, visual_ops=visual_ops, doc=doc)
    write_json(report, project / "creative_report.json")
    write_markdown(report, project / "creative_report.md")

    crit = report.by_severity("critical")
    warn = report.by_severity("warning")
    print(f"\nCreative score: {overall}/100")
    print("  " + "  ".join(f"{k} {v}" for k, v in scores.items()))
    if crit:
        print(f"\n{len(crit)} CRITICAL:")
        for f in crit:
            print(f"  ! [{f.category}] {f.message}")
    print(f"{len(warn)} weakness(es), {len(report.by_severity('suggestion'))} "
          f"recommendation(s), {len(visual_ops)} visual opportunit(ies)")
    print(f"\nReport: {project / 'creative_report.md'}")
    print("Revise script.md and rerun, or move on to the shot list.")
