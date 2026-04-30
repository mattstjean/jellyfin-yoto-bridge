"""Lightweight HTTP wrapper around urllib.

Used by both Jellyfin and Yoto clients. Returns (status_code, parsed_body)
where body is a dict (parsed JSON or {"error": str}).
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Tuple, Dict, Any

from scripts.bridge.pretty_output import info


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

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            # Might be JSON, but might be empty (if testing connectivity, or might be an empty error page, or might be an html page if testing connectivity to a non-API endpoint), so try to parse but fall back to raw text.
            try:
                return r.status, json.loads(body) if body else {}
            except Exception:
                return r.status, {"error": body[:500]}  # Don't include more than 500 chars of an HTML error page
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body) if body else {}
        except Exception:
            return e.code, {"error": body[:500]}
    except urllib.error.URLError as e:
        return 0, {"error": f"Network error: {e.reason}"}
    except TimeoutError:
        return 0, {"error": "Request timed out"}