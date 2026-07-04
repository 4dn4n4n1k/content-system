"""Narrative analysis: claim placement, visual↔narration match, sections,
callbacks, emotional consistency.

Emits findings in categories "hook" and "narrative".
"""
import re

from .models import Finding, Timeline
from .rules import CALLBACK_PATTERN, CLAIM_PATTERN, SERIOUS_PATTERN

try:  # reuse the planner's style vocabulary for emotion/lighting words
    from ..intelligence.planner import CATEGORIES as STYLE_VOCAB
except ImportError:  # critic stays usable standalone
    STYLE_VOCAB = {"emotion": set(), "lighting": set()}

_DARK = {"dark", "moody", "ominous", "tense", "chaotic", "neon", "red"}
_LIGHT = {"bright", "hopeful", "calm", "sleek"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def analyze(timeline: Timeline, script_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    shots = timeline.shots

    # ── strongest claim placement (hook) ────────────────────────────────────
    best, best_hits = None, 0
    for s in shots:
        hits = len(CLAIM_PATTERN.findall(s.narration))
        if hits > best_hits:
            best, best_hits = s, hits
    if best is not None:
        if best.start > rules["hook"]["window_s"]:
            m, sec = divmod(int(best.start), 60)
            findings.append(Finding(
                "warning", "hook",
                f"the strongest claim ({best_hits} signal(s)) lands at {m}:{sec:02d} "
                f"in shot {best.n} — tease a version of it inside the first "
                f"{rules['hook']['window_s']}s", shot_n=best.n, at_s=best.start))
        else:
            findings.append(Finding(
                "strength", "hook",
                f"strongest claim sits at {best.start:.0f}s (shot {best.n}) — "
                f"hook leads with stakes", shot_n=best.n))

    # ── visual ↔ narration mismatch ─────────────────────────────────────────
    for s in shots:
        if s.type not in ("ai", "stock") or not s.visual_text or s.words < 10:
            continue
        overlap = _words(s.narration) & _words(s.visual_text)
        if not overlap:
            findings.append(Finding(
                "suggestion", "narrative",
                f"shot {s.n}: visual ('{s.visual_text[:40]}…') shares no keywords "
                f"with its narration — intentional contrast or a mismatch?",
                shot_n=s.n, at_s=s.start))

    # ── chapter transitions ─────────────────────────────────────────────────
    prev_section = shots[0].section if shots else ""
    for i, s in enumerate(shots):
        if s.section != prev_section:
            near = [shots[j] for j in (i - 1, i) if 0 <= j < len(shots)]
            if not any(x.type == "diagram" for x in near):
                findings.append(Finding(
                    "suggestion", "narrative",
                    f"section change at shot {s.n} ('{s.section or 'untitled'}') has "
                    f"no card marking it — a title card would signpost the chapter",
                    shot_n=s.n, at_s=s.start))
            prev_section = s.section

    # ── unresolved callbacks ────────────────────────────────────────────────
    for s in shots:
        for m in CALLBACK_PATTERN.finditer(s.narration):
            tail = " ".join(x.narration for x in shots if x.start > timeline.total * 0.6)
            context = _words(s.narration[max(0, m.start() - 80):m.end() + 80])
            if context and not (context & _words(tail)):
                findings.append(Finding(
                    "warning", "narrative",
                    f"shot {s.n} promises '{m.group(0)}' but its topic words never "
                    f"reappear in the last 40% of the video — unresolved callback",
                    shot_n=s.n, at_s=s.start))

    # ── emotional consistency ───────────────────────────────────────────────
    for s in shots:
        if s.type == "meme" and SERIOUS_PATTERN.search(s.narration):
            findings.append(Finding(
                "critical", "narrative",
                f"shot {s.n} places a meme over serious subject matter "
                f"('{SERIOUS_PATTERN.search(s.narration).group(0)}') — tonal clash",
                shot_n=s.n, at_s=s.start))
    for a, b in zip(shots, shots[1:]):
        mood_a, mood_b = _words(a.visual_text) & _DARK, _words(b.visual_text) & _LIGHT
        if mood_a and mood_b and b.type in ("ai", "stock") and a.type in ("ai", "stock"):
            findings.append(Finding(
                "suggestion", "narrative",
                f"shots {a.n}→{b.n} flip mood ({'/'.join(sorted(mood_a))} → "
                f"{'/'.join(sorted(mood_b))}) with no transition between them",
                shot_n=b.n, at_s=b.start))

    return findings
