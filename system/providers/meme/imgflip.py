"""Imgflip meme-template provider.

Blank templates from the public catalog (https://api.imgflip.com/get_memes,
no API key, top ~100 templates). Name matching: exact, then substring, then
difflib fuzzy — so shot lists can say "This Is Fine" or "distracted boyfriend"
loosely.
"""
import difflib

import requests

from ..base.meme import MemeProvider
from ..errors import PermanentFailure, TemporaryFailure


class ImgflipMemeProvider(MemeProvider):
    name = "imgflip"

    def __init__(self, cfg: dict | None):
        super().__init__(cfg)
        self._catalog: list[dict] | None = None

    def _templates(self) -> list[dict]:
        if self._catalog is None:
            try:
                r = requests.get("https://api.imgflip.com/get_memes", timeout=30)
                r.raise_for_status()
            except requests.RequestException as e:
                raise TemporaryFailure(f"catalog fetch failed: {e}", self.name) from e
            self._catalog = r.json()["data"]["memes"]
        return self._catalog

    def resolve(self, template_name: str) -> tuple[str, str]:
        templates = self._templates()
        lowered = {t["name"].lower(): t for t in templates}
        query = template_name.lower().strip()
        template = lowered.get(query)
        if template is None:
            substr = [t for t in templates if query in t["name"].lower()]
            template = substr[0] if substr else None
        if template is None:
            close = difflib.get_close_matches(query, list(lowered), n=1, cutoff=0.4)
            template = lowered[close[0]] if close else None
        if template is None:
            sample = ", ".join(t["name"] for t in templates[:15])
            raise PermanentFailure(
                f"No Imgflip template matches '{template_name}'. "
                f"Popular options: {sample}, ...", self.name)
        return template["url"], template["name"]
