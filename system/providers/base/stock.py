"""Contract for stock-footage providers."""
from abc import ABC, abstractmethod
from pathlib import Path


class StockProvider(ABC):
    """Finds and downloads one stock clip for a search query.

    Raise errors from system.providers.errors only.
    """

    name: str = "abstract"

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials are missing."""

    @abstractmethod
    def fetch(self, query: str, dest: Path, pick: int = 0) -> dict | None:
        """Download the best match for `query` to dest (mp4).

        `pick` selects among the top results (shot list `pick` field).
        Returns metadata for the stage's log line (at least {"height": int}),
        or None when the query has no results (stage warns, run continues).
        """

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Optional capability: return candidate assets WITHOUT downloading,
        for the Asset Intelligence layer. Providers that can't search return
        [] (the default) and are simply skipped by the search engine.

        Each candidate is a plain normalized dict (providers stay decoupled
        from the intelligence package):
          id: str            provider-unique id
          preview: str       thumbnail URL ("" if none)
          download_url: str  direct file URL of the preferred rendition
          width, height: int
          duration: float    seconds (0 if unknown)
          text: str          searchable descriptor (slug/title/tags)
          popularity: float | None   provider-native popularity if available
          metadata: dict     anything extra (all renditions, author, ...)
        """
        return []
