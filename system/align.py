"""Stage 8: align the recorded voiceover to the script.

- Transcribes the recording with faster-whisper (word timestamps, local CPU).
- Fuzzy-aligns transcript words to script words to find when each [SHOT n]
  marker is reached -> timing.json (drives the visual timeline).
- Emits captions.ass with short caption chunks synced to the recording.
"""
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from .util import load_config, load_shotlist, project_dirs, resolve_project, write_json  # noqa: F401

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")
MARKER_RE = re.compile(r"\[SHOT\s+(\d+)\]", re.IGNORECASE)


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def _parse_script(script_path: Path):
    """Return (words, markers) where markers = [(shot_n, word_index), ...]."""
    text = script_path.read_text(encoding="utf-8")
    # Drop markdown headings and comments; keep narration lines.
    lines = [l for l in text.splitlines()
             if not l.strip().startswith(("#", "<!--", ">"))]
    text = " ".join(lines)

    words, markers = [], []
    pos = 0
    for m in MARKER_RE.finditer(text):
        words.extend(w for w in text[pos:m.start()].split() if _norm(w))
        markers.append((int(m.group(1)), len(words)))
        pos = m.end()
    words.extend(w for w in text[pos:].split() if _norm(w))
    return [_norm(w) for w in words], markers


def _transcribe(audio: Path, model_size: str):
    from faster_whisper import WhisperModel

    print(f"Transcribing {audio.name} with faster-whisper ({model_size}, CPU int8)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), word_timestamps=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            if _norm(w.word):
                words.append({"word": w.word.strip(), "norm": _norm(w.word),
                              "start": round(w.start, 3), "end": round(w.end, 3)})
    return words, info.duration


def _ass_time(t: float) -> str:
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60); s = t - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_color(hex_color: str) -> str:
    """'#00e5a0' -> ASS inline colour '&HA0E500&' (BBGGRR)."""
    h = hex_color.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _clean(word: str) -> str:
    return word.upper().replace("{", "").replace("}", "").replace("\\", "")


def _write_captions(words: list[dict], path: Path, cfg: dict) -> None:
    cc = cfg["captions"]
    per_line = cc["words_per_line"]
    chunks, current = [], []
    for w in words:
        if current and (len(current) >= per_line or w["start"] - current[-1]["end"] > 0.8):
            chunks.append(current)
            current = []
        current.append(w)
    if current:
        chunks.append(current)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{cc['font']},{cc['font_size']},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,{cc['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    if cc.get("style", "karaoke") == "karaoke":
        # One event per spoken word: the whole chunk stays on screen while the
        # active word pops in the brand accent colour.
        accent = _ass_color(cfg["brand"]["accent"])
        for chunk in chunks:
            for j, w in enumerate(chunk):
                t0 = w["start"]
                t1 = chunk[j + 1]["start"] if j + 1 < len(chunk) else chunk[-1]["end"] + 0.15
                if t1 - t0 < 0.04:
                    t1 = t0 + 0.04
                parts = []
                for k, x in enumerate(chunk):
                    if k == j:
                        parts.append(f"{{\\1c{accent}\\fscx110\\fscy110}}{_clean(x['word'])}{{\\r}}")
                    else:
                        parts.append(_clean(x["word"]))
                lines.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},"
                             f"Cap,,0,0,0,,{' '.join(parts)}\n")
    else:  # block: one static event per chunk
        for chunk in chunks:
            text = _clean(" ".join(w["word"] for w in chunk))
            lines.append(f"Dialogue: 0,{_ass_time(chunk[0]['start'])},"
                         f"{_ass_time(chunk[-1]['end'] + 0.15)},Cap,,0,0,0,,{text}\n")
    path.write_text("".join(lines), encoding="utf-8")


def run(project_slug: str | None, audio: str | None = None) -> None:
    project = resolve_project(project_slug)
    cfg = load_config()
    dirs = project_dirs(project)

    if audio:
        audio_path = Path(audio)
    else:
        candidates = [f for f in sorted(dirs["voiceover"].iterdir())
                      if f.suffix.lower() in AUDIO_EXTS] if dirs["voiceover"].exists() else []
        if not candidates:
            sys.exit(f"No recording found. Record the script and drop the file into "
                     f"{dirs['voiceover']} (wav/mp3/m4a), or pass --audio <file>.")
        audio_path = candidates[0]

    script_path = project / "script.md"
    if not script_path.exists():
        sys.exit(f"Missing {script_path} — generate the script first.")
    script_words, markers = _parse_script(script_path)
    if not markers:
        sys.exit("script.md contains no [SHOT n] markers.")

    shot_numbers = {s["n"] for s in load_shotlist(project)["shots"]}
    spoken, duration = _transcribe(audio_path, cfg["whisper"]["model"])
    if not spoken:
        sys.exit("Whisper found no speech in the recording.")
    print(f"Recording: {duration:.1f}s, {len(spoken)} words. Script: {len(script_words)} words.")

    # Map script word index -> spoken word index via fuzzy sequence alignment.
    matcher = SequenceMatcher(a=script_words, b=[w["norm"] for w in spoken], autojunk=False)
    script_to_spoken: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            script_to_spoken[block.a + k] = block.b + k
    match_ratio = len(script_to_spoken) / max(len(script_words), 1)
    print(f"Word match: {match_ratio:.0%} (ad-libbing is fine; markers snap to nearest matched words)")

    shots = []
    last_start = 0.0
    for shot_n, word_idx in markers:
        if shot_n not in shot_numbers:
            print(f"WARNING: script references [SHOT {shot_n}] which is not in shotlist.json")
        matched = next((script_to_spoken[i] for i in range(word_idx, len(script_words))
                        if i in script_to_spoken), None)
        start = 0.0 if word_idx == 0 else (spoken[matched]["start"] if matched is not None else last_start)
        start = max(start, last_start)  # keep monotonic
        shots.append({"n": shot_n, "start": round(start, 3)})
        last_start = start
    shots[0]["start"] = 0.0

    timing = {"audio": str(audio_path), "duration": round(duration, 3), "shots": shots}
    write_json(project / "timing.json", timing)
    print(f"timing.json written — {len(shots)} shots over {duration:.1f}s")

    if cfg["captions"]["enabled"]:
        _write_captions(spoken, project / "captions.ass", cfg)
        print("captions.ass written")
    print("\nNext: python pipeline.py assemble")
