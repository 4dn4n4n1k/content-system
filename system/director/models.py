"""Data model for the Creative Director.

The director reviews the SCRIPT (pre-shot-list), so its unit of analysis is
the sentence/section, with timestamps estimated from narration word counts.
Report-only: nothing here mutates project files.
"""
from dataclasses import dataclass, field

SEVERITIES = ("critical", "warning", "suggestion", "strength")
CATEGORIES = ("hook", "narrative", "clarity", "emotion", "curiosity", "visuals")


@dataclass
class Sentence:
    index: int
    text: str
    words: int
    start_s: float                  # estimated position on the narration timeline
    section: str


@dataclass
class Section:
    name: str
    start_s: float
    words: int
    sentences: list[Sentence] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return sum(s.words for s in self.sentences) and (
            self.sentences[-1].start_s + 2 - self.start_s) or 0.0


@dataclass
class ScriptDoc:
    sections: list[Section]
    sentences: list[Sentence]       # flat, in order
    total_words: int
    est_duration: float             # seconds at the configured wpm

    def in_window(self, seconds: float) -> list[Sentence]:
        return [s for s in self.sentences if s.start_s < seconds]


@dataclass
class Finding:
    severity: str                   # critical | warning | suggestion | strength
    category: str                   # hook | narrative | clarity | emotion | curiosity | visuals
    message: str
    at_s: float | None = None
    section: str | None = None

    def to_dict(self) -> dict:
        d = {"severity": self.severity, "category": self.category, "message": self.message}
        if self.at_s is not None:
            d["at_s"] = round(self.at_s, 1)
        if self.section:
            d["section"] = self.section
        return d


@dataclass
class VisualOpportunity:
    at_s: float
    section: str
    kind: str                       # stat_card | diagram | timeline | comparison |
                                    # quote_card | list | meme | broll | animation
    trigger: str                    # the sentence fragment that suggested it
    confidence: float               # 0..1
    rationale: str

    def to_dict(self) -> dict:
        return {"at_s": round(self.at_s, 1), "section": self.section, "kind": self.kind,
                "trigger": self.trigger[:90], "confidence": round(self.confidence, 2),
                "rationale": self.rationale}


@dataclass
class DirectorReport:
    overall: int
    category_scores: dict[str, int]
    findings: list[Finding]
    visual_ops: list[VisualOpportunity]
    doc: ScriptDoc

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]
