#!/usr/bin/env python
"""Content system CLI.

Stages:
  ingest    <youtube-url>   pull reference video metadata + transcript
  director                  creative review of the script (pre-shot-list)
  critic                    editorial review of script + shot list (pre-spend)
  broll     [--yes]         generate AI clips (fal.ai) + fetch stock (Pexels)
  graphics                  render motion-graphic cards + memes
  voiceover [--voice NAME]  generate the AI voiceover from script.md
  align     [--audio FILE]  align voiceover audio, emit timing + captions
  renderplan                plan camera/motion/SFX/audio per shot -> render_plan.json
  assemble  [--no-captions] build the final MP4 (executes render_plan.json)
  status                    show what's done / missing for the current project

All stages operate on the "current" project (the last one ingested) unless
--project <slug> is given.
"""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", help="project slug (default: last ingested)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="pull reference video metadata + transcript")
    p.add_argument("url", help="YouTube URL of the reference video")

    sub.add_parser("director", help="creative review of the script (report only)")
    sub.add_parser("critic", help="editorial review of script + shot list (report only)")

    p = sub.add_parser("broll", help="generate AI b-roll and fetch stock clips")
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")
    p.add_argument("--only", type=int, nargs="*", help="only these shot numbers")

    sub.add_parser("graphics", help="render diagram/title/stat cards")

    p = sub.add_parser("voiceover", help="generate the AI voiceover from script.md")
    p.add_argument("--voice", help="override the TTS voice from config.yaml")

    p = sub.add_parser("align", help="align the voiceover audio to the script")
    p.add_argument("--audio", help="voiceover file (default: first file in assets/voiceover/)")

    sub.add_parser("renderplan", help="write render_plan.json (assemble runs this "
                                      "automatically when needed)")

    p = sub.add_parser("assemble", help="build the final video")
    p.add_argument("--no-captions", action="store_true", help="skip caption burn-in")

    sub.add_parser("status", help="show pipeline progress for the project")

    args = parser.parse_args()

    # Import lazily so `ingest` works before heavy deps (whisper etc.) install.
    if args.cmd == "ingest":
        from system.ingest import run
        run(args.url)
    elif args.cmd == "director":
        from system.director.analyzer import run
        run(args.project)
    elif args.cmd == "critic":
        from system.critic.analyzer import run
        run(args.project)
    elif args.cmd == "broll":
        from system.broll import run
        run(args.project, yes=args.yes, only=args.only)
    elif args.cmd == "graphics":
        from system.graphics import run
        run(args.project)
    elif args.cmd == "voiceover":
        from system.voiceover import run
        run(args.project, voice=args.voice)
    elif args.cmd == "align":
        from system.align import run
        run(args.project, audio=args.audio)
    elif args.cmd == "renderplan":
        from system.render_intelligence.planner import run
        run(args.project)
    elif args.cmd == "assemble":
        from system.assemble import run
        run(args.project, captions=not args.no_captions)
    elif args.cmd == "status":
        from system.status import run
        run(args.project)


if __name__ == "__main__":
    sys.exit(main())
