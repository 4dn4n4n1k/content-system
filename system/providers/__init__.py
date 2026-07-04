"""Provider registry and factory.

Stages never import a concrete provider; they ask the factory, which reads
config.yaml:

    providers:
      video: { active: fal,      fal: {...} }
      voice: { active: cartesia, cartesia: {...}, edge: {...} }
      stock: { active: pexels }
      meme:  { active: imgflip }
      sfx:   { active: synthesized }
      music: { active: none }

Adding a provider = write one module implementing the base contract and add
one _REGISTRY line; no stage code changes. Providers are imported lazily so
an SDK only loads when its provider is active (e.g. fal_client is never
imported while rendering graphics).
"""
from importlib import import_module

from ..util import load_config
from .errors import (AuthenticationError, PermanentFailure, ProviderError,  # noqa: F401
                     RateLimitError, TemporaryFailure)

#: kind -> active-name -> (module under system.providers, class name)
_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    "video": {
        "fal": ("video.fal", "FalVideoProvider"),
        # future: "runway": ("video.runway", "RunwayVideoProvider"),
        #         "luma":   ("video.luma", "LumaVideoProvider"), ...
    },
    "voice": {
        "cartesia": ("voice.cartesia", "CartesiaVoiceProvider"),
        "edge": ("voice.edge", "EdgeVoiceProvider"),
        "elevenlabs": ("voice.elevenlabs", "ElevenLabsVoiceProvider"),
    },
    "stock": {
        "pexels": ("stock.pexels", "PexelsStockProvider"),
    },
    "meme": {
        "imgflip": ("meme.imgflip", "ImgflipMemeProvider"),
    },
    "sfx": {
        "synthesized": ("sfx.synthesized", "SynthesizedSfxProvider"),
    },
    "music": {},  # future only (see base/music.py)
}

_DEFAULTS = {"video": "fal", "voice": "cartesia", "stock": "pexels",
             "meme": "imgflip", "sfx": "synthesized", "music": "none"}


class ProviderFactory:
    @staticmethod
    def _get(kind: str, cfg: dict | None = None, **kwargs):
        cfg = cfg or load_config()
        section = (cfg.get("providers") or {}).get(kind) or {}
        active = section.get("active", _DEFAULTS[kind])
        registry = _REGISTRY[kind]
        if active not in registry:
            options = ", ".join(sorted(registry)) or "none implemented yet"
            raise ProviderError(
                f"unknown {kind} provider '{active}' in config.yaml "
                f"(providers.{kind}.active). Available: {options}")
        module_path, class_name = registry[active]
        cls = getattr(import_module(f".{module_path}", __package__), class_name)
        return cls(section.get(active) or {}, **kwargs)

    @classmethod
    def get_video_provider(cls, cfg: dict | None = None):
        return cls._get("video", cfg)

    @classmethod
    def get_voice_provider(cls, cfg: dict | None = None, voice_override: str | None = None):
        return cls._get("voice", cfg, voice_override=voice_override)

    @classmethod
    def get_stock_provider(cls, cfg: dict | None = None):
        return cls._get("stock", cfg)

    @classmethod
    def get_meme_provider(cls, cfg: dict | None = None):
        return cls._get("meme", cfg)

    @classmethod
    def get_sfx_provider(cls, cfg: dict | None = None):
        return cls._get("sfx", cfg)

    @classmethod
    def get_music_provider(cls, cfg: dict | None = None):
        return cls._get("music", cfg)
