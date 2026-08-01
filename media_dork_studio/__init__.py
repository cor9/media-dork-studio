"""Media Dork Studio package."""

from .dork_builder import DorkBuilder, DorkConfig
from .models import SearchResult
from .search_engine import SearchEngine, SearchEngineError
from .smart_advisor import SearchStrategy, SmartAdvisor, UnsafeGoalError

__all__ = [
    "DorkBuilder",
    "DorkConfig",
    "SearchEngine",
    "SearchEngineError",
    "SearchResult",
    "SearchStrategy",
    "SmartAdvisor",
    "UnsafeGoalError",
]

__version__ = "1.0.0"
