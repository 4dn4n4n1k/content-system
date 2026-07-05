"""Stage 11: build the final video with ffmpeg — by executing render_plan.json.

All per-shot rendering decisions (camera moves, zoom punches, SFX events,
music fades, loudness) come from Render Intelligence; this module only
executes the plan. It calls ensure_plan(), which loads render_plan.json or
rebuilds it automatically when timing/assets changed — so `assemble` needs
no extra operator steps.

Two-pass design for robustness with long timelines:
  1. Each shot is rendered to a normalized segment (exact frame count,
     1080p/fps, no audio) in output/segments/ — resumable. A signature
     sidecar (.sig) records the plan parameters used, so a changed plan
     re-renders exactly the affected segments.
  2. Segments are concatenated losslessly, then voiceover + optional music
     bed + SFX track and caption burn-in are applied in one final encode.
"""
import json
import subprocess
import sys

from .render_intelligence.planner import ensure_plan
from .util import load_config, load_shotlist, project_dirs, resolve_project, shot_asset

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")


def _ffmpeg(args: list[str], cwd=None) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed: {' '.join(cmd[:12])} ...")


# ── plan-driven segment rendering ────────────────────────────────────────────

def _kenburns_vf(cam: dict, frames: int, w: int, h: int, fps: int) -> str:
    rate, zmax = cam["zoom_rate_per_frame"], cam["zoom_max"]
    if cam.get("direction", "in") == "in":
        z = f"min(zoom+{rate},{zmax})"
    else:
        z = f"max({zmax}-on*{rate},1.0)"
    pan = cam.get("pan", "center")
    x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if pan == "left":
        x = f"(iw-iw/zoom)*on/{frames}"
    elif pan == "right":
        x = f"(iw-iw/zoom)*(1-on/{frames})"
    elif pan == "up":
        y = f"(ih-ih/zoom)*on/{frames}"
    elif pan == "down":
        y = f"(ih-ih/zoom)*(1-on/{frames})"
    # Upscale first so the slow push-in doesn't shimmer.
    return (f"scale={w * 2}:-2,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},setsar=1")


def _render_segment(src, dest, shot: dict, cfg: dict) -> None:
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    frames = shot["frames"]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-an", str(dest)]

    if shot["kind"] == "image":
        vf = _kenburns_vf(shot["camera"], frames, w, h, fps)
        _ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", str(frames), *enc])
        return

    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},fps={fps},setsar=1")
    motion = shot.get("motion") or {}
    if motion.get("zoom_punch_at_s") is not None:
        punch_frame = round(motion["zoom_punch_at_s"] * fps)
        scale = motion.get("zoom_punch_scale", 1.08)
        vf += (f",zoompan=z='if(lt(on,{punch_frame}),1.0,{scale})':"
               f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}")
    _ffmpeg(["-stream_loop", "-1", "-t", f"{frames / fps + 0.5:.3f}", "-i", str(src),
             "-vf", vf, "-frames:v", str(frames), *enc])


def _signature(shot: dict) -> str:
    return json.dumps({"frames": shot["frames"], "camera": shot["camera"],
                       "motion": shot.get("motion") or {}}, sort_keys=True)


