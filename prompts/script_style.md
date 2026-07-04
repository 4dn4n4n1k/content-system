# Script stage — style profile + instructions for Claude

Input: `research.md`. Output: `projects/<slug>/script.md`. The user reviews and
edits it before anything downstream runs — flag any claim you're unsure about.

## Channel voice (edit this section to tune your style)

- Topics: AI, IT, cybersecurity. Audience: tech-curious, not necessarily experts.
- Tone: sharp, direct, slightly ominous when the topic warrants it. No fluff,
  no "hey guys welcome back". Explain jargon in one clause, don't dumble it down.
- Pacing: short sentences. One idea per sentence. Rhetorical questions sparingly.
- Hook (first 20s): state the stakes or the surprising fact immediately, then
  promise the payoff ("by the end of this video you'll know exactly how...").
- Use concrete numbers and named incidents over vague claims.
- End with one actionable takeaway + a soft CTA (subscribe framed around value).

## Format rules

- Target length: ~140 spoken words per minute. A 10-min video ≈ 1,400 words.
- Markdown: `##` section headings (not read aloud), narration as plain paragraphs.
- Insert `[SHOT n]` markers where the visual should change — every 8–15 seconds
  of narration (every ~20–35 words). Number sequentially from 1.
- Mark shots that should be diagrams/stats where a visual explanation beats
  footage (aim for 1 diagram/stat card per 60–90s of video).
- The script is read verbatim by TTS (edge-tts by default), so write TTS-proof
  text: numbers as words where ambiguous ("4.9 million dollars", not "$4.9M"),
  expand acronyms on first use if mispronunciation is likely (write "A.I." /
  "A.P.T." with periods to force letter-by-letter), no parentheses asides, no
  emoji or symbols. Punctuation drives pacing — use commas and full stops
  deliberately; an em dash or ellipsis creates a beat before a reveal.
