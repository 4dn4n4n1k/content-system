"""Shared helpers: config, project resolution, paths."""
import json
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
CURRENT_FILE = PROJECTS / ".current"

load_dotenv(ROOT / ".env")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "video"


def set_current(slug: str) -> None:
    PROJECTS.mkdir(exist_ok=True)
    CURRENT_FILE.write_text(slug, encoding="utf-8")


def resolve_project(slug: str | None) -> Path:
    """Return the project dir for `slug`, or the current project if None."""
    if slug is None:
        if not CURRENT_FILE.exists():
            sys.exit("No current project. Run `ingest` first or pass --project <slug>.")
        slug = CURRENT_FILE.read_text(encoding="utf-8").strip()
    path = PROJECTS / slug
    if not path.exists():
        sys.exit(f"Project not found: {path}")
    return path


def project_dirs(project: Path) -> dict[str, Path]:
    dirs = {
        "broll": project / "assets" / "broll",
        "graphics": project / "assets" / "graphics",
        "memes": project / "assets" / "memes",
        "voiceover": project / "assets" / "voiceover",
        "music": project / "assets" / "music",
        "output": project / "output",
        "segments": project / "output" / "segments",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_shotlist(project: Path) -> dict:
    path = project / "shotlist.json"
    if not path.exists():
        sys.exit(f"Missing {path}. Generate the shot list first (see README workflow).")
    data = read_json(path)
    seen = set()
    for shot in data["shots"]:
        n = shot["n"]
        if n in seen:
            sys.exit(f"shotlist.json: duplicate shot number {n}")
        seen.add(n)
        if shot["type"] not in ("ai", "stock", "diagram", "meme"):
            sys.exit(f"shotlist.json: shot {n} has unknown type '{shot['type']}'")
    return data


def shot_asset(project: Path, shot: dict) -> Path:
    """Path where a shot's visual asset lives.

    ai/stock     -> assets/broll/shot_NNN.mp4
    diagram/meme -> assets/graphics/shot_NNN.mp4 (animated, Remotion) if present,
                    else shot_NNN.png (static, Playwright fallback)
    """
    dirs = project_dirs(project)
    n = shot["n"]
    if shot["type"] in ("diagram", "meme"):
        mp4 = dirs["graphics"] / f"shot_{n:03d}.mp4"
        png = dirs["graphics"] / f"shot_{n:03d}.png"
        return mp4 if mp4.exists() or not png.exists() else png
    return dirs["broll"] / f"shot_{n:03d}.mp4"
