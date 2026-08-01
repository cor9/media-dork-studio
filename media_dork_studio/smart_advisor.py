"""Offline intent analysis for responsible search-strategy recommendations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class UnsafeGoalError(ValueError):
    """Raised when a goal asks the advisor to optimize sensitive-data discovery."""


@dataclass(frozen=True, slots=True)
class SearchStrategy:
    """A strategy that can be applied directly to the query-builder UI."""

    keywords: str
    alternatives: tuple[str, ...]
    extensions: tuple[str, ...]
    method: str
    site: str = ""
    cloud_targets: tuple[str, ...] = field(default_factory=tuple)
    media_targets: tuple[str, ...] = field(default_factory=tuple)
    exact_phrase: bool = True
    rationale: str = ""


class SmartAdvisor:
    """Recommend terminology, file types, and likely public search surfaces.

    This deterministic advisor runs entirely on-device. It intentionally does
    not optimize goals centered on secrets, credentials, authentication
    artifacts, or private personal data.
    """

    _UNSAFE = re.compile(
        r"\b(passwords?|credentials?|api[ -]?keys?|access[ -]?tokens?|private[ -]?keys?|"
        r"ssh[ -]?keys?|session[ -]?cookies?|social security|ssn|doxx?(?:ing)?|private pii|"
        r"credit card numbers?)\b|(?:^|\s)\.env(?:\s|$)",
        re.IGNORECASE,
    )
    _CLEAN = re.compile(r"[^a-z0-9.+#' -]+", re.IGNORECASE)
    _SPACES = re.compile(r"\s+")
    _FILLER = {
        "find",
        "search",
        "locate",
        "discover",
        "looking",
        "look",
        "want",
        "need",
        "please",
        "some",
        "for",
        "about",
        "files",
        "file",
        "media",
        "publicly",
        "public",
        "online",
    }

    _INTENTS: dict[str, set[str]] = {
        "dataset": {
            "dataset",
            "datasets",
            "data",
            "statistics",
            "spreadsheet",
            "spreadsheets",
            "database",
            "databases",
            "csv",
            "json",
            "research data",
            "open data",
        },
        "report": {
            "report",
            "reports",
            "study",
            "studies",
            "research",
            "paper",
            "papers",
            "whitepaper",
            "white paper",
            "manual",
            "documentation",
            "thesis",
        },
        "ebook": {"ebook", "ebooks", "book", "books", "epub", "mobi", "publication"},
        "video": {
            "video",
            "videos",
            "film",
            "films",
            "movie",
            "movies",
            "footage",
            "documentary",
            "documentaries",
            "lecture",
            "lectures",
            "webinar",
        },
        "audio": {
            "audio",
            "music",
            "song",
            "songs",
            "album",
            "albums",
            "podcast",
            "podcasts",
            "audiobook",
            "recording",
            "recordings",
            "lossless",
            "flac",
        },
        "archive": {
            "archive",
            "archives",
            "collection",
            "collections",
            "backup",
            "backups",
            "compressed",
            "zip",
        },
    }

    _EXTENSIONS: dict[str, tuple[str, ...]] = {
        "dataset": ("csv", "json", "xlsx", "zip"),
        "report": ("pdf", "docx", "xlsx"),
        "ebook": ("pdf", "epub", "mobi"),
        "video": ("mp4", "mkv", "webm", "mov"),
        "audio": ("mp3", "flac", "wav", "m4a"),
        "archive": ("zip", "tar.gz", "7z", "rar"),
    }

    _ALTERNATIVES: dict[str, tuple[str, ...]] = {
        "dataset": ("dataset", "open data", "data catalog"),
        "report": ("report", "study", "white paper"),
        "ebook": ("ebook", "digital edition", "full text"),
        "video": ("video", "footage", "recording"),
        "audio": ("audio", "recording", "lossless"),
        "archive": ("archive", "collection", "repository"),
    }

    @classmethod
    def suggest(cls, goal: str) -> SearchStrategy:
        """Infer a practical search plan from a plain-language goal."""

        clean_goal = cls._SPACES.sub(" ", cls._CLEAN.sub(" ", goal)).strip()
        if not clean_goal:
            raise ValueError("Describe what you want to discover first.")
        if cls._UNSAFE.search(clean_goal):
            raise UnsafeGoalError(
                "The Smart Advisor does not optimize searches for credentials, secrets, authentication artifacts, or private personal data."
            )

        lowered = clean_goal.casefold()
        words = set(lowered.split())
        scores = {
            intent: sum(2 if " " in signal and signal in lowered else 1 for signal in signals if signal in words or (" " in signal and signal in lowered))
            for intent, signals in cls._INTENTS.items()
        }
        ranked = sorted(scores, key=lambda name: scores[name], reverse=True)
        primary = ranked[0] if scores[ranked[0]] else "report"
        secondary = ranked[1] if scores[ranked[1]] and scores[ranked[1]] == scores[primary] else ""

        extensions = list(cls._EXTENSIONS[primary])
        if secondary:
            extensions.extend(cls._EXTENSIONS[secondary][:2])
        if primary == "dataset" and any(term in lowered for term in ("database", "sql", "database export")):
            extensions.append("sql")
        if primary == "video" and "high quality" in lowered:
            extensions = ["mkv", "mp4", "mov", "webm"]
        if primary == "audio" and any(term in lowered for term in ("lossless", "master", "high quality")):
            extensions = ["flac", "wav", "m4a", "mp3"]
        extensions = list(dict.fromkeys(extensions))

        method, cloud_targets, media_targets = cls._places(lowered, primary)
        site = cls._site(lowered)
        keywords = cls._core_keywords(clean_goal, primary, site)
        alternatives = cls._ALTERNATIVES[primary]
        source_description = site or cls._surface_description(method, cloud_targets, media_targets)
        rationale = (
            f"Detected {primary} intent. Prioritizing {', '.join('.' + value for value in extensions[:4])}; "
            f"using {method.lower()} discovery across {source_description}."
        )

        return SearchStrategy(
            keywords=keywords,
            alternatives=alternatives,
            extensions=tuple(extensions),
            method=method,
            site=site,
            cloud_targets=tuple(cloud_targets),
            media_targets=tuple(media_targets),
            exact_phrase=len(keywords.split()) > 1,
            rationale=rationale,
        )

    @classmethod
    def _places(
        cls, lowered: str, primary: str
    ) -> tuple[str, list[str], list[str]]:
        cloud_map = {
            "aws": "AWS S3",
            "s3": "AWS S3",
            "google cloud": "Google Cloud",
            "gcs": "Google Cloud",
            "azure": "Azure Blob",
            "digitalocean": "DigitalOcean",
            "cloudflare": "Cloudflare R2",
            "r2": "Cloudflare R2",
        }
        cloud_targets = list(
            dict.fromkeys(name for signal, name in cloud_map.items() if signal in lowered)
        )
        if cloud_targets or any(term in lowered for term in ("cloud", "bucket", "cdn", "object storage")):
            return "Cloud / CDN", cloud_targets, []

        media_map = {
            "plex": "Plex",
            "emby": "Emby",
            "ftp": "FTP",
            "h5ai": "h5ai",
            "apache": "Apache / Nginx",
            "nginx": "Apache / Nginx",
        }
        media_targets = list(
            dict.fromkeys(name for signal, name in media_map.items() if signal in lowered)
        )
        if media_targets or "media server" in lowered:
            return "Media Server", [], media_targets
        if any(term in lowered for term in ("open directory", "directory index", "index of")):
            return "Open Directory", [], []
        if primary in {"video", "audio", "ebook", "archive"}:
            return "Open Directory", [], []
        return "Generic", [], []

    @staticmethod
    def _site(lowered: str) -> str:
        if "nasa" in lowered:
            return "nasa.gov"
        if "vimeo" in lowered:
            return "vimeo.com"
        if any(term in lowered for term in ("university", "academic", "college", "scholarly", "thesis")):
            return ".edu"
        if any(term in lowered for term in ("government", "federal", "state agency", "municipal", "public records")):
            return ".gov"
        if any(term in lowered for term in ("internet archive", "archive.org", "historical archive")):
            return "archive.org"
        return ""

    @classmethod
    def _core_keywords(cls, clean_goal: str, primary: str, site: str) -> str:
        intent_words = {word for signal in cls._INTENTS[primary] for word in signal.split()}
        source_words = {
            "government",
            "federal",
            "academic",
            "university",
            "college",
            "nasa",
            "vimeo",
            "archive.org",
        }
        tokens = [
            token
            for token in clean_goal.split()
            if token.casefold() not in cls._FILLER
            and token.casefold() not in intent_words
            and (not site or token.casefold() not in source_words)
        ]
        core = " ".join(tokens).strip(" -")
        if core:
            return core
        return primary

    @staticmethod
    def _surface_description(
        method: str, cloud_targets: list[str], media_targets: list[str]
    ) -> str:
        if cloud_targets:
            return ", ".join(cloud_targets)
        if media_targets:
            return ", ".join(media_targets)
        return {
            "Open Directory": "public directory indexes",
            "Cloud / CDN": "major public cloud endpoints",
            "Media Server": "public media-server indexes",
            "Generic": "the public web index",
        }[method]
