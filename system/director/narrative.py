"""Narrative analysis: structure, repetition, information flow, payoffs.

Category "narrative".
"""
import re
from collections import Counter

from .models import Finding, ScriptDoc
from .rules import CLAIM_PATTERN, PAYOFF_PATTERN

_WORD_RE = re.compile(r"[a-z']+")


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    n = rules["narrative"]

    # ── section progression ─────────────────────────────────────────────────
    real_sections = [s for s in doc.sections if s.name]
    if doc.total_words > 400 and len(real_sections) < 2:
        findings.append(Finding(
            "warning", "narrative",
            "the script has no chapter structure (headings) — long-form needs "
            "visible progression the viewer can feel"))
    for sec in real_sections:
        share = sec.words / doc.total_words if doc.total_words else 0
        if share > n["max_section_share"]:
            findings.append(Finding(
                "suggestion", "narrative",
                f"section '{sec.name}' is {share:.0%} of the script — consider "
                f"splitting it", at_s=sec.start_s, section=sec.name))

    # ── repetition: repeated phrases and overused words ─────────────────────
    words = _WORD_RE.findall(" ".join(s.text.lower() for s in doc.sentences))
    ngrams = Counter(tuple(words[i:i + n["ngram"]])
                     for i in range(len(words) - n["ngram"]))
    for gram, count in ngrams.items():
        if count >= 3 and len(set(gram)) > 2:
            findings.append(Finding(
                "warning", "narrative",
                f"the phrase '{' '.join(gram)}' appears {count} times — vary it"))
    content = Counter(w for w in words if len(w) > 5)
    for word, count in content.most_common(3):
        if doc.total_words and count / doc.total_words > 0.012 and count >= 6:
            findings.append(Finding(
                "suggestion", "narrative",
                f"'{word}' is used {count} times — swap in synonyms where it repeats"))

    # ── information flow: stat dumps and dry stretches ──────────────────────
    claim_times = [s.start_s for s in doc.sentences if CLAIM_PATTERN.search(s.text)]
    for i, t in enumerate(claim_times):
        cluster = [x for x in claim_times if t <= x < t + n["claim_cluster_window_s"]]
        if len(cluster) > n["claim_cluster_max"]:
            m, sec = divmod(int(t), 60)
            findings.append(Finding(
                "warning", "narrative",
                f"{len(cluster)} claims/stats packed into the minute after "
                f"{m}:{sec:02d} — space them out or visualize the dump", at_s=t))
            break  # one flag per script is enough
    prev = 0.0
    for t in claim_times + [doc.est_duration]:
        if t - prev > n["dry_stretch_s"] and doc.est_duration > n["dry_stretch_s"]:
            m, sec = divmod(int(prev), 60)
            findings.append(Finding(
                "suggestion", "narrative",
                f"~{t - prev:.0f}s after {m}:{sec:02d} passes without a concrete "
                f"fact or claim — the middle needs fuel too", at_s=prev))
        prev = t

    # ── payoff timing ───────────────────────────────────────────────────────
    payoffs = [s for s in doc.sentences if PAYOFF_PATTERN.search(s.text)]
    if payoffs:
        first = min(p.start_s for p in payoffs)
        if doc.est_duration and first / doc.est_duration > n["payoff_backload_share"]:
            findings.append(Finding(
                "warning", "narrative",
                f"every payoff sits in the final "
                f"{100 - int(n['payoff_backload_share'] * 100)}% — drip value "
                f"earlier or viewers won't stay for the finale", at_s=first))
        else:
            findings.append(Finding(
                "strength", "narrative",
                f"{len(payoffs)} payoff beat(s) distributed through the script"))
    return findings
