from __future__ import annotations

from dataclasses import dataclass
import json
import re
import threading
from typing import Callable, Mapping, Protocol, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Evidence

_TAG_RE = re.compile(r"<[^>]+>")


class ScholarlySearchClient(Protocol):
    def search(self, query: str, *, limit: int = 5) -> Sequence[Evidence]:
        ...


@dataclass(frozen=True, slots=True)
class CrossrefSearchConfig:
    mailto: str | None = None
    user_agent: str = "Tiny-Agent-OpenScholar/0.1 (+https://github.com/wds1996/Tiny-Agent)"
    timeout_seconds: float = 10.0
    max_concurrency: int | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_concurrency is not None and self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive when provided")


class CrossrefScholarlySearch:
    """Crossref REST discovery client.

    Returned values are explicitly ``scholarly_metadata``. Metadata can establish
    bibliographic facts and point us to candidate papers; it is not treated as
    proof of the paper's substantive findings.
    """

    endpoint = "https://api.crossref.org/v1/works"

    def __init__(
        self,
        config: CrossrefSearchConfig | None = None,
        *,
        opener: Callable[..., object] | None = None,
    ) -> None:
        self.config = config or CrossrefSearchConfig()
        self._opener = opener or urlopen
        # Crossref currently permits more concurrent polite-pool requests than
        # anonymous public-pool requests. This is only a concurrency guard, not
        # a complete rate limiter/cache/retry system.
        concurrency = self.config.max_concurrency or (3 if self.config.mailto else 1)
        self._gate = threading.BoundedSemaphore(concurrency)

    def search(self, query: str, *, limit: int = 5) -> list[Evidence]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        if limit <= 0 or limit > 20:
            raise ValueError("limit must satisfy 1 <= limit <= 20")
        with self._gate:
            return self._search_once(query, limit=limit)

    def _search_once(self, query: str, *, limit: int) -> list[Evidence]:
        params = {"query.bibliographic": query, "rows": str(limit)}
        if self.config.mailto:
            params["mailto"] = self.config.mailto
        request = Request(
            f"{self.endpoint}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": self.config.user_agent},
        )
        response = self._opener(request, timeout=self.config.timeout_seconds)
        try:
            raw = response.read()
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

        payload = json.loads(raw.decode("utf-8"))
        items = payload.get("message", {}).get("items", [])
        results: list[Evidence] = []
        for index, item in enumerate(items[:limit], start=1):
            titles = item.get("title") or []
            title = str(titles[0]) if titles else "Untitled work"
            doi = item.get("DOI")
            url = item.get("URL")
            authors = _authors(item.get("author") or [])
            year = _published_year(item)
            venues = item.get("container-title") or []
            venue = str(venues[0]) if venues else None
            results.append(
                Evidence(
                    id=f"X{index}",
                    kind="scholarly_metadata",
                    title=title,
                    text=_metadata_text(
                        title=title,
                        authors=authors,
                        year=year,
                        venue=venue,
                        doi=str(doi) if doi else None,
                    ),
                    source_url=str(url) if url else None,
                    locator=f"doi:{doi}" if doi else None,
                    score=max(0.0, 1.0 - (index - 1) * 0.05),
                    metadata={"doi": doi, "authors": authors, "year": year, "venue": venue},
                )
            )
        return results


class StaticScholarlySearch:
    """Deterministic search client for offline examples/tests."""

    def __init__(self, evidence_by_query: Mapping[str, Sequence[Evidence]]) -> None:
        self._evidence = {key: tuple(values) for key, values in evidence_by_query.items()}

    def search(self, query: str, *, limit: int = 5) -> list[Evidence]:
        exact = list(self._evidence.get(query, ()))
        if exact:
            return exact[:limit]
        lowered = query.lower()
        candidates: list[Evidence] = []
        for key, values in self._evidence.items():
            if key.lower() in lowered or lowered in key.lower():
                candidates.extend(values)
        return candidates[:limit]


def _authors(raw_authors: Sequence[Mapping[str, object]]) -> list[str]:
    names: list[str] = []
    for author in raw_authors:
        given = str(author.get("given") or "").strip()
        family = str(author.get("family") or "").strip()
        value = " ".join(part for part in (given, family) if part)
        if value:
            names.append(value)
    return names


def _published_year(item: Mapping[str, object]) -> int | None:
    for key in ("published-print", "published-online", "published", "created"):
        raw = item.get(key)
        if not isinstance(raw, Mapping):
            continue
        date_parts = raw.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def _metadata_text(
    *, title: str, authors: Sequence[str], year: int | None, venue: str | None, doi: str | None
) -> str:
    parts = [f"Title: {title}"]
    if authors:
        parts.append("Authors: " + ", ".join(authors[:8]))
    if year is not None:
        parts.append(f"Year: {year}")
    if venue:
        parts.append(f"Venue: {_TAG_RE.sub('', venue)}")
    if doi:
        parts.append(f"DOI: {doi}")
    return "\n".join(parts)
