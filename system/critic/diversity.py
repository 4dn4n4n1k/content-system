"""Visual diversity analysis: repetition of types, templates, prompts.

Emits findings in category "diversity".
"""
import re

from .models import Finding, Timeline


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def analyze(timeline: Timeline, script_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    d = rules["diversity"]
    shots = timeline.shots

    # ── same-type runs (ai/ai/ai/ai reads as wallpaper) ─────────────────────
    run: list = []
    for s in shots + [None]:
        if s is not None and (not run or s.type == run[-1].type):
            run.append(s)
            continue
        if len(run) > d["max_same_type_run"]:
            findings.append(Finding(
                "warning", "diversity",
                f"shots {run[0].n}–{run[-1].n}: {len(run)} consecutive "
                f"'{run[0].type}' shots — break the stream with a card, stat or meme",
                shot_n=run[0].n, at_s=run[0].start))
        run = [s] if s is not None else []

    # ── repeated diagram/meme templates ─────────────────────────────────────
    counts: dict[str, list] = {}
    for s in shots:
        if s.template:
            counts.setdefault(s.template, []).append(s)
    for template, used in counts.items():
        if len(used) > d["max_template_repeats"]:
            findings.append(Finding(
                "warning", "diversity",
                f"template '{template}' appears {len(used)} times "
                f"(shots {', '.join(str(s.n) for s in used)}) — vary the card designs",
                shot_n=used[0].n))

    # ── meme budget + adjacency ─────────────────────────────────────────────
    memes = [s for s in shots if s.type == "meme"]
    if len(memes) > d["max_memes"]:
        findings.append(Finding(
            "warning", "diversity",
            f"{len(memes)} memes in one video (max {d['max_memes']}) — "
            f"they stop landing when overused"))
    for a, b in zip(shots, shots[1:]):
        if a.type == "meme" and b.type == "meme":
            findings.append(Finding(
                "critical", "diversity",
                f"shots {a.n} and {b.n} are back-to-back memes — never stack them",
                shot_n=a.n, at_s=a.start))

    # ── near-duplicate prompts/queries ──────────────────────────────────────
    visual = [s for s in shots if s.type in ("ai", "stock") and s.visual_text]
    for a, b in zip(visual, visual[1:]):
        ta, tb = _tokens(a.visual_text), _tokens(b.visual_text)
        if ta and tb:
            jaccard = len(ta & tb) / len(ta | tb)
            if jaccard >= d["similar_prompt_jaccard"]:
                findings.append(Finding(
                    "suggestion", "diversity",
                    f"shots {a.n} and {b.n} have near-identical visuals "
                    f"({jaccard:.0%} overlap) — differentiate angle, subject or scale",
                    shot_n=a.n, at_s=a.start))

    # ── overall variety ─────────────────────────────────────────────────────
    kinds = {s.type for s in shots}
    if len(shots) >= 8 and len(kinds) < 3:
        findings.append(Finding(
            "warning", "diversity",
            f"only {len(kinds)} shot type(s) across {len(shots)} shots — "
            f"mix in {'diagrams/stats' if 'diagram' not in kinds else 'b-roll variety'}"))
    elif len(kinds) >= 3:
        findings.append(Finding(
            "strength", "diversity",
            f"{len(kinds)} distinct shot types across {len(shots)} shots — good mix"))

    return findings
