"""Hook analysis: does the opening earn the next ten minutes?

Category "hook".
"""
from .models import Finding, ScriptDoc
from .rules import CLAIM_PATTERN, QUESTION_HOOK_PATTERN, URGENCY_PATTERN


def analyze(doc: ScriptDoc, research_text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    h = rules["hook"]
    window = doc.in_window(h["window_s"])
    if not doc.sentences:
        return findings

    # strongest claim placement
    best, best_hits = None, 0
    for s in doc.sentences:
        hits = len(CLAIM_PATTERN.findall(s.text))
        if hits > best_hits:
            best, best_hits = s, hits
    if best is not None:
        if best.start_s > h["window_s"]:
            m, sec = divmod(int(best.start_s), 60)
            findings.append(Finding(
                "warning", "hook",
                f"the script's strongest claim ('{best.text[:70]}…') sits at "
                f"~{m}:{sec:02d} — tease it inside the first {h['window_s']}s",
                at_s=best.start_s, section=best.section))
        else:
            findings.append(Finding(
                "strength", "hook",
                f"strongest claim lands at ~{best.start_s:.0f}s — the open leads "
                f"with stakes", at_s=best.start_s))

    # curiosity: a question or curiosity frame early
    early = doc.in_window(h["need_question_by_s"])
    if not any(QUESTION_HOOK_PATTERN.search(s.text) for s in early):
        findings.append(Finding(
            "warning", "hook",
            f"no question or curiosity frame in the first "
            f"{h['need_question_by_s']}s — give viewers something to want answered"))
    else:
        findings.append(Finding(
            "strength", "hook", "the open plants a question — curiosity engaged"))

    # urgency: why watch NOW
    urgency_zone = doc.in_window(h["urgency_window_s"])
    if not any(URGENCY_PATTERN.search(s.text) for s in urgency_zone):
        findings.append(Finding(
            "suggestion", "hook",
            f"nothing in the first {h['urgency_window_s']}s says why this matters "
            f"*now* — one line of present-tense stakes adds urgency"))

    # any claim at all inside the hook window
    if window and not any(CLAIM_PATTERN.search(s.text) for s in window):
        findings.append(Finding(
            "warning", "hook",
            f"the first {h['window_s']}s contain no concrete claim or number — "
            f"the hook is running on vibes"))

    return findings
