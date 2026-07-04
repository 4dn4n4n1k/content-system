"""Editorial rules: defaults + config overrides (config.yaml `critic:`).

Every threshold the analyzers use lives here so tuning is a config edit,
never a code edit. `load_rules(cfg)` deep-merges the operator's overrides
onto the defaults.
"""
import re

DEFAULTS: dict = {
    "wpm": 140,                    # speech rate used when timing.json is absent
    "hook": {
        "window_s": 30,            # the make-or-break opening window
        "max_shot_s": 6,           # no shot in the hook may sit longer than this
        "min_shots": 3,            # visual intensity: at least this many shots
        "no_meme_before_s": 60,    # memes too early undercut the hook
    },
    "pacing": {
        "max_shot_s": 12,          # any shot past this is a dead zone
        "slow_shot_s": 9,          # "slow" threshold for run detection
        "max_consecutive_slow": 2,
        "max_wpm": 175,            # narration density ceiling (info overload)
        "min_wpm": 95,             # narration density floor (dragging)
    },
    "diversity": {
        "max_same_type_run": 3,    # e.g. 4 ai shots back-to-back
        "max_template_repeats": 2, # same diagram template used > N times
        "max_memes": 3,
        "similar_prompt_jaccard": 0.6,
    },
    "retention": {
        "interrupt_interval_s": 60,  # max gap without a pattern interrupt
        "static_sequence_s": 20,     # one shot this long = long static sequence
        "payoff_window_s": 25,       # a promised reveal should pay off within this
    },
    "transitions": {
        "long_shot_s": 10,           # recommend a zoom punch inside shots this long
        "chapter_gap_s": 150,        # recommend chapter separators past this gap
    },
}

# Language signals (deterministic — no models).
# Matches digit claims ("4.9 billion", "$3M", "38%") AND word-form quantities
# ("four billion", "millions of") — scripts are written TTS-proof with numbers
# as words, so digit-only matching would miss most spoken claims.
CLAIM_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|percent|billion|million|thousand|dollars)"
    r"|\$\s?\d"
    r"|\b(?:billions?|millions?|trillions?|thousands?)\b|\bpercent\b"
    r"|worst|biggest|largest|fastest|first ever|only way|never|secret"
    r"|shocking|no one|every single|record", re.IGNORECASE)
CALLBACK_PATTERN = re.compile(
    r"later in this video|we'?ll (?:get|come back) to|more on that|stick around"
    r"|coming up|at the end of this video", re.IGNORECASE)
PAYOFF_PATTERN = re.compile(
    r"here'?s (?:the|what|how|why)|it turns out|the answer is|this is (?:the|why|how)"
    r"|let me show you", re.IGNORECASE)
SERIOUS_PATTERN = re.compile(
    r"victims?|died|death|suicide|funeral|tragedy|devastat|bankrupt|life savings"
    r"|hospital patients", re.IGNORECASE)


def load_rules(cfg: dict | None) -> dict:
    rules = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for key, value in ((cfg or {}).get("critic") or {}).items():
        if isinstance(value, dict) and isinstance(rules.get(key), dict):
            rules[key].update(value)
        else:
            rules[key] = value
    return rules
