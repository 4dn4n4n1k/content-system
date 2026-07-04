"""Stage 7: generate the AI voiceover from script.md.

The TTS engine comes from the factory (config.yaml providers.voice.active:
cartesia | edge | elevenlabs); this module only extracts narration text from
the script and manages the output file.

Output: assets/voiceover/voiceover.<ext> (ext per provider), which `align`
then transcribes for shot timing + captions (same path as any recording, so
dropping a manually recorded file in assets/voiceover/ still works too).
"""
import re
import sys

from .providers import ProviderError, ProviderFactory
from .util import load_config, project_dirs, resolve_project

MARKER_RE = re.compile(r"\[SHOT\s+\d+\]", re.IGNORECASE)


def script_narration(project) -> str:
    """Narration text from script.md: headings, comments and [SHOT n] markers removed."""
    script_path = project / "script.md"
    if not script_path.exists():
        sys.exit(f"Missing {script_path} — generate the script first.")
    lines = [l for l in script_path.read_text(encoding="utf-8").splitlines()
             if not l.strip().startswith(("#", "<!--", ">"))]
    text = MARKER_RE.sub(" ", "\n".join(lines))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text).strip()
    if not text:
        sys.exit("script.md has no narration text.")
    return text


def run(project_slug: str | None, voice: str | None = None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    dirs = project_dirs(project)

    text = script_narration(project)
    words = len(text.split())
    print(f"Narration: {words} words (~{words / 140:.1f} min at 140 wpm)")

    try:
        provider = ProviderFactory.get_voice_provider(cfg, voice_override=voice)
        provider.check_ready()
        dest = dirs["voiceover"] / f"voiceover{provider.output_suffix}"
        provider.synthesize(text, dest)
    except ProviderError as e:
        sys.exit(str(e))

    # Drop a stale sibling from a previous engine so `align` (which picks the
    # first audio file alphabetically) can't grab the wrong recording.
    for stale in dirs["voiceover"].glob("voiceover.*"):
        if stale != dest:
            stale.unlink()

    size = dest.stat().st_size / 1e6
    print(f"Voiceover ready: {dest} ({size:.1f} MB)")
    print("\nNext: python pipeline.py align")
