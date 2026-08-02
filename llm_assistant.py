"""llm_assistant.py — Optional "LLM Query Optimizer".

Supports two providers, both reached with the Python standard library
(no extra dependencies):
  * OpenAI   — POST https://api.openai.com/v1/chat/completions
  * Ollama   — POST http://localhost:11434/api/chat  (local, default)

The model is instructed to answer with a strict JSON object:
    primary_keywords : list[str]   suggested primary keywords
    file_types       : list[str]   recommended extensions (".mov" / "mov")
    target_vectors   : list[str]   keys from the knowledge base vector set
    suggested_sites  : list[str]   extra site: targets
    exclusions       : list[str]   suggested exclusions ("-youtube")
    dork             : str         fully formatted, ready-to-run dork string
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from dork_builder import (VALID_VECTOR_KEYS, DorkParameters, build_query,
                          sanitize_term)

SYSTEM_PROMPT = (
    "You are an expert Google advanced-search ('dork') query optimizer for locating "
    "publicly indexed media assets, open directories and cloud storage. "
    "Given the user's plain-English intent, respond with a single JSON object and "
    "NOTHING else (no markdown fences, no commentary). The JSON object must have "
    "exactly these keys:\n"
    '  "primary_keywords": list of strings, e.g. ["nature", "\\"4k\\"", "prores OR \\"b-roll\\""]\n'
    '  "file_types":       list of recommended extensions, e.g. [".mov", ".mp4"]\n'
    '  "target_vectors":   list chosen from ["open_directories", "cdn_storage", '
    '"media_servers", "ftp_servers", "educational", "web_archives"]\n'
    '  "suggested_sites":  list of extra site targets, e.g. ["s3.amazonaws.com"]\n'
    '  "exclusions":       list of exclusion terms, e.g. ["-youtube", "-vimeo"]\n'
    '  "dork":             the fully formatted, optimized Google dork string\n'
    "Rules for the dork string: use ONLY the operators site:, filetype:, ext:, "
    "intitle:, allintitle:, inurl:, allinurl:, intext:, double quotes for exact "
    "match, - for exclusion, uppercase OR, AND and parentheses for grouping. "
    "NEVER use ~, unary +, or daterange:. Group alternatives with OR inside "
    "parentheses for maximum relevant hit rate."
)

DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"


class LLMError(Exception):
    """Raised for connection, authentication, or response-format failures."""


@dataclass
class LLMConfig:
    provider: str = "ollama"          # "openai" | "ollama"
    model: str = "llama3.1"
    api_key: str = ""                 # OpenAI only; falls back to OPENAI_API_KEY
    base_url: str = ""                # optional endpoint override
    timeout: int = 60


# ----------------------------------------------------------------------
# Config helpers
# ----------------------------------------------------------------------
_DOTENV_LOADED = False


def _load_dotenv() -> None:
    """Populate os.environ from a .env file next to this module (once).

    Existing environment variables always win; no third-party deps needed.
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass  # no .env file is fine


# ----------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ----------------------------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Cannot reach {url} ({exc.reason}).") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f"Bad or slow response from {url}: {exc}") from exc


def _extract_json(text: str) -> dict:
    """Tolerantly pull the first JSON object out of a model response."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError("Model did not return a parseable JSON object.")


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def optimize_query(user_prompt: str, config: LLMConfig) -> dict:
    """Send the user's intent to the configured LLM, return normalized JSON."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if config.provider == "openai":
        _load_dotenv()
        key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise LLMError("OpenAI selected but no API key provided "
                           "(enter one or set OPENAI_API_KEY).")
        url = config.base_url or DEFAULT_OPENAI_URL
        payload = {
            "model": config.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        data = _post_json(url, payload, {"Authorization": f"Bearer {key}"}, config.timeout)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected OpenAI response shape: {data!r:.300}") from exc

    elif config.provider == "ollama":
        url = config.base_url or DEFAULT_OLLAMA_URL
        payload = {
            "model": config.model or "llama3.1",
            "messages": messages,
            "format": "json",
            "stream": False,
        }
        try:
            data = _post_json(url, payload, {}, config.timeout)
        except LLMError as exc:
            raise LLMError(f"{exc} Is Ollama running? Try `ollama serve` "
                           f"and `ollama pull {config.model or 'llama3.1'}`.") from exc
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Ollama response shape: {data!r:.300}") from exc
    else:
        raise LLMError(f"Unknown provider: {config.provider!r}")

    return normalize_result(_extract_json(content))


def normalize_result(data: dict) -> dict:
    """Sanitize every field and guarantee a usable dork string exists."""
    def _clean_list(key: str) -> list[str]:
        raw = data.get(key, [])
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            item = sanitize_term(str(item))
            if item:
                out.append(item)
        return out

    keywords = _clean_list("primary_keywords")
    file_types = [f.lower().lstrip(".") for f in _clean_list("file_types")]
    sites = _clean_list("suggested_sites")
    exclusions = [e.lstrip("-").strip() for e in _clean_list("exclusions")]
    vectors = [v for v in _clean_list("target_vectors") if v in VALID_VECTOR_KEYS]

    dork = sanitize_term(str(data.get("dork", "") or ""))
    if not dork:  # build one ourselves if the model omitted it
        dork = build_query(DorkParameters(
            keywords=keywords, extensions=file_types, sites=sites,
            exclusions=exclusions,
        ))

    return {
        "primary_keywords": keywords,
        "file_types": file_types,
        "target_vectors": vectors,
        "suggested_sites": sites,
        "exclusions": exclusions,
        "dork": dork,
    }
