import io
import json
from urllib.error import HTTPError

import pytest

from media_dork_studio.search_engine import SearchEngine, SearchEngineError


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_search_normalizes_results_and_encodes_query() -> None:
    def opener(request, timeout):
        assert "q=filetype%3Apdf" in request.full_url
        assert timeout == 5
        return FakeResponse(
            {
                "items": [
                    {
                        "title": "Public report",
                        "displayLink": "example.edu",
                        "link": "https://example.edu/files/report.pdf",
                        "mime": "application/pdf",
                        "snippet": "A public report",
                    }
                ]
            }
        )

    results = SearchEngine(timeout=5, opener=opener).search(
        "filetype:pdf", "key", "engine", limit=1
    )

    assert len(results) == 1
    assert results[0].source == "example.edu"
    assert results[0].file_type == "pdf"
    assert results[0].link.endswith("report.pdf")


def test_compound_extension_detection() -> None:
    assert SearchEngine._detect_file_type("https://example.com/data/archive.tar.gz") == "tar.gz"


def test_rate_limit_has_actionable_error() -> None:
    def opener(_request, timeout):
        raise HTTPError("https://example.test", 429, "Too Many", {}, io.BytesIO())

    with pytest.raises(SearchEngineError, match="rate limit"):
        SearchEngine(opener=opener).search("filetype:mp4", "key", "engine")


def test_browser_url_is_encoded() -> None:
    url = SearchEngine().browser_url('intitle:"index of" filetype:mp4')
    assert url.startswith("https://www.google.com/search?")
    assert "%22index+of%22" in url
