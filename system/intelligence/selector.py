"""Selector: turn scored candidates into the clip set that fills the slot.

Default is the single highest-scoring candidate. When the shot's expected
duration meaningfully exceeds the best clip (looping a 4s clip through a 15s
slot reads as cheap), it assembles a small sequence of near-best clips until
the slot is covered. Low-confidence winners are always explained, never
silent (the explanation surfaces in the console and the plan record).
"""
from .models import ScoredCandidate, Selection

#: slot must exceed clip length by this factor before we go multi-clip
LOOP_TOLERANCE = 1.6
#: extra clips must score at least this fraction of the winner's score
RUNNER_UP_FLOOR = 0.85


class Selector:
    def __init__(self, cfg: dict | None):
        cfg = cfg or {}
        self.max_clips = int(cfg.get("max_clips", 3))
        self.low_confidence = float(cfg.get("low_confidence", 0.5))

    def select(self, scored: list[ScoredCandidate],
               target_duration: float) -> Selection | None:
        if not scored:
            return None
        ranked = sorted(scored, key=lambda s: s.score, reverse=True)
        best = ranked[0]

        picks = [best]
        if (best.candidate.duration
                and target_duration > best.candidate.duration * LOOP_TOLERANCE
                and self.max_clips > 1):
            floor = best.score * RUNNER_UP_FLOOR
            for cand in ranked[1:]:
                if sum(p.candidate.duration for p in picks) >= target_duration:
                    break
                if len(picks) >= self.max_clips or cand.score < floor:
                    break
                picks.append(cand)

        covered = sum(p.candidate.duration for p in picks)
        if len(picks) > 1:
            explanation = (f"{len(picks)} clips ({covered:.0f}s) to cover the "
                           f"{target_duration:.0f}s slot without visible looping")
        else:
            explanation = f"best of {len(scored)} candidates, score {best.score:.2f}"
        if best.confidence < self.low_confidence:
            explanation += (f" — LOW CONFIDENCE {best.confidence:.2f}: "
                            f"{'; '.join(best.reasons[:2])}")
        return Selection(picks=picks, explanation=explanation)
