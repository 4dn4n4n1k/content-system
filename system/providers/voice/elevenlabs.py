"""ElevenLabs TTS provider (optional premium voice).

Config (config.yaml providers.voice.elevenlabs):
  voice_id: ElevenLabs voice id (default: Daniel)
  model:    model id (default eleven_multilingual_v2)

Note: --voice override is ignored (voices are ids, not names).
"""
import os
from pathlib import Path

import requests

from ..base.voice import VoiceProvider
from ..errors import AuthenticationError, TemporaryFailure, classify_http


class ElevenLabsVoiceProvider(VoiceProvider):
    name = "elevenlabs"
    output_suffix = ".mp3"

    def check_ready(self) -> None:
        if not os.environ.get("ELEVENLABS_API_KEY"):
            raise AuthenticationError("ELEVENLABS_API_KEY is not set in .env", self.name)

    def synthesize(self, text: str, dest: Path) -> None:
        voice_id = self.cfg.get("voice_id", "onwK4e9ZLuTAKqWW03F9")  # Daniel
        print(f"Synthesizing with ElevenLabs voice {voice_id}...")
        try:
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                json={"text": text,
                      "model_id": self.cfg.get("model", "eleven_multilingual_v2")},
                timeout=600,
            )
        except requests.RequestException as e:
            raise TemporaryFailure(str(e), self.name) from e
        if r.status_code != 200:
            raise classify_http(r.status_code, r.text, self.name)
        dest.write_bytes(r.content)
