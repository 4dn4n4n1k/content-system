"""fal.ai text-to-video provider.

Config (config.yaml providers.video.fal):
  model:           fal model id, e.g. fal-ai/bytedance/seedance/v1/lite/text-to-video
  params:          model-specific arguments merged into every request
  cost_per_second: USD/s used for the pre-generation cost preview
"""
import os
from pathlib import Path

from ..base.video import VideoGenerationProvider
from ..errors import AuthenticationError, PermanentFailure, TemporaryFailure
from ..net import download


class FalVideoProvider(VideoGenerationProvider):
    name = "fal"

    def check_ready(self) -> None:
        if not os.environ.get("FAL_KEY"):
            raise AuthenticationError(
                "FAL_KEY is not set. Copy .env.example to .env and add your fal.ai key.",
                self.name)
        if not self.cfg.get("model"):
            raise PermanentFailure(
                "no model configured (providers.video.fal.model in config.yaml)", self.name)

    @property
    def description(self) -> str:
        return self.cfg.get("model", self.name)

    @property
    def default_duration(self) -> float:
        return float((self.cfg.get("params") or {}).get("duration", 5))

    def generate(self, prompt: str, dest: Path, duration: float | None = None) -> None:
        import fal_client

        args = dict(self.cfg.get("params") or {})
        args["prompt"] = prompt
        if duration is not None:
            args["duration"] = str(duration)
        try:
            result = fal_client.subscribe(self.cfg["model"], arguments=args)
        except Exception as e:  # fal-client raises assorted SDK/HTTP errors
            raise TemporaryFailure(str(e)[:300], self.name) from e
        url = self._video_url(result)
        download(url, dest, provider=self.name)

    def _video_url(self, result) -> str:
        # Tolerate the response shapes used across fal model families.
        video = result.get("video") if isinstance(result, dict) else None
        if isinstance(video, dict) and video.get("url"):
            return video["url"]
        if isinstance(video, str):
            return video
        videos = result.get("videos") if isinstance(result, dict) else None
        if isinstance(videos, list) and videos and videos[0].get("url"):
            return videos[0]["url"]
        raise PermanentFailure(f"unrecognized result shape: {str(result)[:200]}", self.name)
