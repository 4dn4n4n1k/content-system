"""Visual potential: where the script is asking for a specific visual.

Emits VisualOpportunity records (each with a confidence rating) plus
category-"visuals" findings for visually dry sections. The opportunity kinds
map 1:1 onto what the pipeline can already produce (cards, memes, b-roll),
so the shot-list stage can consume the report directly.
"""
import re

from .models import Finding, ScriptDoc, VisualOpportunity
from .rules import (COMPARISON_PATTERN, IRONY_PATTERN, NUMBER_PATTERN,
                    PROCESS_PATTERN, QUOTE_PATTERN, SEQUENCE_PATTERN,
                    SERIOUS_PATTERN, YEAR_PATTERN)

try:  # concrete-scenery vocabulary shared with the Asset Intelligence planner
    from ..intelligence.planner import SYNONYMS as _SCENERY
except ImportError:
    _SCENERY = {}

_BIG_NUMBER = re.compile(
    r"\d[\d,.]*\s*(?:%|percent|billion|million|thousand|dollars|\$)"
    r"|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|a|half a)\s+"
    r"(?:billion|million|trillion|thousand)\b|\b(?:billions|millions|trillions)\s+of\b",
    re.IGNORECASE)


def analyze_opportunities(doc: ScriptDoc, rules: dict) -> list[VisualOpportunity]:
    ops: list[VisualOpportunity] = []
    for s in doc.sentences:
        text = s.text

        if _BIG_NUMBER.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "stat_card", text, 0.9,
                "a headline number lands harder on screen than in the ear"))
        elif len(NUMBER_PATTERN.findall(text)) >= 2:
            ops.append(VisualOpportunity(
                s.start_s, s.section, "stat_card", text, 0.65,
                "multiple figures in one breath — visualize to reduce load"))

        if COMPARISON_PATTERN.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "comparison", text, 0.7,
                "explicit A-vs-B framing — split-screen or two-column card"))

        if len(YEAR_PATTERN.findall(text)) >= 2:
            ops.append(VisualOpportunity(
                s.start_s, s.section, "timeline", text, 0.8,
                "multiple dates — a timeline shows the progression at a glance"))
        elif SEQUENCE_PATTERN.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "list", text, 0.75,
                "enumerated steps — a staggered list card tracks them"))

        if QUOTE_PATTERN.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "quote_card", text, 0.8,
                "attributed statement — quote card adds authority"))

        if PROCESS_PATTERN.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "diagram", text, 0.8,
                "a mechanism is being explained — diagram the flow"))

        if IRONY_PATTERN.search(text) and not SERIOUS_PATTERN.search(text):
            ops.append(VisualOpportunity(
                s.start_s, s.section, "meme", text, 0.6,
                "ironic beat — a meme would land here (respect the meme rules)"))

        scenery = [w for w in _SCENERY if re.search(rf"\b{re.escape(w)}\b",
                                                    text.lower())]
        if scenery:
            ops.append(VisualOpportunity(
                s.start_s, s.section, "broll", text, 0.6,
                f"concrete imagery ({', '.join(scenery[:3])}) — natural b-roll"))

    min_conf = rules["visuals"]["min_confidence"]
    deduped: dict[tuple, VisualOpportunity] = {}
    for op in ops:
        if op.confidence < min_conf:
            continue
        key = (round(op.at_s), op.kind)
        if key not in deduped or op.confidence > deduped[key].confidence:
            deduped[key] = op
    return sorted(deduped.values(), key=lambda o: o.at_s)


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    """Findings only — dry sections with nothing to show."""
    findings: list[Finding] = []
    ops = analyze_opportunities(doc, rules)
    for sec in doc.sections:
        if sec.words < rules["visuals"]["dry_section_min_words"]:
            continue
        end = sec.start_s + sec.words / rules["wpm"] * 60
        inside = [o for o in ops if sec.start_s <= o.at_s < end]
        if not inside:
            findings.append(Finding(
                "warning", "visuals",
                f"section '{sec.name or 'untitled'}' offers nothing concrete to "
                f"show — {sec.words} words of pure narration will be wallpaper "
                f"b-roll. Add a number, example or comparison",
                at_s=sec.start_s, section=sec.name))
    if ops and not findings:
        findings.append(Finding(
            "strength", "visuals",
            f"{len(ops)} visual opportunities spread across the script"))
    return findings
