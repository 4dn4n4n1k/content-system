# contentsystem — Technical Overview

> Purpose of this document: a complete architectural description of the project for
> reviewers (human or AI) who do not have access to the source code. Everything
> described here is implemented and tested unless explicitly marked as *planned*.

---

# 1. Project Overview

**What it does.** `contentsystem` is a semi-automated production pipeline for long-form
YouTube videos (target niche: AI, IT, cybersecurity). The operator drops a YouTube URL
of a *reference* video; the system extracts its transcript and structure as research
material, an AI assistant (Claude Code, operating the repo) writes an original script
and shot list, and a Python CLI pipeline then generates all assets — AI b-roll clips,
animated motion-graphics cards, memes, AI voiceover — and assembles a finished
1080p30 MP4 with word-synced karaoke captions, sound effects, and normalized audio.

**Primary purpose.** Produce faceless explainer videos that are 100% original content
(no reuse of the reference video's footage or audio — copyright-safe and monetizable)
at a marginal cost of roughly **$5–15 per 10-minute video** (essentially just AI video
generation credits), with human review only at the two creative decision points.

**Target users.** A single operator (the repo owner) running a YouTube channel,
working inside Claude Code (the AI pair is a first-class part of the workflow, not an
add-on). Not multi-tenant, not a service.

**Development stage.** Working end-to-end prototype. Every pipeline stage has been
executed successfully against a test project (placeholder b-roll + real TTS, real
meme fetch, real card renders, real assembly). No real production video has been
produced yet; fal.ai (b-roll generation) is wired but has only been exercised up to
the cost-confirmation gate. No version control has been initialized yet.

---

# 2. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | None (deliberate). Interaction is a Python CLI + Claude Code chat. Remotion Studio (`npm run dev` in `motion/`) serves as a live preview UI for motion-graphics compositions. |
| Backend | Python 3.13 CLI (`pipeline.py`) with stage modules in `system/`. No server, no daemon. |
| Database | None. All state is plain files (JSON/Markdown/media) in per-project folders. See §9. |
| Authentication | None (single-user local tool). API keys via `.env`. See §10. |
| AI providers | **fal.ai** (text-to-video b-roll; default model ByteDance Seedance 1.0 Lite, hot-swappable), **Cartesia** (TTS, sonic-3, fixed channel voice), **edge-tts** (free TTS fallback), **ElevenLabs** (optional TTS fallback), **faster-whisper** (local speech-to-text alignment), **Claude Code** (research, scriptwriting, shot-list authoring, orchestration). |
| Video processing | **ffmpeg 8.1** (segment rendering, concat, filters, audio mix, loudnorm, caption burn-in), **Remotion 4 / React 19 / Node 24** (animated graphics cards rendered headlessly to MP4), **Playwright + Chromium** (static PNG card fallback), **Pillow** (image dimension probing). |
| Storage | Local filesystem only. Media assets stay inside each project folder. |
| Deployment | None — runs on the operator's Windows 11 machine. |
| Infrastructure | None beyond the local machine; all heavy generation is API-side (fal.ai, Cartesia). |
| Third-party APIs | fal.ai, Cartesia, Pexels (free stock video), Imgflip (free meme template catalog), YouTube via yt-dlp (metadata + subtitles), optional ElevenLabs. |

---

# 3. Folder Structure

```
contentsystem/
├── pipeline.py              # CLI entry point; argparse subcommands, lazy imports
├── config.yaml              # All tunables: video specs, models, brand, captions, sfx, audio
├── .env / .env.example      # API keys (see §16)
├── requirements.txt         # Python deps
├── PROJECT_OVERVIEW.md      # This document
├── README.md                # Operator manual: setup, workflow table, tips
├── system/                  # Python pipeline modules (one file per stage + shared)
│   ├── util.py              #   config load, project resolution, shotlist validation, asset paths
│   ├── ingest.py            #   yt-dlp metadata + transcript, bot-check fallback chain
│   ├── broll.py             #   b-roll stage: pending computation, cost gate, resume (provider-agnostic)
│   ├── graphics.py          #   card/meme rendering orchestration (Remotion primary, Playwright fallback)
│   ├── voiceover.py         #   voiceover stage: narration extraction, output management (provider-agnostic)
│   ├── align.py             #   faster-whisper transcription, script↔audio fuzzy alignment,
│   │                        #   timing.json + karaoke .ass caption generation
│   ├── assemble.py          #   per-shot segment renders, concat, SFX track, audio mix, final encode
│   ├── sfx.py               #   numpy event-track mixing (SFX sourcing is provider-side)
│   ├── status.py            #   per-project progress checklist
│   ├── templates/           #   Jinja2 HTML card templates (static fallback renderer)
│   ├── render_intelligence/ # Render Intelligence: per-shot render decisions -> render_plan.json
│   │   ├── planner.py       #   orchestrator: build_plan / ensure_plan (auto-replan when
│   │   │                    #   timing or asset kinds change); register() for future
│   │   │                    #   AI/vision planner passes that refine the plan dict
│   │   ├── models.py        #   CameraPlan, MotionPlan, ShotRender, CutPlan, SfxEvent,
│   │   │                    #   AudioPlan, RenderPlan (versioned JSON contract)
│   │   ├── timeline.py      #   shot skeletons + energy curve (type/duration/hook heuristic)
│   │   │                    #   + pattern-interrupt map and gap notes
│   │   ├── camera.py        #   Ken Burns for stills (rate/max/direction/pan, energy-scaled)
│   │   ├── motion.py        #   zoom punches on long holds + critic recommendations
│   │   ├── transitions.py   #   cut list + explicit SFX events (whoosh/impact/pop);
│   │   │                    #   unrenderable critic transitions carried as recommendations
│   │   ├── captions.py      #   enabled flag + per-shot emphasis from creative report
│   │   ├── audio.py         #   music level/fades, sfx level, loudnorm, duck placeholder
│   │   └── report.py        #   console summary of the plan
│   ├── director/            # Creative Director: script-level review, pre-shot-list (report-only)
│   │   ├── analyzer.py      #   orchestrator: ScriptDoc build (sections→sentences with
│   │   │                    #   estimated timestamps), plugin registry (register()), scoring
│   │   ├── models.py        #   Sentence, Section, ScriptDoc, Finding, VisualOpportunity
│   │   ├── rules.py         #   thresholds (config.yaml `director:`) + creative language
│   │   │                    #   signals (urgency, questions, explainers, comparisons, irony,
│   │   │                    #   tension/relief lexicons, jargon list); claim/callback/payoff
│   │   │                    #   patterns shared with the critic
│   │   ├── hook.py          #   claim placement, curiosity frame, urgency, concrete stakes
│   │   ├── narrative.py     #   chapter structure, phrase/word repetition, stat dumps,
│   │   │                    #   dry stretches, payoff distribution
│   │   ├── clarity.py       #   sentence length, unexplained jargon, abstraction, number load
│   │   ├── emotion.py       #   tension/relief arc: flat sections, abrupt jumps, missing relief
│   │   ├── curiosity.py     #   open loops planted vs resolved, premature reveals,
│   │   │                    #   unused stats from research.md
│   │   ├── visuals.py       #   visual opportunities with confidence (stat_card/diagram/
│   │   │                    #   timeline/comparison/quote/list/meme/broll) + dry sections
│   │   └── report.py        #   creative_report.json + operator-facing creative_report.md
│   ├── critic/              # Timeline Critic: pre-spend editorial review (report-only)
│   │   ├── analyzer.py      #   orchestrator: timeline build (script × shotlist × timing),
│   │   │                    #   plugin registry (register() for LLM/vision/analytics
│   │   │                    #   reviewers — same analyze() signature), retention risk, scoring
│   │   ├── models.py        #   Finding, ShotInfo, Timeline, CriticReport
│   │   ├── rules.py         #   configurable thresholds (config.yaml `critic:`) + language
│   │   │                    #   signal patterns (claims, callbacks, payoffs, serious topics)
│   │   ├── pacing.py        #   hook window, dead zones, slow runs, narration density
│   │   ├── diversity.py     #   type runs, template repeats, meme budget, near-dup prompts
│   │   ├── narrative.py     #   claim placement, visual↔narration match, chapter cards,
│   │   │                    #   unresolved callbacks, tonal clashes (meme-over-serious)
│   │   ├── transitions.py   #   recommendation-only: zoom punches, whips, reveals, separators
│   │   └── report.py        #   timeline_report.json + operator-facing timeline_report.md
│   ├── intelligence/        # Asset Intelligence: decision layer for stock shots
│   │   ├── __init__.py      #   AssetIntelligence facade (plan_shot / materialize, 2-phase)
│   │   ├── models.py        #   ShotBrief, AssetCandidate, ScoredCandidate, Selection, ShotPlan
│   │   ├── planner.py       #   deterministic NLP: token categorization + domain synonym
│   │   │                    #   expansion (subjects/environment/camera/emotion/lighting/motion);
│   │   │                    #   pluggable engine (future: LLM planner via same interface)
│   │   ├── search.py        #   fans concepts across StockProvider.search() capabilities,
│   │   │                    #   normalizes + dedupes into an AssetCandidate pool
│   │   ├── scorer.py        #   weighted scoring (relevance/resolution+orientation/duration/
│   │   │                    #   metadata/popularity/provider), config-tunable weights,
│   │   │                    #   score + confidence + human-readable reasons
│   │   ├── selector.py      #   best pick, or multi-clip stitching when the slot is long;
│   │   │                    #   low-confidence picks always carry an explanation
│   │   └── fallback.py      #   stock-vs-generate policy (fallback_threshold) + prompt builder
│   └── providers/           # provider abstraction layer (see §15 Design Decisions)
│       ├── __init__.py      #   ProviderFactory + registry (config.yaml providers.<kind>.active)
│       ├── errors.py        #   ProviderError / AuthenticationError / RateLimitError /
│       │                    #   TemporaryFailure / PermanentFailure (+ HTTP classifier)
│       ├── net.py           #   shared atomic streaming download
│       ├── base/            #   contracts: video.py voice.py stock.py meme.py sfx.py music.py
│       ├── video/fal.py     #   FalVideoProvider (model/params/cost from config)
│       ├── voice/           #   CartesiaVoiceProvider, EdgeVoiceProvider, ElevenLabsVoiceProvider
│       ├── stock/pexels.py  #   PexelsStockProvider
│       ├── meme/imgflip.py  #   ImgflipMemeProvider (catalog + fuzzy match)
│       └── sfx/synthesized.py # SynthesizedSfxProvider (ffmpeg lavfi placeholders)
├── motion/                  # Remotion project (Node/React) for animated graphics
│   ├── src/Root.tsx         #   composition registry (all 1920×1080@30, 450 frames)
│   ├── src/CardFrame.tsx    #   shared stage: grid bg, corner brackets, drift, kicker, riseIn
│   ├── src/brand.ts         #   Brand type + defaults mirroring config.yaml
│   ├── src/cards/           #   TitleCard, StatCard, Diagram, QuoteCard, ListCard, MemeCard
│   └── public/memes/        #   staged meme images for Remotion renders
├── prompts/                 # Instructions the AI assistant follows (see §6)
│   ├── research.md          #   research-stage procedure and output format
│   ├── script_style.md      #   channel voice/style profile, TTS-proofing rules, structure rules
│   └── shot_prompts.md      #   shot-list schema, visual style block, meme rules, duration budgeting
├── sfx/                     # whoosh.wav / impact.wav / pop.wav (auto-generated placeholders,
│                            #   replaceable with any 48 kHz 16-bit pack, same filenames)
├── .claude/skills/          # remotion-best-practices skill (official, installed via skills CLI)
└── projects/                # One folder per video (the "database", see §9)
    ├── .current             #   slug of the active project
    └── <slug>/
        ├── source.json      #   reference video metadata + transcript
        ├── research.md      #   fact-checked research notes (AI-written)
        ├── script.md        #   final narration script with [SHOT n] markers (AI-written, user-approved)
        ├── shotlist.json    #   per-shot generation spec (AI-written, user-approved)
        ├── timing.json      #   shot start times aligned to the voiceover
        ├── captions.ass     #   karaoke subtitles
        ├── assets/
        │   ├── broll/       #   shot_NNN.mp4 (fal.ai / Pexels)
        │   ├── graphics/    #   shot_NNN.mp4 (Remotion) or .png (fallback)
        │   ├── memes/       #   downloaded blank meme templates
        │   ├── voiceover/   #   voiceover.wav (Cartesia) or .mp3 (edge/11labs) or manual recording
        │   └── music/       #   optional music bed (first file is used)
        └── output/
            ├── segments/    #   per-shot normalized segments (render cache)
            ├── sfx_track.wav
            └── final.mp4
```

---

# 4. System Architecture

The system is a **file-driven batch pipeline** orchestrated at two levels:

1. **Creative orchestrator — Claude Code (AI assistant).** Runs the CLI stages in
   order, performs the non-mechanical stages itself (research, scriptwriting,
   shot-list authoring per the `prompts/` instruction files), and stops at two human
   checkpoints. Long-lived decisions (channel voice ID, model choice, meme rules) are
   persisted in Claude's project memory so any future session resumes the same playbook.
2. **Mechanical orchestrator — `pipeline.py`.** Stateless argparse CLI dispatching to
   `system/*.py`. All state lives on disk; every stage is idempotent/resumable by
   checking output-file existence (and, for assembly segments, duration match).

**Complete request flow (one video):**

```
User drops YouTube URL
→ `pipeline.py ingest <url>`         : yt-dlp pulls metadata + English subtitles (json3),
                                       falls back web→android client→browser cookies when
                                       bot-checked; writes source.json; sets projects/.current
→ Claude: research                   : web-searches to fact-check/update claims, adds angles
                                       → research.md
→ Claude: script                     : original narration in channel style, [SHOT n] markers
                                       → script.md            ★ CHECKPOINT 1: user edits/approves
→ `director`                         : deterministic creative review of the script only
                                       (hook, narrative, clarity, emotion, curiosity, visual
                                       potential with confidence ratings)
                                       → creative_report.{json,md}; report-only — revise the
                                       script before any shot-list work
→ Claude: shot list                  : one entry per marker: type ai|stock|diagram|meme with
                                       crafted prompts/fields → shotlist.json
                                                              ★ CHECKPOINT 2: user approves (cost gate)
→ `critic`                           : deterministic editorial review of script + shot list
                                       (hook, pacing, diversity, narrative, retention risk,
                                       transition recommendations) → timeline_report.{json,md};
                                       report-only — the operator decides whether to revise
                                       before any generation money is spent
→ `broll`                            : fal.ai generation for `ai` shots (cost preview + y/N
                                       confirm, per-shot resume, failures retryable);
                                       `stock` shots go through Asset Intelligence:
                                       plan concepts → search providers → score → select →
                                       download, or transparent AI-generation fallback when
                                       stock quality is below threshold (fallback cost is
                                       included in the same confirm gate)
→ `graphics`                         : diagram/meme shots → Remotion render to 15 s MP4 cards
                                       (Playwright PNG fallback); memes: Imgflip template
                                       fetch + fuzzy match + Impact-caption overlay
→ `voiceover`                        : script minus markers/headings → Cartesia sonic-3
                                       (channel voice, paragraph-chunked raw PCM → WAV)
→ `align`                            : faster-whisper word timestamps; fuzzy-match script
                                       words to spoken words (difflib); each [SHOT n] marker
                                       snaps to its word's start time → timing.json;
                                       word-level karaoke captions → captions.ass
→ `renderplan`                       : Render Intelligence: shotlist + timing + both editorial
                                       reports → render_plan.json (camera moves, zoom punches,
                                       explicit SFX events, music fades, energy curve, caption
                                       emphasis, transition recommendations). Auto-run by
                                       assemble; rerun manually after config tuning
→ `assemble`                         : EXECUTES render_plan.json: per-shot segments (Ken Burns
                                       from camera plan, zoom punches from motion plan,
                                       signature sidecars re-render exactly what changed),
                                       concat demuxer, plan's SFX event track + music fades,
                                       loudnorm −14 LUFS, .ass burn-in → output/final.mp4
```

Segment renders are cached; re-running `assemble` after a voiceover change re-renders
only shots whose duration changed (validated via ffprobe against the new timing).

---

# 5. Features

**Implemented:**
- Reference-video ingest via yt-dlp: metadata, chapters, manual or auto captions
  (json3→parsed transcript), YouTube bot-check fallback chain (web → android player
  client → cookies from Firefox/Edge/Chrome, configurable browser).
- Project management: slug folders, `.current` pointer, `status` checklist command.
- AI b-roll via fal.ai: model-agnostic (model ID + params + $/s estimate in
  config.yaml, presets for Seedance Lite / Kling / WAN), global visual `style_block`
  prepended to every prompt, cost preview with interactive confirm (`--yes` to skip),
  `--only N…` partial runs, per-shot resume, per-shot failure isolation.
- Free stock b-roll via Pexels (landscape HD, `pick` index to choose among results).
- **Creative Director** (`pipeline.py director`, config `director:`): deterministic
  script-level creative review before shot-list work — no LLM, no vision, no
  external calls. Parses script.md into sections/sentences with word-count
  timestamps; reads research.md when present. Checks: hook (strongest-claim
  placement incl. word-form numbers, curiosity frame by 45s, urgency, concrete
  stakes in the first 30s), narrative (chapter structure, section balance, n-gram
  phrase repetition, word overuse, stat dumps, fact-dry stretches, payoff
  backloading), clarity (long-sentence share, unexplained jargon vs a 40-term
  lexicon with explainer detection, abstraction density, >2 numbers per sentence),
  emotion (tension/relief lexicon arc: flat sections, abrupt jumps, missing
  relief), curiosity (open loops planted vs resolved in the back half, premature
  reveals, unused stats from research.md), and visual potential (confidence-rated
  opportunities: stat_card, diagram, timeline, comparison, quote_card, list, meme,
  b-roll — kinds map 1:1 to what the pipeline renders, so the shot-list stage can
  consume the report directly). Outputs creative_report.{json,md}. Report-only;
  reviewer plugins register via `director.analyzer.register()`.
- **Timeline Critic** (`pipeline.py critic`, config `critic:`): deterministic
  pre-spend editorial review — no LLM, no vision. Joins script.md, shotlist.json
  and timing.json (falls back to word-count duration estimates at `critic.wpm`).
  Checks: hook window (cut count, shot holds, early memes, strongest-claim
  placement via a claim-signal pattern), pacing (dead zones, slow runs, narration
  wpm bounds), visual diversity (type runs, template repeats, meme budget/adjacency,
  near-duplicate prompts by Jaccard), narrative (visual↔narration keyword match,
  un-carded chapter changes, unresolved callbacks, meme-over-serious tonal clash),
  retention (static sequences, pattern-interrupt gaps, reveals without visual
  payoff → 0-100 risk score), transitions (recommendation-only: zoom punches,
  whips, reveal beats, title cards, chapter separators). Outputs
  timeline_report.json + operator-facing timeline_report.md with overall score,
  category scores, findings by severity, and a per-shot timeline table. Never
  modifies project files; reviewer plugins (LLM/vision/analytics) register via
  `critic.analyzer.register()` with the same `analyze(timeline, script, rules)`
  signature.
- **Asset Intelligence** (config `asset_intelligence`, on by default): for each stock
  shot — deterministic planner expands the query into ranked search concepts via a
  domain lexicon (AI/IT/cyber synonyms + camera/lighting/emotion/motion vocabulary);
  a search engine fans concepts across all searchable stock providers (capability
  method `StockProvider.search()`, providers without it are skipped); a weighted
  scorer (configurable weights) rates relevance, resolution+orientation, duration
  fit, metadata completeness, popularity, provider confidence and emits
  score/confidence/reasons; a selector picks the winner or stitches up to
  `max_clips` near-best clips when the slot is much longer than any single clip;
  below `fallback_threshold` the shot is transparently AI-generated instead (prompt
  built from the planner's brief + global style block), with the cost added to the
  existing broll confirm gate. Legacy direct fetch remains via `enabled: false`.
- Animated motion graphics via Remotion (five card types: title, stat with numeric
  count-up parsing (`$4.9M`, `4B+`, `1,200`), diagram with staggered nodes/arrows,
  quote, list) sharing a branded stage (grid, corner brackets, slow drift so held
  frames never freeze); brand palette/fonts injected from config.yaml as props.
- Meme shots: Imgflip top-100 catalog (no key), fuzzy template-name matching,
  `image_url` override, Pillow-based display sizing, animated MemeCard (pop-in +
  Impact-font top/bottom captions), static HTML fallback; editorial meme rules
  encoded in `prompts/shot_prompts.md`.
- Static graphics fallback: Jinja2 HTML templates → Playwright screenshot → PNG,
  animated at assembly with ffmpeg zoompan (used when Node/Remotion is unavailable;
  `graphics.renderer: static` forces it).
- AI voiceover: Cartesia sonic-3 with a fixed channel voice ID (default engine;
  paragraph-chunked raw-PCM requests concatenated with 0.35 s breaths), edge-tts free
  fallback (voice/rate/pitch configurable, `--voice` CLI override), ElevenLabs
  optional; manual recording drop-in still supported (align is engine-agnostic).
- Voiceover↔script alignment: faster-whisper (small, int8, CPU), word-level
  timestamps, fuzzy script matching robust to ad-libs (reports match %), marker
  snapping, per-shot timing map.
- Karaoke captions: one ASS event per spoken word; active word in brand accent color
  at 110% scale, white bold outline otherwise; `block` style available; burn-in at
  assembly (`--no-captions` to skip).
- Sound design: auto-synthesized default SFX (ffmpeg lavfi) — whoosh on every cut,
  impact when diagram cards land, pop on meme slams — mixed via a numpy-built event
  track; files user-replaceable; volumes configurable.
- Audio mastering: voice + music bed + SFX mixed (amix, resampled 48 kHz) and
  normalized to −14 LUFS / −1.5 dBTP (YouTube loudness target); music auto-ducking by
  static volume (side-chain planned).
- **Render Intelligence** (`pipeline.py renderplan`, config `render:`): plans how
  every shot renders before the assembler touches ffmpeg — Ken Burns parameters for
  stills (rate/max/direction/pan, defaults reproduce the historical look), zoom
  punches on b-roll holds ≥10s (plus Timeline Critic zoom-punch recommendations),
  explicit SFX events replacing hardcoded assembler logic, music fade in/out
  timing, per-shot energy curve (type/duration/hook heuristic) with
  pattern-interrupt map, caption emphasis from the Creative Director's stat beats,
  and cut-level transition recommendations carried (not yet renderable) → all in a
  versioned render_plan.json. `ensure_plan()` auto-replans when timing or asset
  kinds change, so `assemble` needs no extra steps. Future AI/vision planner passes
  register via `render_intelligence.planner.register()` and refine the plan dict.
- Assembly engine: executes render_plan.json — per-segment normalization
  (loop-or-trim to aligned duration, scale/crop to 1920×1080@30, camera/motion
  filters from the plan), concat demuxer, single final encode (libx264 CRF 19,
  AAC 192k, +faststart). Segment invalidation by plan-signature sidecars: a changed
  plan re-renders exactly the affected segments.

**Planned (user-approved roadmap, in priority order):**
- Thumbnail + title system: fal.ai image gen + text compositing, 3 variants/video;
  title rules in the research stage.
- Retention lint: analyzer flagging slow hooks, shots >6 s in minute one, >12 s dead
  zones, missing open loops — run before money is spent.
- Hook template: enforced cold-open structure (3 fast shots + strongest claim).
- Zoom punches on cuts; whip/glitch chapter transitions (currently hard cuts only).
- Shorts generator: 2–3 vertical 9:16 clips per video with big captions.
- Auto-metadata: chapters from timing.json, description/tags, end-screen card.
- Voice audition helper; music arcs (energy shifts at chapter boundaries).

---

# 6. AI Workflow

Three distinct AI roles:

1. **Claude Code as creative agent + orchestrator.** Not a runtime API call — the
   assistant works in the repo. Its behavior is programmed by three prompt files it
   must follow (they function as the "prompts" of the system):
   - `prompts/research.md`: verify every factual claim in the reference transcript
     via web search, refresh stale stats to current values with sources, find 2–3
     angles the reference missed, output structured research.md.
   - `prompts/script_style.md`: channel voice definition (direct, curious,
     slightly ominous for cyber topics), structural rules (cold-open hook, open
     loops between sections, "but/therefore not and-then"), TTS-proofing rules
     (numbers as words, "A.I." periods for pronunciation, punctuation as pacing),
     `[SHOT n]` marker placement conventions.
   - `prompts/shot_prompts.md`: shotlist.json schema; the reusable cinematic
     `style_block` (color grade, lens, lighting descriptors) that keeps ~40–60
     independently generated clips visually coherent; per-shot prompt-writing
     guidance; meme editorial rules (beat-relevance requirement, 1–3 per video,
     structure-matching of template to joke logic, never in hook/serious segments);
     duration budgeting against narration length.
   Cross-session continuity comes from Claude's project memory (channel voice ID,
   model/cost decisions, roadmap state, review-checkpoint discipline).
2. **Generative APIs in the pipeline** (details §8): fal.ai text-to-video, Cartesia
   TTS, optional ElevenLabs, edge-tts.
3. **Local ML**: faster-whisper small (int8, CPU) for transcription/alignment — the
   only on-device model; also transcribes reference videos that lack captions
   (planned use; currently subtitles are the ingest path).

Automation boundary: everything after shot-list approval is fully autonomous
(`broll --yes && graphics && voiceover && align && assemble`); before it, deliberately
human-gated.

---

# 7. Services (modules and responsibilities)

| Module | Responsibility |
|---|---|
| `pipeline.py` | CLI parsing; lazy stage imports (ingest works before heavy deps install); project flag plumbing. |
| `system/util.py` | ROOT/paths, `.env` loading, config.yaml loading, slugify, current-project pointer, per-project dir creation, shotlist load + validation (types, duplicate shot numbers), shot→asset-path resolution (including diagram/meme mp4-else-png logic), JSON I/O. |
| `system/ingest.py` | Metadata probe; subtitle download (en variants, json3); json3→transcript parsing; bot-check fallback chain (web → android client → browser cookies, order/browser configurable via `ingest.cookies_from_browser`); source.json authoring. |
| `system/broll.py` | Pending-shot computation (resume); FAL_KEY/PEXELS key checks; cost estimate + confirm gate; fal_client.subscribe per shot with style_block prepend and per-shot duration; Pexels search/pick/download nearest-1080p file; streaming downloads with `.part` atomic rename; failure collection + nonzero exit for retry loops. |
| `system/graphics.py` | Renderer selection (motion vs static); Remotion invocation per card (`npx remotion render <Comp> out.mp4 --props=<json>` with cwd=motion/, 15-min timeout, props temp-file lifecycle); meme staging into `motion/public/`; per-shot fallback to static on Remotion failure; Playwright/Jinja2 static path (memes embedded as data URIs). |
| `system/memes.py` | Imgflip `get_memes` catalog fetch (cached per process); substring-then-`difflib` fuzzy name match; `image_url` passthrough; template download; Pillow `display_box` fit (1150×720) so low-res memes fill the frame. |
| `system/voiceover.py` | script.md → narration text (strip headings/markers/comments); engine dispatch; Cartesia: paragraph/sentence chunking ≤2000 chars, raw PCM s16le 44.1 kHz requests, WAV concat with 0.35 s pauses, stale-mp3 cleanup; edge-tts async synthesis; ElevenLabs REST; word-count/duration estimate output. |
| `system/align.py` | faster-whisper transcription (word timestamps); script word extraction; difflib-based sequence matching (tolerates ad-libbing, reports %); marker→word-time snapping; timing.json (shot n → start seconds, total duration, audio path); ASS generation — karaoke (event per word, accent \1c + \fscx110 on active word) or block style; ASS color conversion from brand hex. |
| `system/assemble.py` | timing+shotlist join; segment render (video: stream_loop+trim+scale/crop+fps+setsar; image: zoompan drift) with duration-mismatch cache invalidation (ffprobe); concat demuxer; SFX event derivation from timeline (whoosh/impact/pop with per-type offsets and gains); filter_complex assembly (aresample per input, amix normalize=0, loudnorm I=-14:TP=-1.5:LRA=11); subtitle burn-in with cwd-relative .ass path (Windows filter-escaping avoidance); final encode settings; run log. |
| `system/sfx.py` | One-time synthesis of default whoosh/impact/pop via ffmpeg lavfi recipes; strict 48 kHz/16-bit input contract with convert hint; numpy int32 accumulation mixing of (time, name, gain) events; clip to int16 WAV. |
| `system/status.py` | 9-step per-project checklist with file-existence checks and next-command hints. |
| `motion/` (Remotion) | Deterministic frame-based animation (skill rules: interpolate + bezier easing, no CSS transitions); prop-driven compositions; brand as props so config.yaml is the single source of truth. |

---

# 8. APIs

**Integrated:**
| API | Auth | Use | Cost |
|---|---|---|---|
| fal.ai (`fal-client`) | `FAL_KEY` | Text-to-video b-roll; model set in config (`fal-ai/bytedance/seedance/v1/lite/text-to-video` default; Kling/WAN presets) | ~$0.03–0.10/s of video; ~$5–15 per 10-min video |
| Cartesia `POST /tts/bytes` | `CARTESIA_API_KEY` (Bearer), `Cartesia-Version: 2026-03-01` | Default voiceover; model `sonic-3` (configurable), fixed voice id `146485fd-8736-41c7-88a8-7cdd0da34d84`, raw PCM output | per-character credits |
| Pexels Videos `GET /videos/search` | `PEXELS_API_KEY` | Free stock b-roll | free |
| Imgflip `GET /get_memes` | none | Top-100 blank meme templates (captioning done locally, not via their paid caption API) | free |
| YouTube (via yt-dlp, no official API) | none / optional browser cookies | Reference metadata + subtitles | free |
| edge-tts (unofficial Microsoft endpoint) | none | Free TTS fallback | free |
| ElevenLabs TTS REST | `ELEVENLABS_API_KEY` | Optional premium TTS | subscription |

**Planned:** fal.ai image models (thumbnails); possibly YouTube Data API (upload,
metadata, analytics readback for the retention feedback loop).

---

# 9. Database

No DBMS. State is **files with implicit schemas**; the per-project folder is the
aggregate root. Relationships are by shot number `n` across files.

- **`source.json`** — `{id, url, title, channel, duration_s, upload_date, view_count,
  description, chapters[], transcript[{start, text}], transcript_text}`.
- **`script.md`** — Markdown; narration paragraphs interleaved with `[SHOT n]`
  markers; headings/blockquotes are non-narration (stripped by voiceover/align).
- **`shotlist.json`** — `{style_block, shots[]}`; shot variants:
  - `{n, type:"ai", prompt, duration?}`
  - `{n, type:"stock", query, pick?}`
  - `{n, type:"diagram", template:"title_card|stat_card|diagram|quote_card|list_card", fields{…}}`
  - `{n, type:"meme", template|image_url, top?, bottom?}`
  Validation: unique `n`, known `type`. `n` joins to `script.md` markers and asset
  filenames `shot_NNN.*`.
- **`timing.json`** — `{audio: <path>, duration, shots:[{n, start}]}` (seconds,
  ordered; each shot ends where the next begins, last ends at audio end).
- **`captions.ass`** — generated artifact (karaoke events), regenerated by `align`.
- **`projects/.current`** — plain-text slug of the active project.
- **Render caches:** `assets/**/shot_NNN.*` (existence = done) and
  `output/segments/shot_NNN.mp4` (existence + duration match = reusable).

Claude-side persistent memory (outside the repo) stores operator preferences and
decisions; it is documentation-like, not runtime state.

---

# 10. Authentication

None in-app: local, single-user CLI. Secrets are environment variables loaded from a
git-ignored `.env` via python-dotenv at import of `system/util.py`. Provider auth:
fal.ai key via env (`fal-client` reads `FAL_KEY`), Cartesia Bearer token, Pexels
header key, ElevenLabs header key. yt-dlp can optionally read browser cookies
(Firefox/Edge/Chrome) to pass YouTube bot checks — the only user-credential touchpoint,
and it stays local. If this ever becomes multi-user/hosted, all keys move server-side
behind a real auth layer (see §20).

---

# 11. Video Generation Pipeline (prompt → rendered video)

1. **Shot prompt authoring** (AI): each `ai` shot gets a specific prompt; the global
   `style_block` (grade/lens/lighting vocabulary) is prepended at generation time so
   independently generated clips cut together coherently.
2. **Clip generation:** `fal_client.subscribe(model, arguments={prompt, resolution,
   duration…})` → result URL → streamed download → `assets/broll/shot_NNN.mp4`
   (5 s, 720p default). Resume = skip existing files; failures don't halt the batch.
3. **Cards:** Remotion renders `--props`-parameterized compositions to 15 s
   1080p30 MP4s: ~1.5 s entrance animation, then slow scale drift (so trims/holds
   never look like freeze-frames). Memes ride the same path with the fetched template
   + animated Impact captions.
4. **Voiceover:** Cartesia chunks → PCM → single WAV (44.1 kHz mono).
5. **Alignment:** whisper word timestamps; each `[SHOT n]` snaps to the start time of
   the first script word following it (fuzzy-matched to spoken words). Shot durations
   are therefore *derived from actual narration pace*, not guessed up front.
6. **Segment normalization:** every shot rendered to an exact-duration 1920×1080@30
   segment — videos `stream_loop`ed and trimmed (a 5 s clip can fill an 8 s slot;
   card entrance animations survive because trims cut tails, not heads), PNGs get
   ffmpeg `zoompan`.
7. **Timeline:** concat demuxer over segments (no re-encode at this step).
8. **Audio:** numpy-mixed SFX event track (whoosh at cut−0.12 s; impact at
   card+0.2 s; pop at meme+0.55 s) + voiceover + optional looped music →
   `amix` (48 kHz) → `loudnorm I=-14 TP=-1.5 LRA=11`.
9. **Final encode:** caption burn-in (`ass=`), libx264 CRF 19 medium, AAC 192k,
   `+faststart` → `output/final.mp4`. Measured on test render: −15.3 LUFS integrated,
   −1.5 dBTP.

---

# 12. Current Architecture Diagram

```
                                  ┌────────────────────────────┐
                                  │   Operator (Claude Code)   │
                                  │ research · script · shots  │
                                  │  runs stages · 2 checkpts  │
                                  └─────┬──────────────────────┘
                                        │ writes research.md / script.md / shotlist.json
                                        ▼
 YouTube ──yt-dlp──► ingest ──► projects/<slug>/source.json
 (ref video)                        │
                                    │            .env keys        config.yaml
                                    ▼                │                │
        ┌─────────────── pipeline.py (stateless CLI dispatcher) ─────┘
        │            │             │              │            │
        ▼            ▼             ▼              ▼            ▼
      broll       graphics     voiceover        align       assemble
        │            │             │              │            │
   ┌────┴───┐   ┌────┴─────┐   ┌───┴────────┐    │       ┌────┴─────────────┐
   ▼        ▼   ▼          ▼   ▼            ▼    ▼       ▼                  ▼
 fal.ai  Pexels Remotion Imgflip Cartesia edge-tts faster-whisper   ffmpeg (segments,
 (t2v)   (stock)(Node/    (memes) sonic-3 (fallbk) (local, CPU)     concat, SFX+amix,
   │        │   React)      │       │        │    word timestamps   loudnorm, ass burn)
   ▼        ▼     ▼         ▼       ▼        ▼         │                  │
 assets/broll  assets/graphics   assets/voiceover  timing.json        output/final.mp4
                                                   captions.ass       (1080p30, −14 LUFS)
```

---

# 13. Future Roadmap

Near-term (approved, ordered): thumbnail+title system → retention lint → hook
template → zoom punches/transitions → Shorts generator → auto-metadata/chapters.
Supporting: voice audition, music arcs, better SFX pack, first real production video
(3-min pilot before 10-min scale).

Architectural candidates (not committed): git init + CI checks; schema validation
(pydantic/zod) at checkpoint boundaries; parallel fal.ai generation; YouTube upload +
analytics readback closing the retention loop; a thin local web dashboard replacing
CLI status; extraction of the video-model client behind an interface (fal today,
direct provider APIs tomorrow).

---

# 14. Current Problems

- **No version control.** The repo has never been `git init`-ed. Highest-priority debt.
- **No automated tests.** Verification is manual end-to-end runs on a test project.
  align (fuzzy matching) and assemble (filtergraph builder) most need unit coverage.
- **Placeholder SFX** are ffmpeg-synthesized and audibly cheap; intended to be
  replaced by a real royalty-free pack (drop-in by filename).
- **fal.ai path untested past the cost gate** (no key/credits yet): the subscribe →
  download → resume flow is written but has not produced a real clip.
- **Result-shape assumptions:** fal response parsing assumes `result["video"]["url"]`
  (or plain string) — some models return different shapes; needs per-model tolerance.
- **Meme catalog ceiling:** Imgflip top-100 only (plus manual `image_url`); niche
  memes need the manual path.
- **Single-pass loudnorm** lands ~1 LU off target (−15.3 measured vs −14); two-pass
  (measure → apply) would be exact.
- **Hard cuts only**; no transitions/zoom punches yet (roadmap).
- **Windows-coupled:** Segoe UI/Consolas/Impact font assumptions, PowerShell-ish
  docs; Linux/macOS would need font + doc adjustments.
- **CPU-bound local renders:** Remotion cards ≈1–3 min each; whisper small ≈
  real-time×0.3–1 on CPU. Fine at current scale, slow at 10× volume.
- **Alignment edge cases:** heavy ad-libbing or TTS mispronunciations can shift
  marker snapping; 99% match on tests, but no guardrail metric fails the stage yet
  (it only prints the %).
- **No retention analytics loop** — the system optimizes for best practices, not yet
  against real audience data.
- **Script↔shotlist consistency** is by convention (markers ↔ `n`); a mismatch warns
  but nothing auto-repairs.

---

# 15. Design Decisions

- **Files over database:** single operator, few dozen projects, everything inspectable
  and editable at checkpoints in a text editor; resume logic = file existence. A DB
  adds ops burden with zero benefit at this scale.
- **Two-level orchestration (AI + CLI)** rather than a workflow engine: creative
  stages need judgment; mechanical stages need determinism. n8n/Airflow would add
  infrastructure without improving either.
- **fal.ai as video-gen aggregator:** one key, many models, hot-swappable via config;
  survives the fast-moving model market without code changes (user constraint:
  low cost + full API automation; Google Flow was rejected for having no API).
- **Cartesia for voice:** operator-chosen fixed voice = channel identity; raw-PCM
  chunked requests avoid server-side length limits and give exact concat control.
  edge-tts kept as the zero-cost fallback; manual recordings still work because
  alignment is engine-agnostic (whisper doesn't care who spoke).
- **Whisper alignment instead of TTS-reported timestamps:** decouples timing from
  the TTS engine, so swapping voice engines (or using human recordings) never touches
  the timing/caption code.
- **Remotion for graphics:** deterministic frame-based React animation, parameterized
  by props (data-driven cards from shotlist JSON), live-previewable in Studio;
  official agent skill installed to keep generated code idiomatic. Playwright static
  fallback retained so the pipeline degrades gracefully without Node.
- **Segment-then-concat assembly** (vs one giant filtergraph): resumable, debuggable
  per shot, avoids fragile 60-input filter graphs; single final encode preserves quality.
- **ASS karaoke captions** (vs Remotion-rendered captions): libass burn-in is fast,
  word-timing comes free from whisper, and styling is data (regenerating captions
  doesn't re-render any video).
- **Provider abstraction layer (2026-07-04 refactor):** every external service
  sits behind an ABC contract in `system/providers/base/` (video, voice, stock,
  meme, sfx, music) with concrete implementations selected by
  `ProviderFactory` from `config.yaml providers.<kind>.active`. Stages contain
  only pipeline logic and never import SDKs; providers translate all SDK/HTTP
  errors into a shared taxonomy (`ProviderError` → `AuthenticationError` /
  `RateLimitError` / `TemporaryFailure` / `PermanentFailure`). Adding e.g. a
  RunwayProvider = one module + one registry line; hot-swapping = one YAML edit.
  Providers import their SDKs lazily, so only the active provider's dependency
  loads. This satisfies dependency inversion / open-closed and makes stages
  testable with in-memory fakes.
- **Copyright-safe by construction:** reference content is used only as transcript
  research; every rendered byte (clips, cards, voice, memes-with-our-captions) is
  generated. This was a hard requirement to keep monetization safe.
- **Cost gate as UX:** the only interactive prompt in the pipeline is the one that
  spends money.

---

# 16. Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `FAL_KEY` | for `broll` ai shots | fal.ai API key (video generation) |
| `CARTESIA_API_KEY` | for default voiceover | Cartesia TTS (sonic-3, channel voice) |
| `PEXELS_API_KEY` | for `stock` shots | Pexels free stock video search/download |
| `ELEVENLABS_API_KEY` | optional | Only if `voiceover.engine: elevenlabs` |

(`.env` at repo root, loaded by python-dotenv; `.env.example` documents them; no
secrets in config.yaml. Non-secret tuning — models, voice id, brand, volumes — lives
in `config.yaml`.)

---

# 17. Dependencies

**Python** (`requirements.txt`): `yt-dlp` (ingest), `fal-client` (b-roll),
`faster-whisper` (alignment; CTranslate2 int8 CPU inference — chosen over
openai-whisper for speed and Python 3.13 wheels), `edge-tts` (free TTS),
`requests` (Cartesia/Pexels/Imgflip/downloads), `pyyaml` (config), `jinja2`
(static card templates), `playwright` (static renderer), `python-dotenv` (.env),
`pillow` (meme sizing), `numpy` (SFX mixing; already a whisper transitive dep).

**Node** (`motion/package.json`): `remotion` + `@remotion/cli` 4.0.484, `react`/
`react-dom` 19.2.3, TypeScript 5.9; scaffolded by `create-video` (blank template).

**System:** ffmpeg 8.1 (gyan.dev full build) on PATH; Python 3.13.7; Node 24;
Chromium via `playwright install chromium`.

**Claude Code assets:** `remotion-best-practices` skill (official, from
remotion-dev/skills) governing all Remotion code written by the assistant.

---

# 18. Development Workflow

- Built interactively inside Claude Code on Windows 11: plan-mode design → approved
  plan → implementation → **verification by execution** (every feature was proven by
  running the pipeline on a `test-video` project with placeholder clips and real
  TTS/meme/card/assembly output, frame-extracting results with ffmpeg and visually
  checking them, measuring loudness with ffmpeg loudnorm).
- No CI/CD, no test suite, no build step for Python; Remotion type-checked with
  `tsc --noEmit` and previewed in Remotion Studio.
- "Deployment" = the working folder itself. Setup on a fresh machine: install
  Python 3.11+/Node/ffmpeg → `pip install -r requirements.txt` →
  `playwright install chromium` → `npm install` in `motion/` → copy `.env.example`
  to `.env` and fill keys.
- Conventions: stage modules own their stage end-to-end; config.yaml is the single
  tuning surface; all generated artifacts are disposable caches except the four
  reviewed files (research/script/shotlist/config).

---

# 19. Future AI Plans

- **Deeper agent orchestration:** the assistant already runs the full post-approval
  chain autonomously; a natural next step is a scheduled cloud agent (Claude Code
  `/schedule` routine) producing weekly draft packages (research + script + shotlist)
  for async human review, with generation still gated on approval.
- **Retention feedback loop:** pull YouTube Analytics after publishing; feed
  audience-retention curves back into `prompts/` (hook style, pacing rules) —
  turning the style guide into a learned artifact.
- **Retention lint as an AI pass:** beyond mechanical checks, have the assistant
  critique the script against retention heuristics before checkpoint 1.
- **MCP integrations:** currently none are load-bearing (Higgsfield/Picsart/Figma
  connectors exist in the environment but were deliberately not used — fal.ai was
  cheaper and scriptable). Candidate future MCPs: YouTube upload/analytics, a music
  library service.
- **Model routing:** per-shot model choice (cheap model for ambient shots, premium
  for hero shots) once real-video quality data exists.

---

# 20. Recommendations

**Immediate (cheap, high value):**
1. `git init` + first commit + `.gitignore` is already written — do this before any
   further work; add a pre-commit `tsc --noEmit` for `motion/`.
2. Unit tests for the two algorithmic hotspots: `align` (marker snapping under
   ad-lib/mismatch fixtures) and `assemble`'s timeline math (duration derivation,
   cache invalidation). Both are pure enough to test without media.
3. Schema-validate `shotlist.json` and `timing.json` with pydantic at load; fail
   with actionable messages at the checkpoint instead of mid-generation.
4. Make the alignment match % a hard gate (e.g., <90% aborts with guidance) rather
   than a printed note.
5. Two-pass loudnorm for exact −14 LUFS.
6. Replace placeholder SFX with a curated pack (same filenames — zero code).

**Scalability (when volume grows):**
7. Parallelize fal.ai generation (it's I/O-bound; a small worker pool with the same
   resume semantics would cut b-roll wall time ~5×).
8. Cache the whisper model instance across runs (or move align to a persistent
   worker) if producing multiple videos per day.
9. GPU or cloud render for Remotion cards if card count grows (Remotion Lambda
   exists for exactly this).
10. ~~Introduce a `providers/` abstraction over text-to-video~~ — **done** (all six
    external service kinds are behind contracts + factory; see §15). Per-shot
    model routing (§19) is now a stage-level change only.

**Robustness:**
11. Normalize fal result parsing across model families (inspect a few models'
    response schemas; tolerate `video.url`, `videos[0].url`, string).
12. Record a per-shot generation manifest (model, prompt, cost, seed if available)
    next to each clip — reproducibility and spend auditing.
13. Add `--dry-run` to `assemble` printing the timeline table (shot, source, start,
    duration) for pre-render sanity checks.

**Product:**
14. Build the thumbnail/title stage before scaling output — CTR compounds every
    other investment; a great video with a weak package underperforms.
15. Produce the 3-minute pilot video end-to-end before adding more features; real
    footage will reprioritize the roadmap better than any planning.
