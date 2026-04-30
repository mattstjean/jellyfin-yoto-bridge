"""Jellyfin client.

Wraps the bits of the Jellyfin API we actually use: searching for audiobooks,
fetching their tracks, and constructing playable stream URLs.
"""

import urllib.parse
from typing import Dict, Any, List

from . import http
from .pretty_output import info, fail


class Jellyfin:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key

    # ---------- Internal ----------

    def _get(self, path: str, **params) -> Dict[str, Any]:
        params["api_key"] = self.api_key
        url = f"{self.url}{path}?" + urllib.parse.urlencode(params)
        status, body = http.request("GET", url)
        if status == 0:
            fail(f"Couldn't reach Jellyfin at {self.url}. Is it running, and is the URL correct?")
        if status == 401:
            fail("Jellyfin rejected the API key. Generate a new one in Dashboard → API Keys.")
        if status != 200:
            fail(f"Jellyfin error ({status}): {body.get('error') or body}")
        return body

    # ---------- Public ----------

    def find_audiobook(self, search: str) -> Dict[str, Any]:
        """
        Find a single audiobook by search term, prompting if multiple match.

        Searches for both folders (chapter collections) and single-file audiobooks,
        and ranks folders ahead of single files in the disambiguation prompt
        because a folder of chapters is almost always what a user wants for Yoto.
        """
        body = self._get(
            "/Items",
            searchTerm=search,
            IncludeItemTypes="AudioBook,MusicAlbum,Folder",
            Recursive="true",
            Limit=20,
        )
        items = body.get("Items", [])

        # Drop noise: only keep folders or audio items.
        items = [
            i for i in items
            if i.get("IsFolder") or i.get("MediaType") == "Audio"
        ]

        if not items:
            fail(
                f"No audiobooks found matching '{search}'.\n"
                f"  Tip: try a shorter search, or check the book is in a "
                f"library typed as Books or Audiobooks."
            )

        # Sort: folders first (likely the chapter collection), then by name.
        items.sort(key=lambda i: (not i.get("IsFolder", False), i.get("Name", "")))

        if len(items) == 1:
            return items[0]

        info(f"Found {len(items)} matches:")
        for i, m in enumerate(items, 1):
            artists = m.get("Artists") or [
                a.get("Name", "?") for a in m.get("AlbumArtists", [])
            ]
            kind = "folder" if m.get("IsFolder") else "file"
            artist_str = ", ".join(artists) if artists else "unknown"
            info(f"  [{i}] {m['Name']} ({kind}) — {artist_str}")
        pick = input("Which one? ").strip()
        try:
            return items[int(pick) - 1]
        except (ValueError, IndexError):
            fail("Invalid selection.")
            return {}

    def get_tracks(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Return all audio tracks for a book.

        If the item is a folder/album, returns its child audio tracks in order.
        If the item is a single audio file (e.g. one big M4B), returns just it.
        """
        # Single-file audiobook: no children to fetch, the item itself is the track.
        if not item.get("IsFolder", False) and item.get("MediaType") == "Audio":
            return [self._get_full_item(item["Id"])]

        body = self._get(
            "/Items",
            parentId=item["Id"],
            SortBy="IndexNumber,SortName",
            Fields="IndexNumber,RunTimeTicks",
        )
        return [t for t in body.get("Items", []) if t.get("MediaType") == "Audio"]

    def _get_full_item(self, item_id: str) -> Dict[str, Any]:
        """Fetch a single item with the fields we need for payload building."""
        body = self._get(
            "/Items",
            ids=item_id,
            Fields="IndexNumber,RunTimeTicks",
        )
        items = body.get("Items", [])
        return items[0] if items else {}

    def stream_url(self, item_id: str) -> str:
        """Build an MP3 streaming URL for Yoto to call."""
        return (
            f"{self.url}/Audio/{item_id}/stream.mp3"
            f"?api_key={self.api_key}"
            f"&audioCodec=mp3&audioBitRate=128000"
        )