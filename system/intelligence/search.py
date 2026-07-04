"""Search engine: fan a shot's concepts out across searchable providers.

Only talks to StockProvider.search() (the contract capability) — never to a
provider's HTTP API directly. Multi-provider by construction: pass more
providers to the constructor and their candidates merge into one pool
(Pixabay/Storyblocks land here as new StockProvider implementations, zero
changes in this file).
"""
from .models import AssetCandidate


class SearchEngine:
    def __init__(self, providers: list, max_candidates: int = 20):
        # Providers that implement search(); others are silently skipped.
        self.providers = providers
        self.max_candidates = max_candidates

    def search(self, concepts: list[str]) -> list[AssetCandidate]:
        """Query each concept (best first) on every provider; dedupe by
        (provider, id); stop once the pool is full. Earlier concepts rank
        higher, which the scorer sees via the candidate's `concept_rank`."""
        pool: list[AssetCandidate] = []
        seen: set[tuple[str, str]] = set()
        per_concept = max(4, self.max_candidates // max(len(concepts), 1))

        for rank, concept in enumerate(concepts):
            if len(pool) >= self.max_candidates:
                break
            for provider in self.providers:
                try:
                    raw = provider.search(concept, limit=per_concept)
                except Exception as e:
                    print(f"    (search '{concept}' on {provider.name} failed: "
                          f"{str(e)[:80]})")
                    continue
                for item in raw:
                    key = (provider.name, str(item["id"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    meta = dict(item.get("metadata") or {})
                    meta["concept"] = concept
                    meta["concept_rank"] = rank
                    pool.append(AssetCandidate(
                        provider=provider.name,
                        id=str(item["id"]),
                        preview=item.get("preview", ""),
                        download_url=item["download_url"],
                        width=int(item.get("width") or 0),
                        height=int(item.get("height") or 0),
                        duration=float(item.get("duration") or 0),
                        text=item.get("text", ""),
                        popularity=item.get("popularity"),
                        metadata=meta,
                    ))
                    if len(pool) >= self.max_candidates:
                        break
        return pool
