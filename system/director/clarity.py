"""Clarity analysis: sentence complexity, jargon, abstraction, cognitive load.

Category "clarity".
"""
import re

from .models import Finding, ScriptDoc
from .rules import ABSTRACT_SUFFIXES, EXPLAINER_PATTERN, JARGON_TERMS, NUMBER_PATTERN

_WORD_RE = re.compile(r"[a-zA-Z0-9'-]+")


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    c = rules["clarity"]
    if not doc.sentences:
        return findings

    # ── sentence complexity ─────────────────────────────────────────────────
    long_ones = [s for s in doc.sentences if s.words > c["long_sentence_words"]]
    share = len(long_ones) / len(doc.sentences)
    if share > c["max_long_sentence_share"]:
        worst = max(long_ones, key=lambda s: s.words)
        findings.append(Finding(
            "warning", "clarity",
            f"{share:.0%} of sentences exceed {c['long_sentence_words']} words "
            f"(worst: {worst.words} words at ~{worst.start_s:.0f}s) — spoken "
            f"delivery needs shorter breaths", at_s=worst.start_s))
    elif long_ones:
        for s in long_ones[:2]:
            findings.append(Finding(
                "suggestion", "clarity",
                f"{s.words}-word sentence ('{s.text[:60]}…') — split it for the ear",
                at_s=s.start_s, section=s.section))
    else:
        findings.append(Finding(
            "strength", "clarity", "sentence lengths are consistently speakable"))

    # ── unexplained terminology (first use without a nearby explainer) ──────
    explained: set[str] = set()
    flagged: set[str] = set()
    for i, s in enumerate(doc.sentences):
        lowered = s.text.lower()
        for term in JARGON_TERMS:
            if term in flagged or term in explained:
                continue
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                context = " ".join(x.text for x in doc.sentences[max(0, i - 1):i + 2])
                if EXPLAINER_PATTERN.search(context):
                    explained.add(term)
                else:
                    flagged.add(term)
                    findings.append(Finding(
                        "suggestion", "clarity",
                        f"'{term}' first appears at ~{s.start_s:.0f}s with no "
                        f"plain-language gloss — one clause keeps casual viewers on board",
                        at_s=s.start_s, section=s.section))

    # ── excessive abstraction ───────────────────────────────────────────────
    for s in doc.sentences:
        tokens = _WORD_RE.findall(s.text.lower())
        if len(tokens) < 12:
            continue
        abstract = sum(1 for t in tokens if t.endswith(ABSTRACT_SUFFIXES))
        if abstract / len(tokens) > c["abstract_density"]:
            findings.append(Finding(
                "suggestion", "clarity",
                f"abstract-heavy sentence at ~{s.start_s:.0f}s "
                f"('{s.text[:60]}…') — swap concepts for concrete images",
                at_s=s.start_s, section=s.section))

    # ── cognitive load: number-dense sentences ──────────────────────────────
    for s in doc.sentences:
        numbers = NUMBER_PATTERN.findall(s.text)
        if len(numbers) > c["max_numbers_per_sentence"]:
            findings.append(Finding(
                "warning", "clarity",
                f"{len(numbers)} numbers in one sentence at ~{s.start_s:.0f}s — "
                f"listeners can hold about two; give the rest to a stat card",
                at_s=s.start_s, section=s.section))

    return findings
