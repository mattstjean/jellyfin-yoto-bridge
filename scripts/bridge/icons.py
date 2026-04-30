"""Pick a Yoto icon based on text keywords.

Lazy keyword overlap scoring. Falls back to generic icons (book/story/audio)
when no chapter-specific icon scores well. Returns the icon's mediaId, which
the payload module formats as `yoto:#<id>`.
"""

from typing import List, Dict, Any, Optional, Sequence

DEFAULT_FALLBACK = ("book", "story", "audio")


def pick_icon(
    icons: List[Dict[str, Any]],
    keywords: Sequence[str],
    fallback_terms: Sequence[str] = DEFAULT_FALLBACK,
) -> Optional[str]:
    """
    Score icons by tag/title overlap with keywords; fall back to generic terms,
    then to the first icon, then to None.
    """
    keywords_lower = [k.lower() for k in keywords if k]
    best, best_score = None, 0

    for icon in icons:
        tags = [t.lower() for t in icon.get("publicTags", [])]
        title = icon.get("title", "").lower()
        score = sum(
            1 for kw in keywords_lower
            if any(t in kw for t in tags) or kw in title
        )
        if score > best_score:
            best, best_score = icon, score

    if best:
        return best.get("mediaId")

    for term in fallback_terms:
        for icon in icons:
            if term in icon.get("title", "").lower() or term in [
                t.lower() for t in icon.get("publicTags", [])
            ]:
                return icon.get("mediaId")

    return icons[0].get("mediaId") if icons else None