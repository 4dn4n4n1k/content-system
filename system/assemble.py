"""Stage 9: build the final video with ffmpeg.

Two-pass design for robustness with long timelines:
  1. Each shot is rendered to a normalized segment (exact frame count,
     1080p/fps, no audio) in output/segments/ — resumable, so a crash or a
     tweaked shot only re-renders what changed (delete a segment to redo it).
  2. Segments are concatenated losslessly, then voiceover + optional music
     bed and caption burn-in are applied in one final encode.

Frame counts are computed from cumulative timeline boundaries so rounding
never drifts the visuals away from the voiceover.
"""
import subprocess
import sys

from .util import load_config, load_shotlist, project_dirs, read_json, resolve_project, shot_asset

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")


def _duration(path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return -1.0


def _ffmpeg(args: list[str], cwd=None) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed: {' '.join(cmd[:12])} ...")


def _render_segment(src, dest, is_image: bool, frames: int, cfg: dict) -> None:
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    dur = frames / fps
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-an", str(dest)]
    if is_image:
        # Upscale first so the slow push-in doesn't shimmer.
        vf = (f"scale={w * 2}:-2,"
              f"zoompan=z='min(zoom+0.0008,1.12)':"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d={frames}:s={w}x{h}:fps={fps},setsar=1")
        _ffmpeg(["-i", str(src), "-vf", vf, "-frames:v", str(frames), *enc])
    else:
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h},fps={fps},setsar=1")
        _ffmpeg(["-stream_loop", "-1", "-t", f"{dur + 0.5:.3f}", "-i", str(src),
                 "-vf", vf, "-frames:v", str(frames), *enc])


def run(project_slug: str | None, captions: bool = True) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    dirs = project_dirs(project)
    fps = cfg["video"]["fps"]

    timing_path = project / "timing.json"
    if not timing_path.exists():
        sys.exit("Missing timing.json — run `python pipeline.py align` first.")
    timing = read_json(timing_path)
    shots_by_n = {s["n"]: s for s in load_shotlist(project)["shots"]}

    # Resolve timeline: cumulative frame boundaries prevent rounding drift.
    entries = []
    missing = []
    order = timing["shots"]
    for i, t in enumerate(order):
        shot = shots_by_n.get(t["n"])
        if shot is None:
            sys.exit(f"timing.json references shot {t['n']} missing from shotlist.json")
        end = order[i + 1]["start"] if i + 1 < len(order) else timing["duration"]
        f0, f1 = round(t["start"] * fps), round(end * fps)
        if f1 - f0 < 2:
            print(f"  shot {t['n']:03d}: <2 frames on the timeline, skipping")
            continue
        asset = shot_asset(project, shot)
        if not asset.exists():
            missing.append(f"shot {t['n']:03d}: {asset}")
        entries.append({"n": t["n"], "asset": asset, "frames": f1 - f0,
                        "type": shot["type"],
                        "is_image": asset.suffix.lower() == ".png"})
    if missing:
        sys.exit("Missing assets — run `broll` / `graphics` first:\n  " + "\n  ".join(missing))

    print(f"Timeline: {len(entries)} shots, {timing['duration']:.1f}s")
    print("Rendering segments (existing ones are reused; delete to re-render)...")
    for e in entries:
        seg = dirs["segments"] / f"shot_{e['n']:03d}.mp4"
        e["segment"] = seg
        if seg.exists():
            if abs(_duration(seg) - e["frames"] / fps) < 1.5 / fps:
                continue
            print(f"  shot {e['n']:03d}: timing changed, re-rendering")
        else:
            print(f"  shot {e['n']:03d} ({e['frames'] / fps:.1f}s) from {e['asset'].name}")
        _render_segment(e["asset"], seg, e["is_image"], e["frames"], cfg)

    concat_list = dirs["output"] / "concat.txt"
    concat_list.write_text(
        "".join(f"file 'segments/{e['segment'].name}'\n" for e in entries), encoding="utf-8")
    silent = dirs["output"] / "silent.mp4"
    print("Concatenating segments...")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy",
             "silent.mp4"], cwd=dirs["output"])

    # Sound design: whoosh on cuts, impact when cards land, pop on meme slams.
    sfx_cfg = cfg.get("sfx") or {}
    sfx_track = None
    if sfx_cfg.get("enabled", True):
        from . import sfx as sfx_mod
        sfx_mod.ensure_sfx()
        events, t = [], 0.0
        for i, e in enumerate(entries):
            if i > 0:
                events.append((max(0.0, t - 0.12), "whoosh", 0.7))
            if e["type"] == "diagram":
                events.append((t + 0.2, "impact", 1.0))
            elif e["type"] == "meme":
                events.append((t + 0.55, "pop", 1.0))
            t += e["frames"] / fps
        if events:
            sfx_track = dirs["output"] / "sfx_track.wav"
            sfx_mod.build_track(events, timing["duration"], sfx_track)
            print(f"SFX: {len(events)} events -> sfx_track.wav")

    # Final pass: audio mix (voice + music bed + SFX, normalized to -14 LUFS
    # = YouTube's loudness target) + optional caption burn-in, single encode.
    voiceover = timing["audio"]
    music_files = [f for f in sorted(dirs["music"].iterdir())
                   if f.suffix.lower() in AUDIO_EXTS] if dirs["music"].exists() else []
    ass = project / "captions.ass"
    burn = captions and cfg["captions"]["enabled"] and ass.exists()

    args = ["-i", str(silent), "-i", str(voiceover)]
    fc, mix, idx = ["[1:a]aresample=48000[vo]"], ["[vo]"], 2
    if music_files:
        args += ["-stream_loop", "-1", "-i", str(music_files[0])]
        fc.append(f"[{idx}:a]volume={cfg['music']['volume']},aresample=48000[mus]")
        mix.append("[mus]")
        idx += 1
    if sfx_track:
        args += ["-i", str(sfx_track)]
        fc.append(f"[{idx}:a]volume={sfx_cfg.get('volume', 0.45)},aresample=48000[sfxa]")
        mix.append("[sfxa]")
        idx += 1
    if len(mix) > 1:
        fc.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[mix]")
        last = "[mix]"
    else:
        last = "[vo]"
    if (cfg.get("audio") or {}).get("loudnorm", True):
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
