"""Contract for text-to-video generation providers."""
from abc import ABC, abstractmethod
from pathlib import Path


class VideoGenerationProvider(ABC):
    """Generates a single b-roll clip from a text prompt.

    Implementations own everything provider-specific: SDK calls, parameter
    mapping, result-shape parsing, download. They must NOT know about shots,
    shot lists, style blocks, or file naming — the stage passes a finished
    prompt and a destination path.

    Raise errors from system.providers.errors only.
    """

    #: registry key; also used in error messages and cost hints
    name: str = "abstract"

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials/config are missing."""

    @property
    def description(self) -> str:
        """Human-readable model identity for the cost preview."""
        return self.name

    @property
    def default_duration(self) -> float:
        """Clip duration (seconds) used when a shot doesn't specify one."""
        return 5.0

    def estimate_cost(self, seconds: float) -> float | None:
        """Estimated USD for `seconds` of video; None if unknown."""
        cps = self.cfg.get("cost_per_second")
        return seconds * cps if cps is not None else None

    @abstractmethod
    def generate(self, prompt: str, dest: Path, duration: float | None = None) -> None:
        """Generate one clip and write it to dest (mp4)."""
