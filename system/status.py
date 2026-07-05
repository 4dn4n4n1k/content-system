"""Show pipeline progress for a project."""
from .util import load_shotlist, project_dirs, resolve_project, shot_asset


def run(project_slug: str | None) -> None:
    project = resolve_project(project_slug)
    dirs = project_dirs(project)
    print(f"Project: {project.name}\n")

    def mark(ok: bool) -> str:
        return "[x]" if ok else "[ ]"

    print(f"{mark((project / 'source.json').exists())} 1. ingest      source.json")
    print(f"{mark((project / 'research.md').exists())} 2. research    research.md   (Claude)")
    print(f"{mark((project / 'script.md').exists())} 3. script      script.md     (Claude + your review)")
    print(f"{mark((project / 'creative_report.md').exists())} 4. director    "
          f"creative_report.md (script review, pre-shot-list)")

    has_shotlist = (project / "shotlist.json").exists()
    print(f"{mark(has_shotlist)} 5. shot list   shotlist.json (Claude + your review)")
    print(f"{mark((project / 'timeline_report.md').exists())} 6. critic      "
          f"timeline_report.md (review before spending)")

    if has_shotlist:
        shots = load_shotlist(project)["shots"]
        visual = [s for s in shots if s["type"] in ("ai", "stock")]
        gfx = [s for s in shots if s["type"] in ("diagram", "meme")]
        v_done = sum(1 for s in visual if shot_asset(project, s).exists())
        g_done = sum(1 for s in gfx if shot_asset(project, s).exists())
        print(f"{mark(v_done == len(visual))} 7. broll       {v_done}/{len(visual)} clips")
        print(f"{mark(g_done == len(gfx))} 8. graphics    {g_done}/{len(gfx)} cards")
    else:
        print("[ ] 7. broll")
        print("[ ] 8. graphics")

    vo = [f for f in dirs["voiceover"].iterdir()
          if f.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")]
    print(f"{mark(bool(vo))} 9. voiceover   {vo[0].name if vo else 'run: python pipeline.py voiceover'}")
    print(f"{mark((project / 'timing.json').exists())} 10. align      timing.json + captions.ass")
    print(f"{mark((project / 'render_plan.json').exists())} 11. renderplan render_plan.json "
          f"(auto-runs during assemble)")
    print(f"{mark((dirs['output'] / 'final.mp4').exists())} 12. assemble   output/final.mp4")
