"""Fallback policy: decide stock vs AI generation for a planned shot.

If the best stock candidate can't clear the configured quality threshold,
the shot is routed to the configured VideoGenerationProvider with a prompt
built from the planner's brief. The pipeline stage never branches on this —
it just materializes whatever the plan says (same dest file either way).
"""
from .models import Selection, ShotBrief


class FallbackPolicy:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def decide(self, selection: Selection | None) -> tuple[str, list[str]]:
        """Returns (decision, reasons): 'stock' or 'generate'."""
        if selection is None:
            return "generate", ["no stock candidates found for any concept"]
        best = selection.picks[0]
        if best.score < self.threshold:
            return "generate", [
                f"best stock score {best.score:.2f} below threshold {self.threshold:.2f}",
                *best.reasons[:2],
            ]
        return "stock", [f"stock score {best.score:.2f} ≥ threshold {self.threshold:.2f}"]

    @staticmethod
    def generation_prompt(shot: dict, brief: ShotBrief) -> str:
        """Build a text-to-video prompt from the shot's creative intent.
        (The b-roll stage prepends the global style_block, same as any
        explicit `ai` shot, so generated fallbacks match the video's look.)"""
        if shot.get("prompt"):  # author already provided generation intent
            return shot["prompt"]
        style = " ".join(
            brief.categories.get("lighting", []) + brief.categories.get("emotion", [])
            + brief.categories.get("camera", []) + brief.categories.get("motion", []))
        extras = ", ".join(c for c in brief.concepts[1:3])
        prompt = brief.query
        if extras:
            prompt += f", {extras}"
        if style:
            prompt += f", {style}"
        return prompt
