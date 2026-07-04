"""Report rendering: timeline_report.json (machines) + timeline_report.md
(the operator). The MD is the decision document: why the score is what it
is, and what to fix before spending generation credits.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import CriticReport

_SEVERITY_ORDER = ("critical", "warning", "suggestion", "strength")
_LABELS = {"critical": "Critical issues", "warning": "Warnings",
           "suggestion": "Suggestions", "strength": "Strengths"}


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def write_json(report: CriticReport, dest: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timing_source": report.timeline.source,
        "overall_score": report.overall,
        "retention_risk": report.retention_risk,
        "category_scores": report.category_scores,
        "findings": [f.to_dict() for f in report.findings],
        "timeline": [{
            "shot": s.n, "type": s.type, "template": s.template,
            "start_s": round(s.start, 1), "duration_s": round(s.duration, 1),
            "words": s.words, "wpm": round(s.wpm), "section": s.section,
        } for s in report.timeline.shots],
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(report: CriticReport, dest: Path) -> None:
    tl = report.timeline
    lines = [
        "# Timeline Critic Report",
        "",
        f"**Overall score: {report.overall}/100** · retention risk: "
        f"{report.retention_risk}/100 · runtime {_fmt_time(tl.total)} "
        f"({len(tl.shots)} shots, timing {tl.source})",
        "",
        "| Category | Score |",
        "|---|---|",
    ]
    for cat, score in report.category_scores.items():
        lines.append(f"| {cat} | {score}/100 |")
    lines.append("")

    for severity in _SEVERITY_ORDER:
        found = report.by_severity(severity)
        if severity in ("critical", "warning", "suggestion") or found:
            lines.append(f"## {_LABELS[severity]} ({len(found)})")
            lines.append("")
            if not found:
                lines.append("None.")
            for f in found:
                anchor = ""
                if f.at_s is not None:
                    anchor = f" `{_fmt_time(f.at_s)}`"
                elif f.shot_n is not None:
                    anchor = f" `shot {f.shot_n}`"
                lines.append(f"- **[{f.category}]**{anchor} {f.message}")
            lines.append("")

    lines += [
        "## Timeline",
        "",
        "| # | Type | Start | Dur | Words | wpm | Section |",
        "|---|------|-------|-----|-------|-----|---------|",
    ]
    for s in tl.shots:
        label = s.template or s.type
        lines.append(f"| {s.n} | {label} | {_fmt_time(s.start)} | {s.duration:.0f}s "
                     f"| {s.words} | {s.wpm:.0f} | {s.section or '—'} |")
    lines += [
        "",
        "> Durations are "
        + ("measured from the aligned voiceover." if tl.source == "timing.json"
           else "estimates from narration length — they firm up after `align`."),
        "> The critic only reports; revise script.md / shotlist.json and rerun "
        "`python pipeline.py critic` until the numbers look right.",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")
