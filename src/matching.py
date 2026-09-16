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
        t = normalize(text)
        # ``partial_ratio`` aligns the *shorter* string inside the longer one,
        # so a very short text (e.g. a spreadsheet cell "no") scores 100
        # against a much longer query ("musteri no") even when unrelated.
        # Guard: when the text is shorter than the query, compare with a
        # symmetric full-similarity ratio instead.
        if len(t) < len(q):
            return fuzz.ratio(q, t) >= threshold
        return fuzz.partial_ratio(q, t) >= threshold
    return q in normalize(text)


def count_exact(query: str, text: str) -> int:
    """Count case-insensitive occurrences of ``query`` inside ``text``."""
    if not query:
        return 0
    return normalize(text).count(normalize(query))