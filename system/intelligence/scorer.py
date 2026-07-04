"""Scorer: weighted quality scoring of candidates against a shot brief.

Every component scores 0..1; the final score is the weight-normalized sum.
Weights come from config (asset_intelligence.scoring) so tuning never
touches code. `reasons` narrates each component for the audit trail.

Extensible: extra components (e.g. a Vision AI similarity score against the
shot brief) are added to _components() with their own config weight —
callers only ever see score/confidence/reasons.
"""
import re

from .models import AssetCandidate, ScoredCandidate, ShotBrief

DEFAULT_WEIGHTS = {"relevance": 0.40, "resolution": 0.20, "duration": 0.15,
                   "metadata": 0.10, "popularity": 0.10, "provider": 0.05}
DEFAULT_PROVIDER_CONFIDENCE = {"pexels": 0.9}


class Scorer:
    def __init__(self, cfg: dict | None):
        cfg = cfg or {}
        self.weights = {k: float(cfg.get(k, v)) for k, v in DEFAULT_WEIGHTS.items()}
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}
        self.provider_confidence = {**DEFAULT_PROVIDER_CONFIDENCE,
                                    **(cfg.get("provider_confidence") or {})}

    def score(self, cand: AssetCandidate, brief: ShotBrief,
              target_duration: float) -> ScoredCandidate:
        parts, reasons = self._components(cand, brief, target_duration)
        score = sum(self.weights[name] * value for name, value in parts.items())
        # Confidence = how much signal backed the score, not how good the
        # asset is: strong keyword evidence + complete metadata = trust it.
        confidence = round(0.5 * parts["relevance"] + 0.3 * parts["metadata"]
                           + 0.2 * parts["provider"], 3)
        return ScoredCandidate(candidate=cand, score=round(score, 3),
                               confidence=confidence, reasons=reasons)

    def _components(self, cand: AssetCandidate, brief: ShotBrief,
                    target: float) -> tuple[dict[str, float], list[str]]:
        reasons: list[str] = []

        # Relevance: query tokens found in the candidate's descriptor text,
        # subject/object words weighing double vs style words. Falling back
        # to a lower-ranked search concept also costs a little.
        text = f"{cand.text} {cand.metadata.get('concept', '')}".lower()
        words = set(re.findall(r"[a-z0-9-]+", text))
        core = set(brief.categories.get("subject", []) + brief.categories.get("object", []))
        style = set(brief.tokens) - core
        matched = [t for t in core if t in words]
        matched_style = [t for t in style if t in words]
        weight_total = 2 * len(core) + len(style)
        if weight_total:
            relevance = (2 * len(matched) + len(matched_style)) / weight_total
        else:
            relevance = 0.5
        rank_penalty = min(cand.metadata.get("concept_rank", 0) * 0.05, 0.25)
        relevance = max(relevance - rank_penalty, 0.0)
        hit = ", ".join(matched + matched_style) or "none"
        reasons.append(f"relevance {relevance:.2f} (matched: {hit}; "
                       f"via '{cand.metadata.get('concept', brief.query)}')")

        # Resolution, with orientation folded in: portrait footage is nearly
        # unusable in a 16:9 timeline no matter how sharp it is.
        resolution = min(cand.height / 1080, 1.0) if cand.height else 0.3
        if not cand.landscape:
            resolution *= 0.2
            reasons.append(f"portrait {cand.resolution} — heavy penalty")
        else:
            reasons.append(f"{cand.resolution}")

        # Duration: full marks when the clip covers the slot without being a
        # 10x-too-long haystack; short clips loop, so they degrade gently.
        if not cand.duration:
            duration = 0.4
            reasons.append("duration unknown")
        elif cand.duration >= target:
            duration = 1.0 if cand.duration <= 6 * target else 0.8
            reasons.append(f"{cand.duration:.0f}s covers {target:.0f}s slot")
        else:
            duration = max(cand.duration / target, 0.3)
            reasons.append(f"{cand.duration:.0f}s < {target:.0f}s slot (will loop)")

        # Metadata completeness: how describable/inspectable the asset is.
        fields = [cand.preview, cand.text, cand.width, cand.height, cand.duration]
        metadata = sum(1 for f in fields if f) / len(fields)

        # Popularity: neutral 0.5 when the provider has no metric.
        if cand.popularity is None:
            popularity = 0.5
        else:
            popularity = min(max(cand.popularity, 0.0), 1.0)
            reasons.append(f"popularity {popularity:.2f}")

        provider = self.provider_confidence.get(cand.provider, 0.7)

        return ({"relevance": relevance, "resolution": resolution,
                 "duration": duration, "metadata": metadata,
                 "popularity": popularity, "provider": provider}, reasons)
