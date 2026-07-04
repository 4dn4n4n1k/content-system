"""Transition recommendations: where a cut deserves more than a hard cut.

Recommendation-only by design — nothing here changes the shot list or the
assembler. All findings are category "transitions", severity "suggestion".
"""
from .models import Finding, Timeline


def analyze(timeline: Timeline, script_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    t = rules["transitions"]
    shots = timeline.shots

    # zoom punches inside long b-roll holds
    for s in shots:
        if s.type in ("ai", "stock") and s.duration >= t["long_shot_s"]:
            findings.append(Finding(
                "suggestion", "transitions",
                f"shot {s.n} holds {s.duration:.0f}s — a zoom punch around "
                f"{s.start + s.duration / 2:.0f}s would re-energize it",
                shot_n=s.n, at_s=s.start))

    # whip transitions between back-to-back b-roll of the same type
    for a, b in zip(shots, shots[1:]):
        if (a.type == b.type and a.type in ("ai", "stock")
                and a.duration >= t["long_shot_s"] and b.duration >= t["long_shot_s"]):
            findings.append(Finding(
                "suggestion", "transitions",
                f"shots {a.n}→{b.n}: two long {a.type} holds — a whip transition "
                f"would hide the seam and add motion", shot_n=b.n, at_s=b.start))

    # diagram reveals: give stat/diagram cards a breath before the cut
    for a, b in zip(shots, shots[1:]):
        if b.type == "diagram" and a.type in ("ai", "stock"):
            findings.append(Finding(
                "suggestion", "transitions",
                f"shot {b.n} is a card after b-roll — a half-beat pause before the "
                f"cut makes the reveal land harder", shot_n=b.n, at_s=b.start))

    # title cards at section changes that have no card nearby
    prev = shots[0].section if shots else ""
    for i, s in enumerate(shots):
        if s.section != prev:
            near = [shots[j] for j in (i - 1, i) if 0 <= j < len(shots)]
            if not any(x.type == "diagram" and (x.template or "") == "title_card"
                       for x in near):
                findings.append(Finding(
                    "suggestion", "transitions",
                    f"a title card at shot {s.n} would open "
                    f"'{s.section or 'the next chapter'}' cleanly",
                    shot_n=s.n, at_s=s.start))
            prev = s.section

    # chapter separators on long stretches without any section change
    if shots:
        last_break = 0.0
        first_section = shots[0].section
        for s in shots:
            if s.section != first_section:
                last_break = max(last_break, s.start)
        if timeline.total - last_break > t["chapter_gap_s"]:
            findings.append(Finding(
                "suggestion", "transitions",
                f"{timeline.total - last_break:.0f}s since the last chapter break — "
                f"consider a separator card in the back half"))

    return findings
