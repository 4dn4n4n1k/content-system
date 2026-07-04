"""Data model for the Timeline Critic.

The critic never mutates project files — these types describe the timeline
as-is and what the analyzers think of it.
"""
from dataclasses import dataclass, field

SEVERITIES = ("critical", "warning", "suggestion", "strength")
CATEGORIES = ("hook", "pacing", "diversity", "narrative", "retention", "transitions")


@dataclass
class Finding:
    severity: str                   # critical | warning | suggestion | strength
    category: str                   # hook | pacing | diversity | narrative | retention | transitions
    message: str
    shot_n: int | None = None       # anchor shot, when the finding is local
    at_s: float | None = None       # anchor time on the estimated timeline

    def to_dict(self) -> dict:
        d = {"severity": self.severity, "category": self.category, "message": self.message}
        if self.shot_n is not None:
            d["shot"] = self.shot_n
        if self.at_s is not None:
            d["at_s"] = round(self.at_s, 1)
        return d


@dataclass
class ShotInfo:
    """One shot joined across script.md and shotlist.json."""
    n: int
    type: str                       # ai | stock | diagram | meme
    template: str | None            # diagram template / meme template
    visual_text: str                # prompt / query / rendered field text (lowercased)
    narration: str                  # the narration this shot plays under
    words: int
    section: str                    # nearest script heading above the marker ("" if none)
    start: float                    # seconds (measured or estimated)
    duration: float                 # seconds (measured or estimated)

    @property
    def wpm(self) -> float:
        return self.words / self.duration * 60 if self.duration else 0.0

    @property
    def is_interrupt(self) -> bool:
        """Pattern interrupts: anything that breaks the b-roll stream."""
        return self.type in ("diagram", "meme")


@dataclass
class Timeline:
    shots: list[ShotInfo]
    total: float                    # seconds
    source: str                     # "timing.json" | "estimated"
    sections: list[str] = field(default_factory=list)  # in order of appearance

    def in_window(self, seconds: float) -> list[ShotInfo]:
        return [s for s in self.shots if s.start < seconds]


@dataclass
class CriticReport:
    overall: int                    # 0-100
    retention_risk: int             # 0-100 (higher = riskier)
    category_scores: dict[str, int]
    findings: list[Finding]
    timeline: Timeline

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]
