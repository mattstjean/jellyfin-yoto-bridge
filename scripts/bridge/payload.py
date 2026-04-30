"""Build the JSON payload Yoto expects from createOrUpdateContent.

Each Jellyfin track becomes its own Yoto chapter (one-track-per-chapter), so
Yoto's resume behavior tracks the user's position at chapter granularity.
"""

from typing import Dict, Any, List, Optional, Callable

from .icons import pick_icon


def _icon_ref(media_id: Optional[str]) -> Optional[str]:
    return f"yoto:#{media_id}" if media_id else None


def build_payload(
    book: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    icons: List[Dict[str, Any]],
    stream_url_for: Callable[[str], str],
    existing_card_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a Yoto createOrUpdateContent payload.

    `stream_url_for(item_id)` is a callable that builds a streaming URL — passed
    in so this module doesn't need to know about Jellyfin specifics.
    """
    book_icon = pick_icon(icons, [book.get("Name", "")])

    chapters = []
    for i, t in enumerate(tracks, 1):
        title = t.get("Name", f"Chapter {i}")
        duration = (t.get("RunTimeTicks") or 0) // 10_000_000  # ticks → seconds
        ch_icon = pick_icon(icons, [title]) or book_icon
        icon_ref = _icon_ref(ch_icon)

        track_obj: Dict[str, Any] = {
            "key": "01",
            "title": title,
            "trackUrl": stream_url_for(t["Id"]),
            "type": "stream",
            "format": "mp3",
            "duration": duration,
            "overlayLabel": str(i),
        }
        if icon_ref:
            track_obj["display"] = {"icon16x16": icon_ref}

        chapter_obj: Dict[str, Any] = {
            "key": f"{i:02d}",
            "title": title,
            "overlayLabel": str(i),
            "tracks": [track_obj],
        }
        if icon_ref:
            chapter_obj["display"] = {"icon16x16": icon_ref}

        chapters.append(chapter_obj)

    artists = book.get("Artists") or [
        a.get("Name", "") for a in book.get("AlbumArtists", [])
    ]
    payload: Dict[str, Any] = {
        "title": book.get("Name", "Untitled"),
        "content": {
            "chapters": chapters,
            "config": {"resumeTimeout": 2592000},  # 30 days
            "playbackType": "linear",
        },
        "metadata": {
            "description": f"By {', '.join(filter(None, artists))}" if artists else "",
        },
    }
    if existing_card_id:
        payload["cardId"] = existing_card_id
    return payload


def redact_payload_for_display(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy with API keys stripped from URLs (for --dry-run)."""
    import json
    redacted = json.loads(json.dumps(payload))
    for ch in redacted.get("content", {}).get("chapters", []):
        for tr in ch.get("tracks", []):
            url = tr.get("trackUrl", "")
            if "api_key=" in url:
                tr["trackUrl"] = url.split("api_key=")[0] + "api_key=<HIDDEN>" + url.split("api_key=")[1].split("&", 1)[-1] 
    return redacted