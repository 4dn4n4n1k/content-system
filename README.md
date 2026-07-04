# YouTube Content System (AI / IT / Cybersecurity)

Drop a YouTube link → research it → write an **original** script in your style →
AI-generate b-roll → render motion graphics + memes → AI voiceover → the system
auto-syncs visuals + captions to the narration and builds the final 1080p video.

The reference video is used **only** for its topic and structure. Script,
visuals, and audio are 100% original — no reused footage, no copyright strikes.

## One-time setup

```powershell
pip install -r requirements.txt
playwright install chromium
cd motion; npm install; cd ..   # Remotion, for animated motion graphics
copy .env.example .env    # then add your FAL_KEY (fal.ai) and PEXELS_API_KEY
```

Requires Python 3.11+, Node.js 18+, and ffmpeg on PATH (`winget install ffmpeg`).

- fal.ai key (pay-as-you-go AI video): https://fal.ai/dashboard/keys
- Pexels key (free stock footage): https://www.pexels.com/api/

## Making a video

| # | Stage | Who | Command / action |
|---|-------|-----|------------------|
| 1 | Ingest | you | `python pipeline.py ingest <youtube-url>` |
| 2 | Research | Claude | "run the research stage" (uses `prompts/research.md`) |
| 3 | Script | Claude + **you review** | "write the script" (uses `prompts/script_style.md`) — edit `script.md` freely |
| 4 | Director | auto + **you review** | `python pipeline.py director` — creative review of the script itself (hook, narrative, clarity, emotion, curiosity, visual potential) → `creative_report.md`. Fix the story while it's still cheap — before any shot list exists. |
| 5 | Shot list | Claude + **you approve** | "build the shot list" (uses `prompts/shot_prompts.md` + the director's visual opportunities) |
| 6 | Critic | auto + **you review** | `python pipeline.py critic` — editorial review of script + shot list (hook, pacing, diversity, narrative, retention risk, transition ideas) → `timeline_report.md`. Report-only: revise and rerun, or proceed. Costs nothing. |
| 7 | B-roll | auto | `python pipeline.py broll` (shows cost estimate, asks to confirm) |
| 8 | Graphics | auto | `python pipeline.py graphics` — animated motion-graphics cards via Remotion (stat count-ups, staggered diagrams) **and meme shots**: blank templates from Imgflip's free catalog with animated Impact captions, matched to the scene's beat (falls back to static cards if Node is unavailable) |
| 9 | Voiceover | auto | `python pipeline.py voiceover` — AI narration via Cartesia (default, channel voice set in `config.yaml`), with edge-tts (free) and ElevenLabs as alternates. (Prefer your own voice? Drop a recording in `assets/voiceover/` instead and skip this command.) |
| 10 | Align | auto | `python pipeline.py align` |
| 11 | Assemble | auto | `python pipeline.py assemble` → `output/final.mp4` |

`python pipeline.py status` shows where you are at any point.

## Tips

- **Providers:** every external service (video gen, voice, stock, memes, SFX) is
  swappable under `providers:` in `config.yaml` — change `active:` and rerun;
  no code edits. Per-provider settings sit under the provider's own key.
- **Voices:** the channel voice is `providers.voice.cartesia.voice_id` (needs
  CARTESIA_API_KEY). Free fallback: `providers.voice.active: edge`
  (`python -m edge_tts --list-voices` lists options); `elevenlabs` also supported.
- **Own voice instead:** drop any WAV/MP3 into `assets/voiceover/` — alignment is
  fuzzy, so you don't need to match the script word-for-word.
- **Music:** drop a royalty-free track into `projects/<slug>/assets/music/` before
  assembling; it's auto-looped and ducked under your voice.
- **Stock shots are chosen intelligently:** the pipeline expands your query into
  search concepts, scores every candidate (relevance, resolution, duration…), and
  prints why it picked what it picked. If no stock clip clears
  `asset_intelligence.fallback_threshold`, the shot is AI-generated instead — that
  cost shows up in the same broll confirmation. Set `asset_intelligence.enabled:
  false` for the old literal fetch.
- **Redo one clip:** delete `assets/broll/shot_NNN.mp4`, tweak its prompt in
  `shotlist.json`, rerun `broll` — only that clip regenerates. Same for segments
  in `output/segments/`.
- **Costs:** only stage 5 costs money (~$5–15 per 10-min video with the default
  budget model). Change the model under `providers.video.fal` in `config.yaml`
  (its `presets` key has ready options).
- **Captions:** karaoke word-by-word highlight by default; set `captions.style: block`
  in `config.yaml` for static chunks, or `assemble --no-captions` for none.
- **Sound design:** whooshes on cuts, impacts on stat/diagram cards, pops on memes,
  mixed automatically and normalized to -14 LUFS. The default sounds in `sfx/` are
  synthesized placeholders — drop better ones from any royalty-free pack over the
  same filenames (whoosh.wav / impact.wav / pop.wav, any source; 48 kHz 16-bit).

## Layout

```
pipeline.py          CLI (ingest | broll | graphics | align | assemble | status)
config.yaml          providers (video/voice/stock/meme/sfx), branding, captions…
system/              pipeline stages + static HTML card templates (fallback)
system/providers/    provider abstraction: base contracts, implementations,
                     ProviderFactory (add a provider = one module + one registry line)
motion/              Remotion project: animated card compositions (TitleCard,
                     StatCard, Diagram, QuoteCard, ListCard) — preview with
                     `cd motion && npm run dev`
prompts/             instructions Claude follows for research / script / shot list
sfx/                 transition/impact sounds (auto-generated; replace freely)
projects/<slug>/     everything for one video (script, assets, output)
```
