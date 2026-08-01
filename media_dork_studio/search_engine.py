"""Google Custom Search API and browser-launch integration."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from pathlib import PurePosixPath
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .models import SearchResult


class SearchEngineError(RuntimeError):
    """User-facing error raised by search operations."""


class SearchEngine:
    """Thin client for Google's official Custom Search JSON API."""

    API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
    GOOGLE_SEARCH_URL = "https://www.google.com/search"

    def __init__(
        self,
        timeout: float = 20.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self.timeout = timeout
        self._opener = opener

    def search(
        self,
        query: str,
        api_key: str,
        engine_id: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search Google CSE and normalize up to *limit* results."""

        if not query.strip():
            raise SearchEngineError("Build a query before searching.")
        if not api_key.strip() or not engine_id.strip():
            raise SearchEngineError("API Key and Search Engine ID are required.")

        requested = max(1, min(int(limit), 50))
        collected: list[SearchResult] = []
        start = 1

        while len(collected) < requested:
            page_size = min(10, requested - len(collected))
            payload = self._request_page(
                query=query,
                api_key=api_key.strip(),
                engine_id=engine_id.strip(),
                start=start,
                page_size=page_size,
            )
            items = payload.get("items", [])
            if not isinstance(items, list) or not items:
                break
            collected.extend(self._normalize_item(item) for item in items if isinstance(item, dict))
            if len(items) < page_size:
                break
            start += len(items)

        return collected[:requested]

    def browser_url(self, query: str) -> str:
        """Return a safely encoded Google Search URL."""

        return f"{self.GOOGLE_SEARCH_URL}?{urlencode({'q': query})}"

    def open_in_browser(self, query: str) -> bool:
        """Open the generated query in the operating system's browser."""

        if not query.strip():
            raise SearchEngineError("Build a query before opening the browser.")
        return webbrowser.open_new_tab(self.browser_url(query))

    def _request_page(
        self,
        *,
        query: str,
        api_key: str,
        engine_id: str,
        start: int,
        page_size: int,
    ) -> dict:
        params = urlencode(
            {
                "key": api_key,
                "cx": engine_id,
                "q": query,
                "start": start,
                "num": page_size,
                "safe": "active",
            }
        )
        request = Request(
            f"{self.API_ENDPOINT}?{params}",
            headers={"Accept": "application/json", "User-Agent": "MediaDorkStudio/1.0"},
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            message = self._http_error_message(error)
            raise SearchEngineError(message) from error
        except URLError as error:
            raise SearchEngineError(
                f"Could not reach Google Custom Search: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise SearchEngineError("Google Custom Search timed out. Try again.") from error

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SearchEngineError("Google returned an unreadable response.") from error

        if not isinstance(payload, dict):
            raise SearchEngineError("Google returned an unexpected response.")
        if "error" in payload:
            detail = payload.get("error", {})
            message = detail.get("message", "Google Custom Search rejected the request.")
            raise SearchEngineError(str(message))
        return payload

    @staticmethod
    def _http_error_message(error: HTTPError) -> str:
        if error.code == 429:
            return "Google rate limit reached (429). Wait, reduce requests, or open the query in your browser."
        if error.code == 403:
            return "Google rejected the request (403). Check the API key, API enablement, quota, and Search Engine ID."
        if error.code == 400:
            return "Google rejected the query (400). Check the API key, Engine ID, and query syntax."
        return f"Google Custom Search failed with HTTP {error.code}."

    @classmethod
    def _normalize_item(cls, item: dict) -> SearchResult:
        link = str(item.get("link", ""))
        source = str(item.get("displayLink", "")) or urlsplit(link).netloc
        return SearchResult(
            title=str(item.get("title", "Untitled result")),
            source=source,
            link=link,
            file_type=cls._detect_file_type(link, str(item.get("mime", ""))),
            snippet=str(item.get("snippet", "")),
        )

    @staticmethod
    def _detect_file_type(link: str, mime_type: str = "") -> str:
        path = PurePosixPath(urlsplit(link).path.lower())
        filename = path.name
        known_compound = ("tar.gz", "tar.bz2", "tar.xz")
        for extension in known_compound:
            if filename.endswith(f".{extension}"):
                return extension
        suffix = path.suffix.lstrip(".")
        if suffix:
            return suffix
        guessed = mimetypes.guess_extension(mime_type.split(";", 1)[0].strip())
        return guessed.lstrip(".") if guessed else "unknown"
