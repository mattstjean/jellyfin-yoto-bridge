"""Yoto content + icon API client.

The actual /content endpoints + icon library fetch. Auth is handled by
YotoAuth (passed in), so this class only worries about API calls.
"""

import logging
import urllib.parse
from typing import Dict, Any, List, Tuple

from . import http
from .yoto_auth import YotoAuth, YOTO_API
from .pretty_output import warn, fail

log = logging.getLogger(__name__)


class Yoto:
    def __init__(self, auth: YotoAuth):
        self.auth = auth

    # ---------- Internal ----------

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.auth.access_token()}"}

    def _get(self, path: str, **params) -> Tuple[int, Dict[str, Any]]:
        url = f"{YOTO_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return http.request("GET", url, headers=self._headers())

    def _post(self, path: str, json_body: Any) -> Tuple[int, Dict[str, Any]]:
        return http.request(
            "POST", f"{YOTO_API}{path}",
            headers=self._headers(),
            json_body=json_body,
        )

    # ---------- Public ----------

    def list_cards(self) -> List[Dict[str, Any]]:
        log.debug("list_cards")
        s, r = self._get("/content/mine")
        if s != 200:
            fail(f"Couldn't fetch cards: {r}")
        # Response shape can be {"cards": [...]} or just [...]
        if isinstance(r, dict):
            cards = r.get("cards", [])
        else:
            cards = r if isinstance(r, list) else []
        log.debug("  → %d cards", len(cards))
        return cards

    def create_or_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        card_id = payload.get("cardId")
        log.debug("create_or_update: title=%r  cardId=%s", payload.get("title"), card_id)
        chapters = payload.get("content", {}).get("chapters", [])
        log.debug("  chapters: %d", len(chapters))
        s, r = self._post("/content", payload)
        if s != 200:
            msg = r.get("message") or r.get("error") or r
            fail(f"Yoto API error ({s}): {msg}")
        result_id = r.get("card", {}).get("cardId")
        log.debug("  → %d  cardId=%s", s, result_id)
        return r

    def get_public_icons(self) -> List[Dict[str, Any]]:
        log.debug("get_public_icons")
        s, r = self._get("/media/displayIcons/user/yoto")
        if s != 200:
            warn("Couldn't fetch Yoto icon library; chapters won't have icons.")
            return []
        icons = r.get("displayIcons", [])
        log.debug("  → %d icons", len(icons))
        return icons