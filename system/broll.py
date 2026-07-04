"""Stage 5: generate AI b-roll and fetch stock clips.

Providers come from the factory (config.yaml providers.video / providers.stock);
this module contains only pipeline logic: pending-shot computation, the cost
gate, resume, and per-shot failure isolation.

Resumable: shots whose file already exists in assets/broll/ are skipped.
"""
import sys

from .providers import ProviderError, ProviderFactory
from .util import load_config, load_shotlist, resolve_project, shot_asset


def run(project_slug: str | None, yes: bool = False, only: list[int] | None = None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    shotlist = load_shotlist(project)
    style_block = shotlist.get("style_block", "")

    shots = [s for s in shotlist["shots"] if s["type"] in ("ai", "stock")]
    if only:
        shots = [s for s in shots if s["n"] in only]
    pending = [s for s in shots if not shot_asset(project, s).exists()]
    done = len(shots) - len(pending)
    if done:
        print(f"{done} shot(s) already downloaded — skipping (delete files in assets/broll to regenerate).")
    if not pending:
        print("Nothing to generate.")
        return

    ai_pending = [s for s in pending if s["type"] == "ai"]
    stock_pending = [s for s in pending if s["type"] == "stock"]

    # Resolve providers up front so credential problems surface before any
    # money is spent, not halfway through a batch.
    video = stock = None
    try:
        if ai_pending:
            video = ProviderFactory.get_video_provider(cfg)
            video.check_ready()
        if stock_pending:
            stock = ProviderFactory.get_stock_provider(cfg)
            stock.check_ready()
    except ProviderError as e:
        sys.exit(str(e))

    # Asset Intelligence: plan stock shots (free) before the cost gate so
    # any AI fallbacks it decides on are confirmed and paid for knowingly.
    intel, plans = None, {}
    gen_clips, gen_secs = 0, 0.0
    if stock_pending and (cfg.get("asset_intelligence") or {}).get("enabled"):
        from .intelligence import AssetIntelligence
        intel = AssetIntelligence(cfg, stock_providers=[stock])
        try:
            for shot in stock_pending:
                plans[shot["n"]] = intel.plan_shot(shot)
            gen_clips, gen_secs = intel.generation_requirements(plans.values())
            if gen_clips and video is None:
                video = ProviderFactory.get_video_provider(cfg)
                video.check_ready()
        except ProviderError as e:
            sys.exit(str(e))

    if ai_pending or gen_clips:
        secs = sum(float(s.get("duration", video.default_duration)) for s in ai_pending)
        print(f"\nAI generation: {len(ai_pending)} clips, ~{secs:.0f}s of video")
        if gen_clips:
            print(f"  + {gen_clips} stock-shot fallback(s), ~{gen_secs:.0f}s "
                  f"(stock quality below asset_intelligence.fallback_threshold)")
            secs += gen_secs
        est = video.estimate_cost(secs)
        print(f"Model: {video.description}")
        if est is not None:
            print(f"Estimated cost: ${est:.2f} "
                  f"(providers.video.{video.name}.cost_per_second in config.yaml)")
        else:
            print("Estimated cost: unknown "
                  f"(set providers.video.{video.name}.cost_per_second in config.yaml)")
        if not yes:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer != "y":
                sys.exit("Aborted.")

    failures = []
    for shot in pending:
        dest = shot_asset(project, shot)
        try:
            if shot["type"] == "ai":
                prompt = f"{style_block} {shot['prompt']}" if style_block else shot["prompt"]
                print(f"  shot {shot['n']:03d} [ai]    generating: {shot['prompt'][:70]}...")
                video.generate(prompt, dest, duration=shot.get("duration"))
                print(f"  shot {shot['n']:03d} [ai]    saved {dest.name}")
            elif intel:
                intel.materialize(plans[shot["n"]], dest,
                                  video_provider=video, style_block=style_block)
            else:  # legacy direct fetch (asset_intelligence.enabled: false)
                print(f"  shot {shot['n']:03d} [stock] searching: {shot['query']}")
                info = stock.fetch(shot["query"], dest, pick=shot.get("pick", 0))
                if info is None:
                    print(f"  shot {shot['n']:03d} [stock] WARNING: no results for "
                          f"'{shot['query']}' — change the query or switch the shot to type 'ai'")
                else:
                    print(f"  shot {shot['n']:03d} [stock] saved {dest.name} ({info.get('height')}p)")
        except Exception as e:  # keep going; rerun picks up the failures
            failures.append(shot["n"])
            print(f"  shot {shot['n']:03d} FAILED: {e}")

    if failures:
        print(f"\n{len(failures)} shot(s) failed: {failures}. Rerun `broll` to retry just those.")
        sys.exit(1)
    print("\nAll b-roll ready.")
