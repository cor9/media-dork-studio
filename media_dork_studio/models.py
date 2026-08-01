"""Shared data models for search results."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A normalized Google Custom Search result."""

    title: str
    source: str
    link: str
    file_type: str
    snippet: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return a stable, export-friendly dictionary."""

        return asdict(self)
