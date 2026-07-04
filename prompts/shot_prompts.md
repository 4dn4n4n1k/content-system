# Shot list stage — instructions for Claude

Input: approved `script.md`. Output: `projects/<slug>/shotlist.json`. The user
approves this before generation (this is the stage that costs money).

## Schema

```json
{
  "style_block": "Cinematic, moody tech-noir. Dark environment lit by monitor glow and neon cyan/green accents. Shallow depth of field, slow camera drift, photorealistic, 4k. No text, no captions, no watermarks, no readable UI.",
  "shots": [
    { "n": 1, "type": "ai", "prompt": "Slow push-in on a dark server room, rack LEDs pulsing...", "duration": 5 },
    { "n": 2, "type": "stock", "query": "data center corridor", "pick": 0 },
  { "n": 7, "type": "meme", "template": "Distracted Boyfriend",
    "top": "shiny new AI tool", "bottom": "the patch backlog" },
    { "n": 3, "type": "diagram", "template": "stat_card",
      "fields": { "kicker": "RANSOMWARE", "stat": "$4.9M", "label": "average cost of a breach", "source": "IBM 2025" } }
  ]
}
```

- `style_block` is prepended to every AI prompt — keep it constant per video so
  clips look like one film.
- Templates: `title_card` (kicker/title/subtitle), `stat_card` (kicker/stat/label/source),
  `diagram` (title/nodes: [{name, desc}]), `quote_card` (quote/attribution),
  `list_card` (title/items: []).

## Prompt-writing rules for AI shots

- One subject, one camera move, one lighting mood per clip. 5s clips can't do plots.
- Describe motion explicitly ("slow dolly left", "camera orbits") — motionless
  prompts produce dead clips.
- NEVER request on-screen text, logos, or UI — video models garble text; that's
  what diagram cards are for.
- No real people's faces or brand marks (deepfake/trademark risk).
- Vary shot scale like an editor: wide → medium → close-up across consecutive shots.
- Use `stock` for generic footage (offices, streets, hands typing) and `ai` for
  shots stock can't provide (abstract AI visuals, dramatized hacking, futuristic scenes).

## Meme rules (`type: meme`)

- **Relevance is the whole joke.** The meme must comment on exactly what the
  narration says at that moment — the situation, the irony, the frustration.
  If it merely relates to the topic, cut it. A meme that lands on the *beat*
  ("and somehow, it got worse" → cue meme) beats a topically-correct one.
- Frequency: 1–3 per 10-min video, never two in a row, never in the first 60s
  (the hook must stay tight) and never during serious segments (breach victims,
  losses). They fit best on transitions, ironic reveals, and "we've all been
  there" moments.
- `template` is fuzzy-matched against Imgflip's top-100 catalog (Drake Hotline
  Bling, Distracted Boyfriend, This Is Fine, Expanding Brain, Two Buttons,
  Change My Mind, Is This A Pigeon, Surprised Pikachu, ...). Pick templates
  whose *structure* matches the logic of the joke (comparison → Drake/Two
  Buttons; escalation → Expanding Brain; denial → This Is Fine).
- Caption text: `top` / `bottom`, max ~6 words each, phrased from the
  audience's point of view. Optionally `image_url` for a custom image.
- Keep meme slots short in the script — 3–5 seconds of narration (the beat +
  a breath). The meme pops in animated; it shouldn't outstay the laugh.

## Duration budgeting

Each [SHOT n] in the script spans ~8–15s of narration, but generated clips are
~5s: that's fine — the assembler loops clips to fill the slot. For slots longer
than ~12s, prefer a diagram card (they animate with a slow zoom and hold up) or
split into two shots in the script.
