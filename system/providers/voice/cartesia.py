"""Cartesia TTS provider (sonic models) — the channel's default voice.

Config (config.yaml providers.voice.cartesia):
  voice_id:  Cartesia voice UUID (the channel voice)
  model:     sonic model id (default sonic-3)
  language:  ISO code (default en)

Requests raw PCM per paragraph chunk and concatenates into one WAV with a
0.35 s breath between chunks, so server-side transcript limits never matter.
Note: the CLI --voice override is intentionally ignored here (voice_override
addresses named voices; Cartesia voices are config-pinned UUIDs).
"""
import os
import wave
from pathlib import Path

import requests

from ..base.voice import VoiceProvider, chunk_paragraphs
from ..errors import AuthenticationError, TemporaryFailure, classify_http

SR = 44100


class CartesiaVoiceProvider(VoiceProvider):
    name = "cartesia"
    output_suffix = ".wav"

    def check_ready(self) -> None:
        if not os.environ.get("CARTESIA_API_KEY"):
            raise AuthenticationError("CARTESIA_API_KEY is not set in .env", self.name)

    def synthesize(self, text: str, dest: Path) -> None:
        key = os.environ["CARTESIA_API_KEY"]
        voice_id = self.cfg["voice_id"]
        model = self.cfg.get("model", "sonic-3")
        chunks = chunk_paragraphs(text)
        print(f"Synthesizing with Cartesia {model}, voice {voice_id} ({len(chunks)} chunk(s))...")

        pcm = b""
        pause = b"\x00\x00" * int(SR * 0.35)  # paragraph breath between chunks
        for i, chunk in enumerate(chunks):
            try:
                r = requests.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers={"Authorization": f"Bearer {key}",
                             "Cartesia-Version": "2026-03-01",
                             "Content-Type": "application/json"},
                    json={"model_id": model,
                          "transcript": chunk,
                          "voice": {"mode": "id", "id": voice_id},
                          "language": self.cfg.get("language", "en"),
                          "output_format": {"container": "raw", "encoding": "pcm_s16le",
                                            "sample_rate": SR}},
                    timeout=600,
                )
            except requests.RequestException as e:
                raise TemporaryFailure(f"chunk {i + 1}: {e}", self.name) from e
            if r.status_code != 200:
                raise classify_http(r.status_code, f"chunk {i + 1}: {r.text}", self.name)
            pcm += r.content + pause

        with wave.open(str(dest), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm)
