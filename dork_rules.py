"""dork_rules.py — Offline "Smart Presets & Knowledge Base" access layer.

Loads knowledge_base.json and exposes:
  * category / vector lookups for the GUI
  * suggest_terms(topic): zero-dependency intent matcher that maps a
    plain-English request to the best preset category and recommended
    server footprints (the native, offline half of the Smart Engine).
"""

from __future__ import annotations

import json
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent / "knowledge_base.json"


class KnowledgeBaseError(Exception):
    """Raised when the knowledge base file is missing or malformed."""


class KnowledgeBase:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else KB_PATH
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KnowledgeBaseError(f"Knowledge base not found: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseError(f"Knowledge base is not valid JSON: {exc}") from exc

        for section in ("categories", "vectors", "clean_results_exclusions"):
            if section not in self._data:
                raise KnowledgeBaseError(f"Knowledge base is missing section '{section}'.")

    # ------------------------------------------------------------------
    # Raw lookups
    # ------------------------------------------------------------------
    def category_names(self) -> list[str]:
        return list(self._data["categories"].keys())

    def vector_names(self) -> list[str]:
        return list(self._data["vectors"].keys())

    def get_category(self, key: str) -> dict:
        return self._data["categories"][key]

    def get_vector(self, key: str) -> dict:
        return self._data["vectors"][key]

    def clean_results_exclusions(self) -> list[str]:
        return list(self._data["clean_results_exclusions"])

    def category_label(self, key: str) -> str:
        return self.get_category(key).get("label", key)

    def vector_label(self, key: str) -> str:
        return self.get_vector(key).get("label", key)

    # ------------------------------------------------------------------
    # Offline intent matcher
    # ------------------------------------------------------------------
    def suggest_terms(self, topic: str) -> dict:
        """Map a plain-English topic to the best preset category.

        Scores every category by counting how many of its topic_hints
        appear in the user's text. Returns a suggestion bundle the GUI
        can apply directly (keywords, extensions, recommended vectors).
        """
        text = (topic or "").lower()
        best_key, best_score, best_hits = None, 0, []

        for key, cat in self._data["categories"].items():
            hits = [h for h in cat.get("topic_hints", []) if h in text]
            if len(hits) > best_score:
                best_key, best_score, best_hits = key, len(hits), hits

        if best_key is None:
            return {
                "category": None,
                "score": 0,
                "matched_hints": [],
                "keywords": [],
                "extensions": [],
                "recommended_vectors": [],
            }

        cat = self._data["categories"][best_key]
        return {
            "category": best_key,
            "label": cat.get("label", best_key),
            "score": best_score,
            "matched_hints": best_hits,
            "keywords": list(cat.get("keywords", [])),
            "extensions": list(cat.get("extensions", [])),
            "recommended_vectors": list(cat.get("recommended_vectors", [])),
        }


if __name__ == "__main__":  # quick manual check
    kb = KnowledgeBase()
    print("Categories:", kb.category_names())
    print("Vectors:", kb.vector_names())
    demo = kb.suggest_terms("uncompressed 4k nature footage for editing")
    print("Suggestion:", demo)
