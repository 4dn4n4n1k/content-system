"""Data model for Render Intelligence.

The RenderPlan is the contract between planning and rendering: the assembler
consumes render_plan.json and applies exactly what it says — no editorial
decisions live in the renderer anymore. Anything the renderer can't execute
yet (e.g. whip transitions) is carried as a recommendation/note, never lost.
"""
from dataclasses import dataclass, field

PLAN_VERSION = 1


@dataclass
class CameraPlan:
    """Per-shot camera treatment.

    mode "kenburns" (images): the renderer builds a zoompan from these params.
    mode "none" (video/cards): the source's own motion is left alone.
    """
    mode: str = "none"              # none | kenburns
    zoom_rate_per_frame: float = 0.0
    zoom_max: float = 1.0
    direction: str = "in"           # in | out
    pan: str = "center"             # center | left | right | up | down

    def to_dict(self) -> dict:
        return {"mode": self.mode, "zoom_rate_per_frame": self.zoom_rate_per_frame,
                "zoom_max": self.zoom_max, "direction": self.direction, "pan": self.pan}


@dataclass
class MotionPlan:
    """Per-shot motion accents (video shots only)."""
    zoom_punch_at_s: float | None = None   # relative to shot start
    zoom_punch_scale: float = 1.08
    reason: str = ""

    def to_dict(self) -> dict:
        if self.zoom_punch_at_s is None:
            return {}
        return {"zoom_punch_at_s": round(self.zoom_punch_at_s, 2),
                "zoom_punch_scale": self.zoom_punch_scale, "reason": self.reason}


@dataclass
class ShotRender:
    n: int
    type: str                       # ai | stock | diagram | meme
    kind: str                       # video | image (current asset form)
    start: float
    duration: float
    frames: int
    energy: float
    camera: CameraPlan
    motion: MotionPlan
    caption_emphasis: str = "normal"   # normal | high (metadata for renderers)

    def to_dict(self) -> dict:
        return {"n": self.n, "type": self.type, "kind": self.kind,
                "start": round(self.start, 3), "duration": round(self.duration, 3),
                "frames": self.frames, "energy": round(self.energy, 2),
                "camera": self.camera.to_dict(), "motion": self.motion.to_dict(),
                "caption_emphasis": self.caption_emphasis}


@dataclass
class CutPlan:
    at_s: float
    from_n: int
    to_n: int
    type: str = "cut"               # only "cut" is renderable today
    recommendation: str | None = None   # e.g. "whip transition (critic)"

    def to_dict(self) -> dict:
        d = {"at_s": round(self.at_s, 3), "from": self.from_n, "to": self.to_n,
             "type": self.type}
        if self.recommendation:
            d["recommendation"] = self.recommendation
        return d


@dataclass
class SfxEvent:
    t: float
    name: str                       # whoosh | impact | pop (files in sfx/)
    gain: float
    reason: str = ""

    def to_dict(self) -> dict:
        return {"t": round(max(self.t, 0.0), 3), "sfx": self.name,
                "gain": self.gain, "reason": self.reason}


@dataclass
class AudioPlan:
    music_volume: float
    music_fade_in_s: float
    music_fade_out_s: float
    sfx_volume: float
    loudnorm: bool
    duck: dict = field(default_factory=lambda: {"enabled": False})

    def to_dict(self) -> dict:
        return {"music_volume": self.music_volume,
                "music_fade_in_s": self.music_fade_in_s,
                "music_fade_out_s": self.music_fade_out_s,
                "sfx_volume": self.sfx_volume, "loudnorm": self.loudnorm,
                "duck": self.duck}


@dataclass
class RenderPlan:
    fps: int
    duration: float
    shots: list[ShotRender]
    cuts: list[CutPlan]
    events: list[SfxEvent]
    audio: AudioPlan
    captions_enabled: bool
    energy_curve: list[dict] = field(default_factory=list)
    pattern_interrupts: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        from datetime import datetime, timezone
        return {
            "version": PLAN_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fps": self.fps, "duration": round(self.duration, 3),
            "shots": [s.to_dict() for s in self.shots],
            "cuts": [c.to_dict() for c in self.cuts],
            "events": [e.to_dict() for e in self.events],
            "audio": self.audio.to_dict(),
            "captions": {"enabled": self.captions_enabled},
            "energy_curve": self.energy_curve,
            "pattern_interrupts": [round(t, 2) for t in self.pattern_interrupts],
            "notes": self.notes,
        }
