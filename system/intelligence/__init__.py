"""Asset Intelligence: the decision layer between the shot list and providers.

    Shot → Planner → SearchEngine → Scorer → Selector → FallbackPolicy
                                                      ↘ stock download
                                                      ↘ AI generation

Two-phase API, so the b-roll stage's cost gate stays accurate:

  plan_shot(shot)     free: interpret intent, search, score, decide
                      stock-vs-generate. Returns a ShotPlan audit record.
  materialize(plan)   spends: download the selected clip(s) or generate.

The stage never branches on the decision — it prints the plan's story and
materializes it. Output filenames are identical to the legacy path.
"""
import subprocess
import sys
from pathlib import Path

from ..providers.net import download
from .fallback import FallbackPolicy
from .models import ShotPlan
from .planner import get_planner
from .scorer import Scorer
from .search import SearchEngine
from .selector import Selector

DEFAULT_TARGET_DURATION = 5.0


class AssetIntelligence:
    def __init__(self, cfg: dict, stock_providers: list):
        ai = cfg.get("asset_intelligence") or {}
        self.cfg = cfg
        self.threshold = float(ai.get("fallback_threshold", 0.72))
        self.planner = get_planner(ai.get("planner"))
        self.engine = SearchEngine([p for p in stock_providers if p is not None],
                                   max_candidates=int(ai.get("max_candidates", 20)))
        self.scorer = Scorer(ai.get("scoring"))
        self.selector = Selector(ai.get("selector"))
        self.policy = FallbackPolicy(self.threshold)

    # ── phase 1: plan (no downloads, no spend) ──────────────────────────────

    def plan_shot(self, shot: dict) -> ShotPlan:
        brief = self.planner.plan(shot)
        target = float(shot.get("duration", DEFAULT_TARGET_DURATION))
        print(f"  shot {shot['n']:03d} [intel] concepts: {', '.join(brief.concepts[:5])}")

        candidates = self.engine.search(brief.concepts)
        scored = [self.scorer.score(c, brief, target) for c in candidates]
        selection = self.selector.select(scored, target)
        decision, reasons = self.policy.decide(selection)

        plan = ShotPlan(shot=shot, brief=brief, considered=len(scored),
                        selection=selection, decision=decision, reasons=reasons)
        if decision == "generate":
            plan.generation_prompt = self.policy.generation_prompt(shot, brief)
            plan.generation_duration = target
            print(f"  shot {shot['n']:03d} [intel] {len(scored)} candidates -> "
                  f"AI fallback ({'; '.join(reasons[:1])})")
        else:
            best = selection.picks[0]
            print(f"  shot {shot['n']:03d} [intel] {len(scored)} candidates -> "
                  f"stock {best.candidate.provider}#{best.candidate.id} "
                  f"score {best.score:.2f} conf {best.confidence:.2f}")
            print(f"  shot {shot['n']:03d} [intel]   {selection.explanation}")
        return plan

    @staticmethod
    def generation_requirements(plans) -> tuple[int, float]:
        """(clip_count, total_seconds) the cost gate must account for."""
        gen = [p for p in plans if p.decision == "generate"]
        return len(gen), sum(p.generation_duration for p in gen)

    # ── phase 2: materialize (downloads / spends) ───────────────────────────

    def materialize(self, plan: ShotPlan, dest: Path,
                    video_provider=None, style_block: str = "") -> None:
        n = plan.shot["n"]
        if plan.decision == "generate":
            if video_provider is None:
                raise RuntimeError("plan requires AI generation but no video provider given")
            prompt = plan.generation_prompt
            if style_block:
                prompt = f"{style_block} {prompt}"
            print(f"  shot {n:03d} [stock] generating instead "
                  f"({'; '.join(plan.reasons[:1])}): {plan.generation_prompt[:60]}...")
            video_provider.generate(prompt, dest, duration=plan.shot.get("duration"))
            print(f"  shot {n:03d} [stock] saved {dest.name} (AI fallback)")
            return

        picks = plan.selection.picks
        if len(picks) == 1:
            cand = picks[0].candidate
            download(cand.download_url, dest, provider=cand.provider)
            print(f"  shot {n:03d} [stock] saved {dest.name} "
                  f"({cand.height}p, {cand.provider}#{cand.id})")
            return

        # Multi-clip: normalize parts to a uniform stream, then concat.
        v = self.cfg["video"]
        parts = []
        try:
            for i, pick in enumerate(picks):
                raw = dest.with_suffix(f".raw{i}.mp4")
                norm = dest.with_suffix(f".part{i}.mp4")
                download(pick.candidate.download_url, raw, provider=pick.candidate.provider)
                _run_ffmpeg(["-i", str(raw),
                             "-vf", f"scale={v['width']}:{v['height']}:"
                                    f"force_original_aspect_ratio=increase,"
                                    f"crop={v['width']}:{v['height']},"
                                    f"fps={v['fps']},setsar=1",
                             "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
                             str(norm)])
                raw.unlink()
                parts.append(norm)
            concat_list = dest.with_suffix(".concat.txt")
            concat_list.write_text("".join(f"file '{p.name}'\n" for p in parts),
                                   encoding="utf-8")
            _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list),
                         "-c", "copy", str(dest)])
            concat_list.unlink()
        finally:
            for p in parts:
                p.unlink(missing_ok=True)
        print(f"  shot {n:03d} [stock] saved {dest.name} "
              f"({len(picks)} clips stitched: {plan.selection.explanation})")


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed while stitching stock clips:\n{result.stderr[-500:]}")
