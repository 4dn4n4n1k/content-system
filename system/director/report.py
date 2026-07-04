"""Report rendering: creative_report.json + creative_report.md.

The MD is written for the operator deciding whether to revise the script
before shot-list work begins.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import DirectorReport

_LABELS = {"critical": "Critical", "warning": "Weaknesses",
           "suggestion": "Recommendations", "strength": "Strengths"}


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def write_json(report: DirectorReport, dest: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall_score": report.overall,
        "category_scores": report.category_scores,
        "est_duration_s": round(report.doc.est_duration, 1),
        "total_words": report.doc.total_words,
        "sections": [s.name for s in report.doc.sections if s.name],
        "findings": [f.to_dict() for f in report.findings],
        "visual_opportunities": [o.to_dict() for o in report.visual_ops],
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(report: DirectorReport, dest: Path) -> None:
    doc = report.doc
    lines = [
        "# Creative Director Report",
        "",
        f"**Overall creative score: {report.overall}/100** · {doc.total_words} words "
        f"≈ {_fmt_time(doc.est_duration)} runtime · "
        f"{len([s for s in doc.sections if s.name])} chapters",
        "",
        "| Category | Score |",
        "|---|---|",
    ]
    for cat, score in report.category_scores.items():
        lines.append(f"| {cat} | {score}/100 |")
    lines.append("")

    strengths = report.by_severity("strength")
    lines += [f"## Strengths ({len(strengths)})", ""]
    lines += [f"- **[{f.category}]** {f.message}" for f in strengths] or ["None found."]
    lines.append("")

    weaknesses = report.by_severity("critical") + report.by_severity("warning")
    lines += [f"## Weaknesses ({len(weaknesses)})", ""]
    if not weaknesses:
        lines.append("None.")
    for f in weaknesses:
        tag = "❗ " if f.severity == "critical" else ""
        lines.append(f"- {tag}**[{f.category}]** `{_fmt_time(f.at_s)}` {f.message}")
    lines.append("")

    recs = report.by_severity("suggestion")
    lines += [f"## High-impact recommendations ({len(recs)})", ""]
    if not recs:
        lines.append("None.")
    for f in recs:
        lines.append(f"- **[{f.category}]** `{_fmt_time(f.at_s)}` {f.message}")
    lines.append("")

    lines += [
        f"## Visual opportunities ({len(report.visual_ops)})",
        "",
        "| When | Kind | Conf | Why | Trigger |",
        "|------|------|------|-----|---------|",
    ]
    for o in report.visual_ops:
        lines.append(f"| {_fmt_time(o.at_s)} | {o.kind} | {o.confidence:.0%} "
                     f"| {o.rationale} | {o.trigger[:60]}… |")
    lines.append("")

    retention = [f for f in report.findings
                 if f.category in ("hook", "curiosity", "emotion")
                 and f.severity in ("critical", "warning")]
    lines += [f"## Retention opportunities ({len(retention)})", ""]
    if not retention:
        lines.append("The hook/curiosity/emotion signals look healthy.")
    for f in retention:
        lines.append(f"- `{_fmt_time(f.at_s)}` {f.message}")
    lines += [
        "",
        "> Timestamps are estimates at the configured speech rate; they shift "
        "slightly after voiceover alignment.",
        "> The director only recommends — edit script.md yourself, rerun "
        "`python pipeline.py director`, then move on to the shot list.",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")
