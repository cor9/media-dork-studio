"""results_engine.py — Results-tab backend.

* extract_urls_from_text : pull URLs out of pasted text OR search-API JSON
                           (SerpAPI-style "organic_results" -> "link", or any
                           "link"/"url"/"href" keys, recursively)
* validate_links         : threaded HTTP status checks (200/404/...) with
                           HEAD-first requests and a GET fallback
* export_results         : write results to .JSON / .CSV / .TXT
"""

from __future__ import annotations

import csv
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+")
LINK_KEYS = {"link", "url", "href"}
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36 DorkForge/1.0")


@dataclass
class LinkResult:
    url: str
    status: int | None = None
    ok: bool = False
    error: str | None = None


# ----------------------------------------------------------------------
# URL extraction
# ----------------------------------------------------------------------
def _walk_for_links(node, found: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in LINK_KEYS and isinstance(value, str) and value.startswith("http"):
                found.append(value)
            else:
                _walk_for_links(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_for_links(item, found)


def extract_urls_from_text(text: str) -> list[str]:
    """Extract deduplicated URLs from pasted URLs, text, or search-API JSON."""
    text = (text or "").strip()
    found: list[str] = []

    try:  # maybe the user pasted a whole API response
        _walk_for_links(json.loads(text), found)
    except json.JSONDecodeError:
        pass

    found += URL_RE.findall(text)  # always also scan raw text

    seen, out = set(), []
    for url in found:
        url = url.rstrip(".,;)")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# ----------------------------------------------------------------------
# Link validation
# ----------------------------------------------------------------------
def _check_one(url: str, timeout: float) -> LinkResult:
    headers = {"User-Agent": USER_AGENT}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return LinkResult(url=url, status=resp.status, ok=200 <= resp.status < 400)
        except urllib.error.HTTPError as exc:
            if exc.code == 405 and method == "HEAD":  # method not allowed -> retry GET
                continue
            return LinkResult(url=url, status=exc.code, ok=exc.code in (401, 403),
                              error=None if exc.code in (401, 403) else f"HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return LinkResult(url=url, error=str(getattr(exc, "reason", exc)))
    return LinkResult(url=url, error="unreachable")


def validate_links(urls: list[str], on_result=None, timeout: float = 8.0,
                   max_workers: int = 8) -> list[LinkResult]:
    """Check each URL concurrently. on_result(LinkResult) fires per completion
    (from a worker thread — GUI code should marshal to the main thread)."""
    results: list[LinkResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_check_one, u, timeout): u for u in urls}
        for fut in futures:
            try:
                res = fut.result()
            except Exception as exc:  # never let one bad URL kill the batch
                res = LinkResult(url=futures[fut], error=str(exc))
            results.append(res)
            if on_result:
                on_result(res)
    return results


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------
def export_results(results: list[LinkResult], path: str, fmt: str) -> None:
    fmt = fmt.lower()
    rows = [asdict(r) for r in results]
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
    elif fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["url", "status", "ok", "error"])
            writer.writeheader()
            writer.writerows(rows)
    elif fmt == "txt":
        with open(path, "w", encoding="utf-8") as fh:
            for r in results:
                tag = r.status if r.status is not None else (r.error or "error")
                fh.write(f"{r.url} [{tag}]\n")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
