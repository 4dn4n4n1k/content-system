"""Contract for meme-template providers."""
from abc import ABC, abstractmethod


class MemeProvider(ABC):
    """Resolves a meme template name to a downloadable blank-template image.

    Captioning is NOT a provider concern — the graphics stage overlays
    animated captions locally, so the same template can be re-captioned
    without re-fetching.

    Raise errors from system.providers.errors only (PermanentFailure with a
    helpful sample list when nothing matches).
    """

    name: str = "abstract"

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials are missing."""

    @abstractmethod
    def resolve(self, template_name: str) -> tuple[str, str]:
        """Return (image_url, canonical_label) for a template name."""
