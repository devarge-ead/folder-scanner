"""Text matching helpers: exact (case-insensitive substring) and fuzzy (rapidfuzz)."""

from rapidfuzz import fuzz


def normalize(value: str) -> str:
    return (value or "").lower()


def matches(query: str, text: str, method: str, threshold: int) -> bool:
    """Return True when ``text`` matches ``query`` under the chosen method."""
    if not query:
        return False
    q = normalize(query)
    if method == "fuzzy":
        return fuzz.partial_ratio(q, normalize(text)) >= threshold
    return q in normalize(text)


def count_exact(query: str, text: str) -> int:
    """Count case-insensitive occurrences of ``query`` inside ``text``."""
    if not query:
        return 0
    return normalize(text).count(normalize(query))