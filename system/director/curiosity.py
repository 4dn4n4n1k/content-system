"""Curiosity analysis: open loops, resolutions, missed research, early reveals.

Category "curiosity".
"""
import re

from .models import Finding, ScriptDoc
from .rules import CALLBACK_PATTERN, CLAIM_PATTERN, PAYOFF_PATTERN

_WORD_RE = re.compile(r"[a-z]{4,}")


def _topic(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    cu = rules["curiosity"]
    if not doc.sentences:
        return findings
    total = doc.est_duration or 1.0

    # ── open loops: explicit promises + genuine questions ───────────────────
    tail_start = total * cu["resolve_search_share"]
    tail_text = " ".join(s.text for s in doc.sentences if s.start_s >= tail_start)
    tail_topics = _topic(tail_text)

    loops = []
    for s in doc.sentences:
        if CALLBACK_PATTERN.search(s.text) or (s.text.strip().endswith("?")
                                               and s.start_s < tail_start):
            loops.append(s)
    resolved = unresolved = 0
    for s in loops:
        overlap = _topic(s.text) & tail_topics
        if overlap:
            resolved += 1
        else:
            unresolved += 1
            findings.append(Finding(
                "warning", "curiosity",
                f"open loop at ~{s.start_s:.0f}s ('{s.text[:60]}…') never comes "
                f"back in the second half — resolve it or cut the promise",
                at_s=s.start_s, section=s.section))
    if resolved:
        findings.append(Finding(
            "strength", "curiosity",
            f"{resolved} open loop(s) planted and later resolved — good tension"))
    if not loops and total > 240:
        findings.append(Finding(
            "warning", "curiosity",
            "no open loops anywhere — nothing pulls the viewer through the "
            "middle. Plant at least one early promise"))

    # ── premature reveals ───────────────────────────────────────────────────
    early_cutoff = total * cu["early_share"]
    first_loop_at = min((s.start_s for s in loops), default=None)
    for s in doc.sentences:
        if s.start_s <= early_cutoff and PAYOFF_PATTERN.search(s.text):
            if first_loop_at is None or s.start_s < first_loop_at:
                findings.append(Finding(
                    "suggestion", "curiosity",
                    f"reveal at ~{s.start_s:.0f}s ('{s.text[:60]}…') before any "
                    f"question was planted — tease first, pay off second",
                    at_s=s.start_s, section=s.section))

    # ── missed opportunities from research ──────────────────────────────────
    if research_text:
        script_numbers = set(re.findall(r"\d[\d,.]*", " ".join(
            s.text for s in doc.sentences)))
        unused = []
        for line in research_text.splitlines():
            for m in CLAIM_PATTERN.finditer(line):
                nums = re.findall(r"\d[\d,.]*", m.group(0))
                if nums and not (set(nums) & script_numbers):
                    unused.append(line.strip().lstrip("-• ")[:80])
                    break
        for item in dict.fromkeys(unused[:3]):
            findings.append(Finding(
                "suggestion", "curiosity",
                f"research has an unused stat: '{item}…' — strong claims like "
                f"this are hook/loop material"))

    return findings
