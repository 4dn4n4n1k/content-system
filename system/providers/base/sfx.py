"""Contract for sound-effect providers."""
from abc import ABC, abstractmethod
from pathlib import Path

#: The assembler's mixing contract: every SFX file must be this format.
SAMPLE_RATE = 48000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


class SoundEffectProvider(ABC):
    """Guarantees that named SFX files exist locally.

    `names` are logical sound names ("whoosh", "impact", "pop"); the provider
    must produce `<name>.wav` files in dest_dir at 48 kHz / 16-bit / mono.
    Files already present must be left untouched (they may be user-supplied
    replacements — that workflow is part of the product).

    Raise errors from system.providers.errors only.
    """

    name: str = "abstract"

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials are missing."""

    @abstractmethod
    def ensure(self, names: tuple[str, ...], dest_dir: Path) -> None:
        """Make sure <name>.wav exists in dest_dir for every name."""
