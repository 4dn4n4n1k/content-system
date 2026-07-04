"""Stage 6: render diagram/title/stat/quote/list cards and meme shots.

Two renderers:
  motion (default) — animated cards via the Remotion project in motion/
                     (elements stagger in, stat count-up, slow drift hold)
                     -> assets/graphics/shot_NNN.mp4
  static (fallback) — HTML template -> Playwright screenshot
                     -> assets/graphics/shot_NNN.png (assembler adds a slow zoom)

Shot examples:
  { "n": 3, "type": "diagram", "template": "stat_card",
    "fields": { "stat": "4,000+", "label": "attacks per day" } }
  { "n": 7, "type": "meme", "template": "Distracted Boyfriend",
    "top": "shiny new AI tool", "bottom": "the patch backlog" }

Meme shots pull the blank template from Imgflip's free catalog (no key), then
get animated Impact-style captions overlaid on the brand background.

Resumable: shots whose output file already exists are skipped.
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .providers import ProviderError, ProviderFactory
from .providers.net import download
from .util import ROOT, load_config, load_shotlist, project_dirs, resolve_project

TEMPLATES = Path(__file__).parent / "templates"
MOTION = ROOT / "motion"
TEMPLATE_TO_COMP = {
    "title_card": "TitleCard",
    "stat_card": "StatCard",
    "diagram": "Diagram",
    "quote_card": "QuoteCard",
    "list_card": "ListCard",
}


def _motion_available() -> bool:
    return (MOTION / "node_modules" / "remotion").exists() and shutil.which("npx") is not None


def _ensure_meme_template(shot: dict, memes_dir: Path, meme_provider) -> Path:
    """Download the blank template for a meme shot (skipped if present).
    Returns the local image path. `image_url` bypasses the provider."""
    existing = list(memes_dir.glob(f"shot_{shot['n']:03d}.*"))
    if existing:
        return existing[0]
    if shot.get("image_url"):
        url, label = shot["image_url"], "custom image"
    else:
        url, label = meme_provider.resolve(shot["template"])
    suffix = Path(url.split("?")[0]).suffix or ".jpg"
    dest = memes_dir / f"shot_{shot['n']:03d}{suffix}"
    download(url, dest, timeout=60, provider="meme")
    print(f"  shot {shot['n']:03d} [meme]  template '{label}' -> {dest.name}")
    return dest


def _display_box(image_path: Path, max_w: int = 1150, max_h: int = 720) -> tuple[int, int]:
    """Display size that fills the card while keeping the meme's aspect ratio
    (memes are low-res; scaling up is part of the look)."""
    from PIL import Image

    with Image.open(image_path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return round(w * scale), round(h * scale)


def _meme_props(shot: dict, project: Path, meme_provider) -> dict:
    """Stage the meme image into motion/public/ and build MemeCard props."""
    dirs = project_dirs(project)
    src = _ensure_meme_template(shot, dirs["memes"], meme_provider)
    public = MOTION / "public" / "memes"
    public.mkdir(parents=True, exist_ok=True)
    staged = public / f"{project.name}_{src.name}"
    shutil.copyfile(src, staged)
    w, h = _display_box(src)
    return {"image": f"memes/{staged.name}", "width": w, "height": h,
            "top": shot.get("top", ""), "bottom": shot.get("bottom", "")}


def _render_motion(shot: dict, dest: Path, cfg: dict, project: Path, meme_provider=None) -> None:
    if shot["type"] == "meme":
        comp = "MemeCard"
        props = {"brand": cfg["brand"], **_meme_props(shot, project, meme_provider)}
    else:
        comp = TEMPLATE_TO_COMP.get(shot["template"])
        if comp is None:
            raise ValueError(f"no Remotion composition for template '{shot['template']}'")
        props = {"brand": cfg["brand"], **shot.get("fields", {})}
    props_path = dest.with_suffix(".props.json")
    props_path.write_text(json.dumps(props), encoding="utf-8")
    try:
        result = subprocess.run(
            [shutil.which("npx"), "remotion", "render", comp, str(dest),
             f"--props={props_path}", "--log=error"],
            cwd=MOTION, capture_output=True, text=True, timeout=900,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-500:] or "remotion render failed")
    finally:
        props_path.unlink(missing_ok=True)


def _render_static(shots: list[dict], project: Path, cfg: dict, meme_provider=None) -> None:
    from jinja2 import Environment, FileSystemLoader
    from playwright.sync_api import sync_playwright

    dirs = project_dirs(project)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": cfg["video"]["width"],
                                          "height": cfg["video"]["height"]})
        for shot in shots:
            dest = dirs["graphics"] / f"shot_{shot['n']:03d}.png"
            if shot["type"] == "meme":
                img = _ensure_meme_template(shot, dirs["memes"], meme_provider)
                mime = "image/png" if img.suffix == ".png" else "image/jpeg"
                data_uri = f"data:{mime};base64,{base64.b64encode(img.read_bytes()).decode()}"
                w, h = _display_box(img)
                template = env.get_template("meme_card.html")
                html = template.render(brand=cfg["brand"], image=data_uri,
                                       width=w, height=h,
                                       font_size=max(36, min(64, round(h * 0.1))),
                                       top=shot.get("top", ""), bottom=shot.get("bottom", ""))
            else:
                template = env.get_template(f"{shot['template']}.html")
                html = template.render(brand=cfg["brand"], **shot.get("fields", {}))
            page.set_content(html)
            page.wait_for_timeout(150)  # let fonts settle
            page.screenshot(path=str(dest))
            print(f"  shot {shot['n']:03d} [{shot.get('template', 'meme')}] -> {dest.name} (static)")
        browser.close()


def run(project_slug: str | None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    dirs = project_dirs(project)
    shots = [s for s in load_shotlist(project)["shots"] if s["type"] in ("diagram", "meme")]
    if not shots:
        print("No diagram/meme shots in shotlist.json — nothing to render.")
        return

    renderer = (cfg.get("graphics") or {}).get("renderer", "motion")
    use_motion = renderer == "motion" and _motion_available()
    if renderer == "motion" and not use_motion:
        print("Remotion not available (motion/node_modules missing or no npx) — "
              "falling back to static cards.")

    meme_provider = None
    if any(s["type"] == "meme" for s in shots):
        try:
            meme_provider = ProviderFactory.get_meme_provider(cfg)
            meme_provider.check_ready()
        except ProviderError as e:
            sys.exit(str(e))

    static_fallback = []
    if use_motion:
        for shot in shots:
            dest = dirs["graphics"] / f"shot_{shot['n']:03d}.mp4"
            if dest.exists():
                print(f"  shot {shot['n']:03d} already rendered — skipping")
                continue
            print(f"  shot {shot['n']:03d} [{shot.get('template', 'meme')}] rendering motion card...")
            try:
                _render_motion(shot, dest, cfg, project, meme_provider)
                print(f"  shot {shot['n']:03d} -> {dest.name}")
            except Exception as e:
                print(f"  shot {shot['n']:03d} Remotion failed ({str(e)[:200]}) — will render static")
                static_fallback.append(shot)
    else:
        static_fallback = [s for s in shots
                           if not (dirs["graphics"] / f"shot_{s['n']:03d}.png").exists()]

    if static_fallback:
        try:
            _render_static(static_fallback, project, cfg, meme_provider)
        except ProviderError as e:
            sys.exit(str(e))
    print(f"\nGraphics done ({len(shots)} card(s)).")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