def run(project_slug: str | None, captions: bool = True) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    dirs = project_dirs(project)

    if not (project / "timing.json").exists():
        sys.exit("Missing timing.json — run `python pipeline.py align` first.")
    plan = ensure_plan(project, cfg)
    fps = plan["fps"]
    shots_by_n = {s["n"]: s for s in load_shotlist(project)["shots"]}

    # Resolve assets for every planned shot.
    missing = []
    for ps in plan["shots"]:
        asset = shot_asset(project, shots_by_n[ps["n"]])
        if not asset.exists():
            missing.append(f"shot {ps['n']:03d}: {asset}")
        ps["asset"] = asset
    if missing:
        sys.exit("Missing assets — run `broll` / `graphics` first:\n  " + "\n  ".join(missing))

    print(f"Timeline: {len(plan['shots'])} shots, {plan['duration']:.1f}s "
          f"(render_plan.json)")
    print("Rendering segments (unchanged ones are reused)...")
    for ps in plan["shots"]:
        seg = dirs["segments"] / f"shot_{ps['n']:03d}.mp4"
        sig_path = seg.with_suffix(".sig")
        ps["segment"] = seg
        sig = _signature(ps)
        if seg.exists() and sig_path.exists() and sig_path.read_text(encoding="utf-8") == sig:
            continue
        why = "plan changed" if seg.exists() else f"{ps['frames'] / fps:.1f}s from {ps['asset'].name}"
        print(f"  shot {ps['n']:03d}: {why}"
              + (f" (punch at +{ps['motion']['zoom_punch_at_s']}s)" if ps.get("motion") else ""))
        _render_segment(ps["asset"], seg, ps, cfg)
        sig_path.write_text(sig, encoding="utf-8")

    concat_list = dirs["output"] / "concat.txt"
    concat_list.write_text(
        "".join(f"file 'segments/{ps['segment'].name}'\n" for ps in plan["shots"]),
        encoding="utf-8")
    silent = dirs["output"] / "silent.mp4"
    print("Concatenating segments...")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy",
             "silent.mp4"], cwd=dirs["output"])

    # SFX track: the plan's event list, verbatim.
    audio_plan = plan["audio"]
    sfx_track = None
    if (cfg.get("sfx") or {}).get("enabled", True) and plan["events"]:
        from . import sfx as sfx_mod
        sfx_mod.ensure_sfx()
        events = [(e["t"], e["sfx"], e["gain"]) for e in plan["events"]]
        sfx_track = dirs["output"] / "sfx_track.wav"
        sfx_mod.build_track(events, plan["duration"], sfx_track)
        print(f"SFX: {len(events)} events -> sfx_track.wav")

    # Final pass: audio mix per plan (voice + music bed + SFX, loudnorm to
    # -14 LUFS) + optional caption burn-in, single encode.
    timing_audio = json.loads((project / "timing.json").read_text(encoding="utf-8"))["audio"]
    music_files = [f for f in sorted(dirs["music"].iterdir())
                   if f.suffix.lower() in AUDIO_EXTS] if dirs["music"].exists() else []
    ass = project / "captions.ass"
    burn = captions and plan["captions"]["enabled"] and ass.exists()

    args = ["-i", str(silent), "-i", str(timing_audio)]
    fc, mix, idx = ["[1:a]aresample=48000[vo]"], ["[vo]"], 2
    if music_files:
        args += ["-stream_loop", "-1", "-i", str(music_files[0])]
        fade_out_start = max(plan["duration"] - audio_plan["music_fade_out_s"], 0)
        fc.append(f"[{idx}:a]volume={audio_plan['music_volume']},"
                  f"afade=t=in:st=0:d={audio_plan['music_fade_in_s']},"
                  f"afade=t=out:st={fade_out_start:.2f}:d={audio_plan['music_fade_out_s']},"
                  f"aresample=48000[mus]")
        mix.append("[mus]")
        idx += 1
    if sfx_track:
        args += ["-i", str(sfx_track)]
        fc.append(f"[{idx}:a]volume={audio_plan['sfx_volume']},aresample=48000[sfxa]")
        mix.append("[sfxa]")
        idx += 1
    if len(mix) > 1:
        fc.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[mix]")
        last = "[mix]"
    else:
        last = "[vo]"
    if audio_plan["loudnorm"]:
        fc.append(f"{last}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
        last = "[aout]"
    args += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", last]
    if burn:
        # Run from the project dir so the filter path needs no Windows escaping.
        args += ["-vf", "ass=captions.ass"]
        vcodec = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p"]
    else:
        vcodec = ["-c:v", "copy"]
    args += [*vcodec, "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(dirs["output"] / "final.mp4")]

    print(f"Final encode (captions: {'on' if burn else 'off'}, "
          f"music: {music_files[0].name if music_files else 'none'})...")
    _ffmpeg(args, cwd=project)

    final = dirs["output"] / "final.mp4"
    print(f"\nDone: {final} ({final.stat().st_size / 1e6:.1f} MB)")
