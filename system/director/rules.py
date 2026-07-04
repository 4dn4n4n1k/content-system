"""Creative rules: defaults + config overrides (config.yaml `director:`) and
the deterministic language signals the analyzers share.

Claim/callback/payoff/serious patterns are reused from the Timeline Critic so
the two review stages agree on what counts as a claim or a promise.
"""
import re

# Shared language signals — one definition across both review stages.
from ..critic.rules import (CALLBACK_PATTERN, CLAIM_PATTERN,  # noqa: F401
                            PAYOFF_PATTERN, SERIOUS_PATTERN)

DEFAULTS: dict = {
    "wpm": 140,
    "hook": {
        "window_s": 30,
        "need_question_by_s": 45,      # curiosity signal expected this early
        "urgency_window_s": 60,
    },
    "narrative": {
        "max_section_share": 0.40,     # one section dominating the runtime
        "ngram": 4,                    # phrase length for repetition detection
        "claim_cluster_window_s": 60,  # >N claims inside this = stat dump
        "claim_cluster_max": 3,
        "dry_stretch_s": 90,           # this long with zero facts/claims
        "payoff_backload_share": 0.8,  # all payoffs after this point = backloaded
    },
    "clarity": {
        "long_sentence_words": 30,
        "max_long_sentence_share": 0.15,
        "abstract_density": 0.18,      # abstract nouns / words in a sentence
        "max_numbers_per_sentence": 2,
    },
    "emotion": {
        "flat_density": 0.004,         # emotional words per word, below = flat
        "min_overall_tension": 0.008,  # a cyber/AI video needs stakes
        "abrupt_delta": 0.035,         # tension jump between adjacent sections
    },
    "curiosity": {
        "early_share": 0.15,           # "premature reveal" = payoff before this
        "resolve_search_share": 0.5,   # loops must resolve in the later half
    },
    "visuals": {
        "dry_section_min_words": 60,   # sections shorter than this aren't judged
        "min_confidence": 0.5,         # opportunities below this are dropped
    },
}

URGENCY_PATTERN = re.compile(
    r"right now|today|already happening|as we speak|before it'?s too late"
    r"|this year|every day|at this moment|won'?t wait", re.IGNORECASE)
QUESTION_HOOK_PATTERN = re.compile(
    r"\?|what if|have you ever|why (?:do|does|did|is|are)|how (?:do|does|did|can)",
    re.IGNORECASE)
EXPLAINER_PATTERN = re.compile(
    r"\bwhich (?:is|means)|meaning|basically|in other words|that is,|—\s*think of"
    r"|in simple terms|aka\b|:\s", re.IGNORECASE)
COMPARISON_PATTERN = re.compile(
    r"\bversus\b|\bvs\.?\b|compared (?:to|with)|whereas|on one hand|meanwhile"
    r"|the difference between", re.IGNORECASE)
SEQUENCE_PATTERN = re.compile(
    r"\bfirst\b.*\bthen\b|\bstep (?:one|two|three|\d)|stage \d|three (?:ways|steps|things)"
    r"|finally\b", re.IGNORECASE | re.DOTALL)
QUOTE_PATTERN = re.compile(r'"[^"]{15,}"|according to|\bsaid\b|\bwarned\b|\bput it\b',
                           re.IGNORECASE)
PROCESS_PATTERN = re.compile(
    r"here'?s how|how it works|works like|under the hood|behind the scenes"
    r"|the process", re.IGNORECASE)
IRONY_PATTERN = re.compile(
    r"ironically|of course,|somehow|you guessed it|naturally,|surprise[,:]"
    r"|plot twist", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER_PATTERN = re.compile(r"\d[\d,.]*\s*(?:%|percent|billion|million|thousand|dollars)?")

TENSION_WORDS = {
    "attack", "attacks", "breach", "breached", "stolen", "steal", "threat",
    "danger", "dangerous", "warning", "risk", "fear", "exploit", "exploited",
    "victim", "victims", "malware", "ransomware", "compromised", "infected",
    "destroyed", "lost", "crisis", "weapon", "war", "collapse", "leaked",
}
RELIEF_WORDS = {
    "safe", "safely", "protect", "protected", "protection", "solution", "fix",
    "fixed", "secure", "secured", "defend", "defense", "hope", "recover",
    "recovered", "win", "stopped", "blocked", "prevented", "good news",
}
JARGON_TERMS = {
    "apt", "zero-day", "0day", "botnet", "cve", "endpoint", "edr", "xdr",
    "siem", "soc", "c2", "payload", "phishing", "spear-phishing", "llm",
    "inference", "fine-tuning", "rag", "api", "sdk", "vpn", "dns", "mfa",
    "oauth", "encryption", "cryptography", "kernel", "firmware", "sandbox",
    "hypervisor", "container", "kubernetes", "backdoor", "rootkit", "keylogger",
}
ABSTRACT_SUFFIXES = ("tion", "sion", "ity", "ness", "ment", "ance", "ence", "ism")


def load_rules(cfg: dict | None) -> dict:
    rules = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for key, value in ((cfg or {}).get("director") or {}).items():
        if isinstance(value, dict) and isinstance(rules.get(key), dict):
            rules[key].update(value)
        else:
            rules[key] = value
    return rules
