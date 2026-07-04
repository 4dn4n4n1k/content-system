"""Contract for text-to-speech providers."""
import re
from abc import ABC, abstractmethod
from pathlib import Path


class VoiceProvider(ABC):
    """Synthesizes the full narration to one audio file.

    The stage decides the destination path (using `output_suffix`) and does
    all script parsing; providers receive plain narration text with blank
    lines separating paragraphs (usable as pause hints).

    `voice_override` is the CLI `--voice` flag; providers that address voices
    by name may honor it, others ignore it.

    Raise errors from system.providers.errors only.
    """

    name: str = "abstract"
    #: file extension the provider produces (drives voiceover.<ext> naming)
    output_suffix: str = ".mp3"

    def __init__(self, cfg: dict | None, voice_override: str | None = None):
        self.cfg = cfg or {}
        self.voice_override = voice_override

    def check_ready(self) -> None:
        """Raise AuthenticationError if credentials/config are missing."""

    @abstractmethod
    def synthesize(self, text: str, dest: Path) -> None:
        """Write the narration audio to dest."""


def chunk_paragraphs(text: str, max_chars: int = 2000) -> list[str]:
    """Split narration into TTS-friendly chunks on paragraph, then sentence
    boundaries, keeping each under max_chars. Shared by request-size-limited
    providers."""
    chunks = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", para):
            if current and len(current) + len(sentence) + 1 > max_chars:
                chunks.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
    return chunks
