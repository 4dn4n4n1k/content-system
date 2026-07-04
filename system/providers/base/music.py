"""Contract for music-bed providers (no implementation yet — future only).

When a provider lands (e.g. a royalty-free library API), the assembler will
request a bed matching the video's mood/length instead of using whatever file
sits in assets/music/. Manual drop-in stays supported regardless.
"""
from abc import ABC, abstractmethod
from pathlib import Path


class MusicProvider(ABC):
    name: str = "abstract"

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials are missing."""

    @abstractmethod
    def fetch(self, mood: str, duration: float, dest: Path) -> None:
        """Download a music bed of at least `duration` seconds to dest."""
