"""Stage 1: pull reference video metadata + transcript with yt-dlp."""
import json

from .util import PROJECTS, load_config, project_dirs, set_current, slugify, write_json

BOT_CHECK = "Sign in to confirm"
BROWSERS = ("firefox", "edge", "chrome")  # cookie fallback order (browser must be closed)


def _attempts() -> list[tuple[str, dict]]:
    """yt-dlp option variants to try, in order, when YouTube bot-checks us."""
    variants = [
        ("web", {}),
        # The android client is not bot-checked as aggressively as the web client.
        ("android client", {"extractor_args": {"youtube": {"player_client": ["android"]}}}),
    ]
    cfg_browser = (load_config().get("ingest") or {}).get("cookies_from_browser")
    for browser in ([cfg_browser] if cfg_browser else BROWSERS):
        variants.append((f"{browser} cookies", {"cookiesfrombrowser": (browser,)}))
    return variants


def _extract(url: str, base_opts: dict, download: bool, variant: dict | None = None):
    """Run yt-dlp, walking the fallback chain until one variant succeeds.
    Returns (info_or_None, winning_variant_opts)."""
    import yt_dlp
    from yt_dlp.utils import DownloadError

    attempts = [("given", variant)] if variant is not None else _attempts()
    last_err = None
    for label, extra in attempts:
        try:
            with yt_dlp.YoutubeDL({**base_opts, **extra}) as ydl:
                if download:
                    ydl.download([url])
                    return None, extra
                return ydl.extract_info(url, download=False), extra
        except (DownloadError, yt_dlp.cookies.CookieLoadError) as e:
            last_err = e
            msg = str(e).splitlines()[0]
            if BOT_CHECK not in msg and label == "web":
                raise  # a different error — don't mask it behind fallbacks
            print(f"  ({label}: {msg[:100]})")
    raise last_err


def _parse_json3(path) -> list[dict]:
    """Parse a YouTube json3 subtitle file into [{start, text}]."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if text:
            lines.append({"start": round(ev.get("tStartMs", 0) / 1000, 2), "text": text})
    return lines


def run(url: str) -> None:
    print(f"Fetching metadata: {url}")
    probe_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    info, variant = _extract(url, probe_opts, download=False)

    slug = slugify(info["title"])
    project = PROJECTS / slug
    project.mkdir(parents=True, exist_ok=True)
    project_dirs(project)
    set_current(slug)

    print(f"Project: projects/{slug}")
    print(f"Title:   {info['title']}")
    print(f"Channel: {info.get('channel') or info.get('uploader')}")
    print(f"Length:  {info.get('duration', 0) // 60}m {info.get('duration', 0) % 60}s")

    # Grab English subtitles (manual preferred, auto-captions as fallback).
    sub_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB", "en-orig"],
        "subtitlesformat": "json3",
        "outtmpl": str(project / "subs"),
        "quiet": True,
        "no_warnings": True,
    }
    _extract(url, sub_opts, download=True, variant=variant)

    transcript = []
    for sub_file in sorted(project.glob("subs.*.json3")):
        transcript = _parse_json3(sub_file)
        sub_file.unlink()
        if transcript:
            break

    source = {
        "id": info["id"],
        "url": info.get("webpage_url", url),
        "title": info["title"],
        "channel": info.get("channel") or info.get("uploader"),
        "duration_s": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "description": info.get("description", ""),
        "chapters": info.get("chapters") or [],
        "transcript": transcript,
        "transcript_text": " ".join(t["text"] for t in transcript),
    }
    write_json(project / "source.json", source)

    words = len(source["transcript_text"].split())
    if transcript:
        print(f"Transcript: {len(transcript)} segments, ~{words} words -> source.json")
    else:
        print("WARNING: no English transcript found. Research stage will rely on "
              "the description and web search only.")
    print("\nNext: ask Claude to run the research + script stages for this project.")
