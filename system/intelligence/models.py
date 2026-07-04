"""Data model for the Asset Intelligence subsystem.

Everything downstream of the planner speaks these types; providers stay
decoupled by returning plain normalized dicts that the search engine lifts
into AssetCandidate (providers never import this package).
"""
from dataclasses import dataclass, field


@dataclass
class ShotBrief:
    """Planner output: the interpreted creative intent of one shot."""
    query: str
    tokens: list[str]                      # content-bearing words of the query
    categories: dict[str, list[str]]       # subject/environment/object/camera/emotion/lighting/motion
    concepts: list[str]                    # ordered search strings, best first


@dataclass
class AssetCandidate:
    """One searchable asset, normalized across providers."""
    provider: str
    id: str
    preview: str                           # thumbnail/preview URL ("" if none)
    download_url: str
    width: int
    height: int
    duration: float                        # seconds, 0 if unknown
    text: str = ""                         # searchable descriptor (slug/title/tags)
    popularity: float | None = None        # provider-native popularity, if any
    metadata: dict = field(default_factory=dict)

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def landscape(self) -> bool:
        return self.width >= self.height


@dataclass
class ScoredCandidate:
    candidate: AssetCandidate
    score: float                           # 0..1 weighted quality
    confidence: float                      # 0..1 how much to trust the score
    reasons: list[str] = field(default_factory=list)


@dataclass
class Selection:
    """Selector output: the clip(s) that will fill the shot's slot."""
    picks: list[ScoredCandidate]
    explanation: str

    @property
    def combined_duration(self) -> float:
        return sum(p.candidate.duration for p in self.picks)


@dataclass
class ShotPlan:
    """Full decision record for one shot — also the audit trail."""
    shot: dict
    brief: ShotBrief
    considered: int                        # candidates scored
    selection: Selection | None            # None when nothing usable was found
    decision: str                          # "stock" | "generate"
    reasons: list[str]                     # why this decision was made
    generation_prompt: str | None = None   # set when decision == "generate"
    generation_duration: float = 0.0
