"""edge-tts provider (Microsoft Edge neural voices) — free, no API key.

Config (config.yaml providers.voice.edge):
  voice: e.g. en-US-ChristopherNeural (list: python -m edge_tts --list-voices)
  rate:  e.g. "+4%"
  pitch: e.g. "+0Hz"

Honors the CLI --voice override.
"""
import asyncio
from pathlib import Path

from ..base.voice import VoiceProvider
from ..errors import TemporaryFailure


class EdgeVoiceProvider(VoiceProvider):
    name = "edge"
    output_suffix = ".mp3"

    def synthesize(self, text: str, dest: Path) -> None:
        import edge_tts

        voice = self.voice_override or self.cfg.get("voice", "en-US-ChristopherNeural")
        print(f"Synthesizing with edge-tts voice {voice}...")
        communicate = edge_tts.Communicate(
            text, voice, rate=self.cfg.get("rate", "+0%"), pitch=self.cfg.get("pitch", "+0Hz"))
        try:
            asyncio.run(communicate.save(str(dest)))
        except Exception as e:  # edge-tts raises assorted network errors
            raise TemporaryFailure(str(e)[:300], self.name) from e
