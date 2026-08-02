"""dork_builder.py — Query builder logic and string sanitizer.

Turns a DorkParameters bundle into a precision Google dork string using
only modern, functional operators (2026 standard):

    VALID:      site: filetype: ext: intitle: allintitle: inurl:
                allinurl: intext: "" (exact) - (exclusion) OR | AND ()
    DEPRECATED: ~ (synonyms), unary + , daterange:   -> stripped/rejected
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

OPERATOR_PREFIXES = (
    "site:", "filetype:", "ext:", "intitle:", "allintitle:",
    "inurl:", "allinurl:", "intext:",
)

VALID_VECTOR_KEYS = (
    "open_directories", "cdn_storage", "media_servers",
    "ftp_servers", "educational", "web_archives",
)


# ----------------------------------------------------------------------
# Sanitizer
# ----------------------------------------------------------------------
def sanitize_term(term: str) -> str:
    """Normalize a single term; strip deprecated operator syntax.

    * daterange: tokens are dropped entirely (returns "")
    * leading ~ (synonym operator) and unary + are stripped
    * internal whitespace is collapsed
    """
    t = (term or "").strip()
    if not t:
        return ""
    if t.lower().startswith("daterange:"):
        return ""
    changed = True
    while changed and t:
        changed = False
        while t.startswith("~"):
            t = t[1:].lstrip()
            changed = True
        while t.startswith("+") and len(t) > 1 and not t.startswith("+ "):
            t = t[1:].lstrip()
            changed = True
    return re.sub(r"\s+", " ", t)


def _is_operator_fragment(term: str) -> bool:
    """True if the term already carries an operator or exclusion prefix."""
    low = term.lower()
    return low.startswith(OPERATOR_PREFIXES) or term.startswith("-")


def _quote(term: str) -> str:
    """Quote multi-word plain terms; leave operators/quotes untouched."""
    if not term:
        return ""
    if _is_operator_fragment(term):
        return term
    if term.startswith('"') and term.endswith('"') and len(term) >= 2:
        return term
    if " " in term:
        return f'"{term}"'
    return term


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


def _or_group(parts: list[str]) -> str:
    parts = _dedupe([p for p in parts if p])
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


def _site_fragment(site: str) -> str:
    s = sanitize_term(site)
    if not s:
        return ""
    return s if s.lower().startswith("site:") else f"site:{s}"


def _exclusion_fragment(term: str) -> str:
    t = _quote(sanitize_term(term.lstrip("-").strip()))
    return f"-{t}" if t else ""


# ----------------------------------------------------------------------
# Parameter bundle
# ----------------------------------------------------------------------
@dataclass
class DorkParameters:
    keywords: list[str] = field(default_factory=list)          # OR-grouped alternatives
    extensions: list[str] = field(default_factory=list)        # -> filetype: group
    sites: list[str] = field(default_factory=list)             # -> site: target surface
    inurl: list[str] = field(default_factory=list)             # -> inurl: refinements
    intitle: list[str] = field(default_factory=list)           # -> intitle: refinements
    intext: list[str] = field(default_factory=list)            # -> intext: refinements
    exclusions: list[str] = field(default_factory=list)        # -> -term each
    vector_footprints: dict[str, list[str]] = field(default_factory=dict)  # raw fragments
    clean_results: bool = False
    clean_exclusions: list[str] = field(default_factory=list)  # anti-clutter set


# ----------------------------------------------------------------------
# Builder
# ----------------------------------------------------------------------
def build_query(params: DorkParameters) -> str:
    """Assemble the final dork string.

    Semantics, tuned for peak relevant hit rate:
      * keywords OR together (any may match)
      * every target surface (sites + vector footprints) ORs into ONE
        parenthesized group, so enabling several vectors widens — never
        narrows — the search
      * extensions / inurl / intitle / intext refine (AND) the query
      * exclusions are appended as -terms
    """
    parts: list[str] = []

    # 1. Keywords (OR group)
    kw_group = _or_group([_quote(sanitize_term(k)) for k in params.keywords])
    if kw_group:
        parts.append(kw_group)

    # 2. Target surface: sites + raw vector footprints in a single OR group
    target_parts = [_site_fragment(s) for s in params.sites]
    for key in params.vector_footprints:
        for frag in params.vector_footprints[key]:
            frag = sanitize_term(frag)
            if frag:
                target_parts.append(frag)
    target_group = _or_group(target_parts)
    if target_group:
        parts.append(target_group)

    # 3. Extensions -> filetype:
    exts = [sanitize_term(e).lower().lstrip(".") for e in params.extensions]
    ext_group = _or_group([f"filetype:{e}" for e in exts if e])
    if ext_group:
        parts.append(ext_group)

    # 4. Refinement groups
    for prefix, values in (("inurl", params.inurl),
                           ("intitle", params.intitle),
                           ("intext", params.intext)):
        group = _or_group([f"{prefix}:{_quote(sanitize_term(v))}" for v in values])
        if group:
            parts.append(group)

    # 5. Exclusions (user + smart noise reduction)
    exclusions = list(params.exclusions)
    if params.clean_results:
        exclusions += list(params.clean_exclusions)
    for term in _dedupe([_exclusion_fragment(e) for e in exclusions]):
        parts.append(term)

    return " ".join(p for p in parts if p).strip()


# ----------------------------------------------------------------------
# Validator — enforces the 2026 operator standard on ANY string
# ----------------------------------------------------------------------
def validate_query(query: str) -> list[str]:
    """Return a list of warnings about deprecated/broken syntax (empty = clean)."""
    warnings: list[str] = []
    q = query or ""

    if "~" in q:
        warnings.append("Deprecated '~' (synonym) operator detected — Google ignores it.")
    if re.search(r"(?:^|\s)\+\S", q):
        warnings.append("Deprecated unary '+' operator detected — remove it; terms are ANDed by default.")
    if re.search(r"\bdaterange:", q, re.IGNORECASE):
        warnings.append("Deprecated 'daterange:' operator detected — use Google's native date filter instead.")
    if q.count('"') % 2 != 0:
        warnings.append("Unbalanced double quotes detected.")
    if q.count("(") != q.count(")"):
        warnings.append("Unbalanced parentheses detected.")

    # lowercase boolean words outside quoted phrases do nothing on Google
    unquoted = re.sub(r'"[^"]*"', "", q)
    for word in re.findall(r"\b(or|and)\b", unquoted):
        warnings.append(f"Lowercase '{word}' is ignored by Google — use uppercase '{word.upper()}'.")
        break

    return warnings


if __name__ == "__main__":  # quick manual check
    p = DorkParameters(
        keywords=["nature", "\"4k\"", "prores OR \"b-roll\""],
        extensions=["mov", "mp4"],
        sites=["s3.amazonaws.com"],
        vector_footprints={"open_directories": ['intitle:"index of /"', '"parent directory"']},
        exclusions=["youtube", "vimeo"],
        clean_results=True,
        clean_exclusions=["html", "htm", "php"],
    )
    q = build_query(p)
    print(q)
    print("warnings:", validate_query(q))
