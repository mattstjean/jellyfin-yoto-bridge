"""Lightweight HTTP wrapper around urllib.

Used by both Jellyfin and Yoto clients. Returns (status_code, parsed_body)
where body is a dict (parsed JSON or {"error": str}).
"""

import json
import logging
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Tuple, Dict, Any

log = logging.getLogger(__name__)

_API_KEY_RE = re.compile(r"(api_key=)[^&]+")


def _redact(url: str) -> str:
    return _API_KEY_RE.sub(r"\1<hidden>", url)


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    form: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    timeout: int = 30,
) -> Tuple[int, Dict[str, Any]]:
    """Make an HTTP request. Never raises for HTTP errors — returns (0, ...) for network failures."""
    data = None
    headers = dict(headers or {})

    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    log.debug("%s %s", method, _redact(url))
    if json_body is not None:
        log.debug("  body: %s", json.dumps(json_body)[:200])

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            # Might be JSON, but might be empty (if testing connectivity, or might be an empty error page, or might be an html page if testing connectivity to a non-API endpoint), so try to parse but fall back to raw text.
            try:
                parsed = json.loads(body) if body else {}
                log.debug("  → %d  (%d bytes)", r.status, len(body))
                return r.status, parsed
            except Exception:
                log.debug("  → %d  (non-JSON body)", r.status)
                return r.status, {"error": body[:500]}  # Don't include more than 500 chars of an HTML error page
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log.debug("  → HTTP %d", e.code)
        try:
            return e.code, json.loads(body) if body else {}
        except Exception:
            return e.code, {"error": body[:500]}
    except urllib.error.URLError as e:
        log.debug("  → network error: %s", e.reason)
        return 0, {"error": f"Network error: {e.reason}"}
    except TimeoutError:
        log.debug("  → timeout")
        return 0, {"error": "Request timed out"}