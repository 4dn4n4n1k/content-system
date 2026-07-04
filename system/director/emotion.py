"""Emotional progression: tension/relief arc across sections.

Category "emotion".
"""
import re

from .models import Finding, ScriptDoc
from .rules import RELIEF_WORDS, TENSION_WORDS

_WORD_RE = re.compile(r"[a-z']+")


def _densities(text: str) -> tuple[float, float, int]:
    words = _WORD_RE.findall(text.lower())
    if not words:
        return 0.0, 0.0, 0
    tension = sum(1 for w in words if w in TENSION_WORDS)
    relief = sum(1 for w in words if w in RELIEF_WORDS)
    return tension / len(words), relief / len(words), len(words)


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    e = rules["emotion"]
    sections = [s for s in doc.sections if s.words >= 40] or doc.sections
    if not sections:
        return findings

    profile = []
    for sec in sections:
        text = " ".join(x.text for x in sec.sentences)
        tension, relief, _ = _densities(text)
        profile.append((sec, tension, relief))

    # flat sections: no emotional language at all
    for sec, tension, relief in profile:
        if sec.words >= 60 and tension + relief < e["flat_density"]:
            findings.append(Finding(
                "suggestion", "emotion",
                f"section '{sec.name or 'untitled'}' is emotionally flat — "
                f"no stakes, no relief, just information", at_s=sec.start_s,
                section=sec.name))

    # abrupt tension jumps between adjacent sections
    for (a, ta, _), (b, tb, _) in zip(profile, profile[1:]):
        if abs(tb - ta) > e["abrupt_delta"]:
            direction = "spikes" if tb > ta else "collapses"
            findings.append(Finding(
                "suggestion", "emotion",
                f"tension {direction} between '{a.name or 'untitled'}' and "
                f"'{b.name or 'untitled'}' — add a bridging beat so the shift "
                f"feels intentional", at_s=b.start_s, section=b.name))

    # overall arc
    full_tension, full_relief, _ = _densities(
        " ".join(s.text for s in doc.sentences))
    if full_tension < e["min_overall_tension"]:
        findings.append(Finding(
            "warning", "emotion",
            "overall tension is low for this genre — the viewer never feels "
            "the threat. Raise the stakes in at least one section"))
    elif full_relief == 0.0:
        findings.append(Finding(
            "suggestion", "emotion",
            "wall-to-wall tension with no relief — give viewers one breather "
            "or win so the next spike lands harder"))
    else:
        findings.append(Finding(
            "strength", "emotion", "the script has both tension and release"))

    return findings
