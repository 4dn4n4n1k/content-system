"""Pacing + hook analysis: shot lengths, slow runs, narration density.

Emits findings in categories "hook" and "pacing".
"""
from .models import Finding, Timeline


def analyze(timeline: Timeline, script_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    hook, pacing = rules["hook"], rules["pacing"]

    # ── hook window ─────────────────────────────────────────────────────────
    hook_shots = timeline.in_window(hook["window_s"])
    if len(hook_shots) < hook["min_shots"]:
        findings.append(Finding(
            "warning", "hook",
            f"only {len(hook_shots)} shot(s) in the first {hook['window_s']}s — "
            f"the opening needs at least {hook['min_shots']} cuts to feel alive"))
    else:
        findings.append(Finding(
            "strength", "hook",
            f"{len(hook_shots)} cuts inside the first {hook['window_s']}s — lively open"))
    for s in hook_shots:
        if s.duration > hook["max_shot_s"]:
            findings.append(Finding(
                "critical", "hook",
                f"shot {s.n} holds {s.duration:.0f}s inside the hook "
                f"(max {hook['max_shot_s']}s) — early drop-off risk",
                shot_n=s.n, at_s=s.start))
        if s.type == "meme" and s.start < hook["no_meme_before_s"]:
            findings.append(Finding(
                "critical", "hook",
                f"shot {s.n} is a meme at {s.start:.0f}s — memes before "
                f"{hook['no_meme_before_s']}s undercut the hook",
                shot_n=s.n, at_s=s.start))

    # ── shot-length dead zones ──────────────────────────────────────────────
    for s in timeline.shots:
        if s.duration > pacing["max_shot_s"]:
            findings.append(Finding(
                "warning", "pacing",
                f"shot {s.n} runs {s.duration:.0f}s (> {pacing['max_shot_s']}s) — "
                f"split it or add motion", shot_n=s.n, at_s=s.start))

    # ── consecutive slow shots ──────────────────────────────────────────────
    run: list = []
    for s in timeline.shots + [None]:
        if s is not None and s.duration >= pacing["slow_shot_s"]:
            run.append(s)
            continue
        if len(run) > pacing["max_consecutive_slow"]:
            findings.append(Finding(
                "warning", "pacing",
                f"shots {run[0].n}–{run[-1].n}: {len(run)} slow shots in a row "
                f"(each ≥ {pacing['slow_shot_s']}s) — pacing sags here",
                shot_n=run[0].n, at_s=run[0].start))
        run = []

    # ── narration density ───────────────────────────────────────────────────
    for s in timeline.shots:
        if s.words < 8:  # tiny segments give meaningless rates
            continue
        if s.wpm > pacing["max_wpm"]:
            findings.append(Finding(
                "warning", "pacing",
                f"shot {s.n} narrates at ~{s.wpm:.0f} wpm — information overload, "
                f"give the viewer a beat", shot_n=s.n, at_s=s.start))
        elif s.wpm < pacing["min_wpm"]:
            findings.append(Finding(
                "suggestion", "pacing",
                f"shot {s.n} narrates at ~{s.wpm:.0f} wpm — consider tightening "
                f"the script here", shot_n=s.n, at_s=s.start))

    return findings
