# Timeline Critic Report

**Overall score: 81/100** · retention risk: 68/100 · runtime 0:24 (4 shots, timing timing.json)

| Category | Score |
|---|---|
| hook | 31/100 |
| pacing | 80/100 |
| diversity | 100/100 |
| narrative | 94/100 |
| retention | 100/100 |

## Critical issues (3)

- **[hook]** `0:00` shot 1 holds 9s inside the hook (max 6s) — early drop-off risk
- **[hook]** `0:13` shot 3 holds 8s inside the hook (max 6s) — early drop-off risk
- **[hook]** `0:21` shot 4 is a meme at 21s — memes before 60s undercut the hook

## Warnings (2)

- **[pacing]** `0:08` shot 2 narrates at ~189 wpm — information overload, give the viewer a beat
- **[pacing]** `0:21` shot 4 narrates at ~195 wpm — information overload, give the viewer a beat

## Suggestions (4)

- **[narrative]** `0:00` shot 1: visual ('placeholder clip one…') shares no keywords with its narration — intentional contrast or a mismatch?
- **[narrative]** `0:08` shot 2: visual ('placeholder clip two…') shares no keywords with its narration — intentional contrast or a mismatch?
- **[transitions]** `0:13` shot 3 is a card after b-roll — a half-beat pause before the cut makes the reveal land harder
- **[transitions]** `0:13` a title card at shot 3 would open 'The numbers' cleanly

## Strengths (3)

- **[hook]** 4 cuts inside the first 30s — lively open
- **[diversity]** 3 distinct shot types across 4 shots — good mix
- **[hook]** `shot 3` strongest claim sits at 13s (shot 3) — hook leads with stakes

## Timeline

| # | Type | Start | Dur | Words | wpm | Section |
|---|------|-------|-----|-------|-----|---------|
| 1 | ai | 0:00 | 9s | 22 | 153 | Intro |
| 2 | ai | 0:08 | 4s | 14 | 189 | Intro |
| 3 | stat_card | 0:13 | 8s | 20 | 152 | The numbers |
| 4 | This Is Fine | 0:21 | 3s | 11 | 195 | The numbers |

> Durations are measured from the aligned voiceover.
> The critic only reports; revise script.md / shotlist.json and rerun `python pipeline.py critic` until the numbers look right.