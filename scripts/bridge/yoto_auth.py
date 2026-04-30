"""Yoto OAuth device-code flow.

Manages the access/refresh token lifecycle. The TokenStore protocol is just
"something that has cfg and saves it" — typically the config module.
"""

import time
from typing import Dict, Any, Callable

from . import http
from .pretty_output import info, ok, warn, fail

YOTO_AUTH = "https://login.yotoplay.com"
YOTO_API = "https://api.yotoplay.com"
YOTO_SCOPES = "user:content:manage user:icons:manage offline_access"


class YotoAuth:
    """
    Handles getting and refreshing Yoto access tokens.

    Reads the client_id and existing tokens from the cfg dict, writes any new
    tokens back via save_cfg(cfg).
    """

    def __init__(self, cfg: Dict[str, Any], save_cfg: Callable[[Dict[str, Any]], None]):
        self.cfg = cfg
        self.save_cfg = save_cfg

    # ---------- Public ----------

    def access_token(self) -> str:
        """Return a valid access token, refreshing or re-authorizing as needed."""
        if "yoto_access_token" not in self.cfg:
            self._device_login()
        elif time.time() > self.cfg.get("yoto_token_expires", 0):
            self._refresh()
        return self.cfg["yoto_access_token"]

    # ---------- Internal ----------

    def _device_login(self) -> None:
        info("Authorizing with Yoto\u2026")
        s, r = http.request("POST", f"{YOTO_AUTH}/oauth/device/code", form={
            "client_id": self.cfg["yoto_client_id"],
            "scope": YOTO_SCOPES,
            "audience": YOTO_API,
        })
        if s != 200:
            fail(f"Device code request failed: {r.get('error_description') or r.get('error') or r}")

        info("")
        info(f"  Visit:  {r['verification_uri_complete']}")
        info(f"  Code:   {r['user_code']}")
        info("")
        info("Waiting for you to approve in the browser\u2026")

        interval = r.get("interval", 5)
        deadline = time.time() + r.get("expires_in", 300)
        device_code = r["device_code"]

        while time.time() < deadline:
            s2, r2 = http.request("POST", f"{YOTO_AUTH}/oauth/token", form={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": self.cfg["yoto_client_id"],
                "audience": YOTO_API,
            })
            if s2 == 0:
                warn("Network error while polling for authorization, retrying\u2026")
                continue
            if s2 == 200:
                self._store_tokens(r2)
                ok("Authorized.\n")
                return
            err = r2.get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            if err == "expired_token":
                fail("Authorization timed out. Run the command again.")
            if err == "access_denied":
                fail("Authorization denied. Run the command again to retry.")
            fail(f"Auth failed: {r2.get('error_description') or err or r2}")
        fail("Authorization timed out. Run the command again.")
        time.sleep(interval)

    def _refresh(self) -> None:
        s, r = http.request("POST", f"{YOTO_AUTH}/oauth/token", form={
            "grant_type": "refresh_token",
            "client_id": self.cfg["yoto_client_id"],
            "refresh_token": self.cfg["yoto_refresh_token"],
        })
        if s != 200:
            warn("Couldn't refresh token, re-authorizing.")
            self._device_login()
            return
        self._store_tokens(r)

    def _store_tokens(self, r: Dict[str, Any]) -> None:
        self.cfg["yoto_access_token"] = r["access_token"]
        self.cfg["yoto_refresh_token"] = r.get(
            "refresh_token", self.cfg.get("yoto_refresh_token")
        )
        self.cfg["yoto_token_expires"] = (
            int(time.time()) + r.get("expires_in", 86400) - 60
        )
        self.save_cfg(self.cfg)