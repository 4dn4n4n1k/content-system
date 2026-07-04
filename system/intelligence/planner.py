"""Planner: turn a shot's search query into ranked search concepts.

Deterministic NLP only — token categorization against a domain lexicon
(AI / IT / cybersecurity) plus synonym expansion. No LLM calls.

Pluggable: anything with `plan(shot) -> ShotBrief` is a planner. A future
LLMPlanner implements the same method and get_planner() picks it from
config (asset_intelligence.planner.engine) — nothing downstream changes.
"""
import re

from .models import ShotBrief

STOPWORDS = {"a", "an", "the", "of", "in", "on", "with", "and", "or", "at", "to", "for"}

# Domain synonym map: token/phrase -> alternative search strings, best first.
SYNONYMS: dict[str, list[str]] = {
    "ai": ["artificial intelligence", "neural network", "machine learning"],
    "artificial intelligence": ["neural network", "machine learning"],
    "datacenter": ["server room", "data center", "server racks"],
    "data center": ["server room", "server racks", "gpu cluster"],
    "server": ["server room", "server racks"],
    "gpu": ["gpu cluster", "graphics card", "circuit board"],
    "chip": ["microchip", "circuit board", "semiconductor"],
    "network": ["network cables", "fiber optics", "glowing connections"],
    "cloud": ["cloud computing", "data center"],
    "hacker": ["hooded hacker", "hacking", "computer code screen"],
    "hacking": ["hooded hacker", "computer code screen"],
    "cybersecurity": ["network security", "digital padlock", "encryption"],
    "security": ["digital padlock", "network security"],
    "malware": ["computer virus", "warning screen", "glitch screen"],
    "ransomware": ["locked screen", "warning screen", "digital padlock"],
    "phishing": ["suspicious email", "laptop email", "typing laptop"],
    "code": ["programming code", "source code screen", "developer typing"],
    "coding": ["programming code", "developer typing"],
    "robot": ["robotic arm", "humanoid robot", "automation"],
    "money": ["cash", "finance", "stock market screen"],
    "crypto": ["cryptocurrency", "bitcoin", "trading screen"],
    "city": ["city aerial night", "skyline night"],
    "office": ["modern office", "people working computers"],
    "phone": ["smartphone", "person using phone"],
    "typing": ["hands typing keyboard", "developer typing"],
}

# Style vocabulary — these words describe HOW to shoot, not WHAT.
CATEGORIES: dict[str, set[str]] = {
    "camera": {"aerial", "drone", "closeup", "close-up", "macro", "timelapse",
               "pan", "tracking", "handheld", "pov", "wide"},
    "lighting": {"blue", "neon", "dark", "moody", "bright", "glowing", "red",
                 "green", "backlit", "silhouette"},
    "emotion": {"tense", "calm", "dramatic", "futuristic", "ominous", "hopeful",
                "chaotic", "sleek"},
    "motion": {"slow", "fast", "spinning", "flowing", "moving", "rotating",
               "flickering"},
    "environment": {"room", "street", "lab", "warehouse", "basement", "rooftop",
                    "underground", "indoor", "outdoor", "night", "rain"},
}

GENERIC_FALLBACKS = ["technology", "digital abstract background"]

MAX_CONCEPTS = 8


class HeuristicPlanner:
    """Deterministic lexicon-based planner."""

    def __init__(self, cfg: dict | None):
        cfg = cfg or {}
        self.synonyms = cfg.get("synonyms", True)
        self.keyword_expansion = cfg.get("keyword_expansion", True)

    def plan(self, shot: dict) -> ShotBrief:
        query = shot.get("query", "").strip()
        words = [w for w in re.findall(r"[a-z0-9-]+", query.lower()) if w not in STOPWORDS]

        categories: dict[str, list[str]] = {k: [] for k in
                                            ("subject", *CATEGORIES.keys(), "object")}
        for w in words:
            placed = False
            for cat, vocab in CATEGORIES.items():
                if w in vocab:
                    categories[cat].append(w)
                    placed = True
                    break
            if not placed:
                # Content word: lexicon entries are subjects, the rest objects.
                categories["subject" if w in SYNONYMS else "object"].append(w)

        concepts: list[str] = [query] if query else []

        if self.synonyms:
            # Phrase-level synonyms first (e.g. "data center"), then per-token.
            lowered = query.lower()
            for phrase, alts in SYNONYMS.items():
                if " " in phrase and phrase in lowered:
                    concepts.extend(alts)
            for w in categories["subject"]:
                concepts.extend(SYNONYMS[w])

        if self.keyword_expansion:
            # Recombine subject matter with style words the query mentioned —
            # stock libraries index those as plain keywords too.
            style = categories["lighting"] + categories["camera"]
            core = categories["subject"] + categories["object"]
            if core and style:
                concepts.append(f"{' '.join(core[:2])} {' '.join(style[:1])}")
            if core:
                concepts.append(" ".join(core[:3]))
            concepts.extend(f"{s} technology" for s in categories["subject"][:1])

        if len(concepts) < 4:
            concepts.extend(GENERIC_FALLBACKS)

        seen, ordered = set(), []
        for c in concepts:
            c = c.strip()
            if c and c.lower() not in seen:
                seen.add(c.lower())
                ordered.append(c)

        return ShotBrief(query=query, tokens=words, categories=categories,
                         concepts=ordered[:MAX_CONCEPTS])


def get_planner(cfg: dict | None):
    """Planner factory. `engine: heuristic` is the only engine today; an
    `llm` engine plugs in here without touching callers."""
    cfg = cfg or {}
    engine = cfg.get("engine", "heuristic")
    if engine == "heuristic":
        return HeuristicPlanner(cfg)
    raise ValueError(f"unknown planner engine '{engine}' (available: heuristic)")
