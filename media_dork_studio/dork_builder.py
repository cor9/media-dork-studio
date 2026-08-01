"""Safe, testable Google dork query construction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable


@dataclass(slots=True)
class DorkConfig:
    """Inputs used to construct a Google search query."""

    extensions: list[str] = field(default_factory=list)
    custom_extensions: str = ""
    method: str = "Open Directory"
    cloud_targets: list[str] = field(default_factory=list)
    media_targets: list[str] = field(default_factory=list)
    keywords: str = ""
    keyword_alternatives: str = ""
    exact_phrase: bool = False
    site: str = ""
    exclude_terms: str = "html, htm, php, asp, aspx, jsp"
    after_date: str = ""
    before_date: str = ""
    size_hint: str = ""


class DorkBuilder:
    """Construct queries from constrained UI inputs.

    The builder removes query-control punctuation from free-form fields so one
    input cannot accidentally break the surrounding operator groups.
    """

    FILE_TYPES: dict[str, tuple[str, ...]] = {
        "Video": ("mp4", "mkv", "avi", "mov", "webm", "flv"),
        "Audio": ("mp3", "flac", "wav", "aac", "ogg", "m4a"),
        "Documents / PDFs": (
            "pdf",
            "epub",
            "mobi",
            "doc",
            "docx",
            "xls",
            "xlsx",
        ),
        "Archives / Data": (
            "zip",
            "tar.gz",
            "rar",
            "7z",
            "csv",
            "json",
            "sql",
        ),
    }

    CLOUD_TARGETS: dict[str, str] = {
        "AWS S3": "s3.amazonaws.com",
        "Google Cloud": "storage.googleapis.com",
        "Azure Blob": "blob.core.windows.net",
        "DigitalOcean": "digitaloceanspaces.com",
        "Cloudflare R2": "r2.dev",
    }

    MEDIA_TARGETS: dict[str, str] = {
        "Plex": '("Plex Media Server" OR inurl:/web/index.html)',
        "Emby": '("Emby Server" OR inurl:/web/index.html)',
        "Apache / Nginx": '(intitle:"index of" OR intitle:"directory listing")',
        "FTP": "inurl:ftp",
        "h5ai": '(intitle:"h5ai" OR inurl:_h5ai)',
    }

    METHODS = ("Open Directory", "Cloud / CDN", "Media Server", "Generic")

    _CONTROL_CHARS = re.compile(r'["\\(){}\[\]|<>]')
    _WHITESPACE = re.compile(r"\s+")
    _EXTENSION = re.compile(r"^[a-z0-9][a-z0-9.+-]{0,15}$")
    _SITE = re.compile(
        r"^\.?[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$", re.IGNORECASE
    )
    _EXCLUDE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$", re.IGNORECASE)

    @classmethod
    def build(cls, config: DorkConfig) -> str:
        """Build a normalized query string from *config*."""

        parts: list[str] = []

        vector = cls._method_clause(
            config.method, config.cloud_targets, config.media_targets
        )
        if vector:
            parts.append(vector)

        keyword = cls._sanitize_text(config.keywords)
        if keyword:
            parts.append(f'"{keyword}"' if config.exact_phrase else keyword)

        alternatives = cls._alternative_clause(config.keyword_alternatives)
        if alternatives:
            parts.append(alternatives)

        extensions = cls.normalize_extensions(
            [*config.extensions, *cls._split_custom_extensions(config.custom_extensions)]
        )
        if extensions:
            file_clauses = [f"filetype:{extension}" for extension in extensions]
            parts.append(
                file_clauses[0]
                if len(file_clauses) == 1
                else f"({' OR '.join(file_clauses)})"
            )

        site = cls.normalize_site(config.site)
        if site:
            parts.append(f"site:{site}")

        parts.extend(cls._exclude_clauses(config.exclude_terms))

        after = cls._valid_iso_date(config.after_date)
        before = cls._valid_iso_date(config.before_date)
        if after:
            parts.append(f"after:{after}")
        if before:
            parts.append(f"before:{before}")

        size_hint = cls._sanitize_text(config.size_hint)
        if size_hint:
            parts.append(f'"{size_hint}"')

        return " ".join(parts)

    @classmethod
    def normalize_extensions(cls, extensions: Iterable[str]) -> list[str]:
        """Normalize, validate, and de-duplicate extension values."""

        normalized: list[str] = []
        seen: set[str] = set()
        for value in extensions:
            extension = value.strip().lower().lstrip(".")
            if not extension or not cls._EXTENSION.fullmatch(extension):
                continue
            if extension not in seen:
                normalized.append(extension)
                seen.add(extension)
        return normalized

    @classmethod
    def normalize_site(cls, value: str) -> str:
        """Return a domain/TLD suitable for a ``site:`` operator."""

        site = value.strip().lower()
        site = re.sub(r"^site:\s*", "", site)
        site = re.sub(r"^https?://", "", site)
        site = site.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        site = site.rstrip(".")
        return site if site and cls._SITE.fullmatch(site) else ""

    @classmethod
    def _method_clause(
        cls, method: str, cloud_targets: list[str], media_targets: list[str]
    ) -> str:
        if method == "Open Directory":
            return (
                '(intitle:"index of" OR intitle:"directory listing") '
                '("parent directory" OR "last modified" OR "size")'
            )
        if method == "Cloud / CDN":
            chosen = cloud_targets or list(cls.CLOUD_TARGETS)
            targets = [cls.CLOUD_TARGETS[name] for name in chosen if name in cls.CLOUD_TARGETS]
            if not targets:
                return ""
            clauses = [f"site:{target}" for target in targets]
            return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"
        if method == "Media Server":
            chosen = media_targets or list(cls.MEDIA_TARGETS)
            clauses = [cls.MEDIA_TARGETS[name] for name in chosen if name in cls.MEDIA_TARGETS]
            if not clauses:
                return ""
            return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"
        return ""

    @classmethod
    def _sanitize_text(cls, value: str) -> str:
        value = cls._CONTROL_CHARS.sub(" ", value)
        value = value.replace(":", " ")
        return cls._WHITESPACE.sub(" ", value).strip()

    @classmethod
    def _split_custom_extensions(cls, value: str) -> list[str]:
        return re.split(r"[\s,;|]+", value.strip()) if value.strip() else []

    @classmethod
    def _alternative_clause(cls, value: str) -> str:
        alternatives: list[str] = []
        seen: set[str] = set()
        for raw in re.split(r"[,;]+", value):
            phrase = cls._sanitize_text(raw)
            if not phrase or phrase.casefold() in seen:
                continue
            seen.add(phrase.casefold())
            alternatives.append(f'"{phrase}"' if " " in phrase else phrase)
        if not alternatives:
            return ""
        return alternatives[0] if len(alternatives) == 1 else f"({' OR '.join(alternatives)})"

    @classmethod
    def _exclude_clauses(cls, value: str) -> list[str]:
        clauses: list[str] = []
        seen: set[str] = set()
        for raw in re.split(r"[\s,;]+", value.strip()):
            term = raw.strip().lstrip("-").lower()
            if term and cls._EXCLUDE.fullmatch(term) and term not in seen:
                clauses.append(f"-{term}")
                seen.add(term)
        return clauses

    @staticmethod
    def _valid_iso_date(value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return ""
