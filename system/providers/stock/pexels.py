"""Pexels stock-video provider (free API).

Config (config.yaml providers.stock.pexels): none currently.
"""
import os
from pathlib import Path

import requests

from ..base.stock import StockProvider
from ..errors import AuthenticationError, TemporaryFailure, classify_http
from ..net import download


class PexelsStockProvider(StockProvider):
    name = "pexels"

    def check_ready(self) -> None:
        if not os.environ.get("PEXELS_API_KEY"):
            raise AuthenticationError(
                "Shot list contains stock shots but PEXELS_API_KEY is not set in .env",
                self.name)

    def _search_api(self, query: str, per_page: int) -> list[dict]:
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": os.environ["PEXELS_API_KEY"]},
                params={"query": query, "orientation": "landscape",
                        "size": "medium", "per_page": per_page},
                timeout=60,
            )
        except requests.RequestException as e:
            raise TemporaryFailure(str(e), self.name) from e
        if r.status_code != 200:
            raise classify_http(r.status_code, r.text, self.name)
        return r.json().get("videos", [])

    @staticmethod
    def _best_file(video: dict) -> dict:
        # Prefer an HD file close to 1080p, avoid 4K downloads.
        return sorted(video["video_files"],
                      key=lambda f: abs((f.get("height") or 0) - 1080))[0]

    def fetch(self, query: str, dest: Path, pick: int = 0) -> dict | None:
        videos = self._search_api(query, per_page=5)
        if not videos:
            return None
        best = self._best_file(videos[pick % len(videos)])
        download(best["link"], dest, provider=self.name)
        return {"height": best.get("height")}

    def search(self, query: str, limit: int = 20) -> list[dict]:
        candidates = []
        for video in self._search_api(query, per_page=min(limit, 80)):
            best = self._best_file(video)
            # The URL slug is the only textual descriptor Pexels exposes,
            # e.g. https://www.pexels.com/video/server-room-with-racks-123/
            slug = video.get("url", "").rstrip("/").split("/")[-1]
            text = " ".join(w for w in slug.split("-") if not w.isdigit())
            candidates.append({
                "id": str(video["id"]),
                "preview": video.get("image", ""),
                "download_url": best["link"],
                "width": best.get("width") or video.get("width", 0),
                "height": best.get("height") or video.get("height", 0),
                "duration": float(video.get("duration") or 0),
                "text": text,
                "popularity": None,  # Pexels video search exposes no metric
                "metadata": {"author": (video.get("user") or {}).get("name", ""),
                             "page": video.get("url", "")},
            })
        return candidates
