"""Shared HTTP helpers for providers."""
from pathlib import Path

import requests

from .errors import TemporaryFailure


def download(url: str, dest: Path, timeout: int = 300, provider: str = "download") -> None:
    """Stream a file to dest atomically (.part rename on success)."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException as e:
        tmp.unlink(missing_ok=True)
        raise TemporaryFailure(f"download failed: {e}", provider) from e
    tmp.replace(dest)
