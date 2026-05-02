#!/usr/bin/env python3
"""
duckdns_update — keep your DuckDNS subdomain pointing at your home IP.

DuckDNS auto-detects your IP from the request, so we don't need to look it up.
This script is meant to be run on a schedule (every 5 minutes is fine).

First run: prompts for your DuckDNS subdomain and token, saves them.
Subsequent runs: silent on success, exits non-zero on failure (so the
scheduler can flag it).

Usage:
  duckdns_update.py                   Update once
  duckdns_update.py --setup           Force re-prompt for config
  duckdns_update.py --status          Show current config (token redacted)
"""

import logging
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

from scripts.logging_setup import configure as _configure_logging

log = logging.getLogger(__name__)


# ---------- Config ----------

def config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "duckdns_update"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "duckdns_update"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "duckdns_update"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    p = config_path()
    return json.loads(p.read_text()) if p.exists() else {}


def save_config(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2))
    try:
        p.chmod(0o600)
    except Exception:
        pass


def first_run_setup() -> dict:
    print("First-run setup. This is a one-time thing.\n")
    print("Get these from https://www.duckdns.org after signing in.\n")

    domain = input("DuckDNS subdomain (just the part before .duckdns.org): ").strip()
    if not domain:
        print("Subdomain is required.", file=sys.stderr)
        sys.exit(1)
    domain = domain.replace(".duckdns.org", "")  # forgive accidental full domain

    token = input("DuckDNS token: ").strip()
    if not token:
        print("Token is required.", file=sys.stderr)
        sys.exit(1)

    cfg = {"domain": domain, "token": token}
    save_config(cfg)
    print(f"\n✓ Saved config to {config_path()}")
    return cfg


# ---------- Update ----------

def update(cfg: dict) -> bool:
    """Call DuckDNS update endpoint. Returns True on success."""
    url = (
        f"https://www.duckdns.org/update"
        f"?domains={cfg['domain']}"
        f"&token={cfg['token']}"
        f"&ip="  # blank = let DuckDNS auto-detect
    )
    log.debug("updating: %s.duckdns.org", cfg["domain"])
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read().decode().strip()
    except urllib.error.URLError as e:
        log.debug("network error: %s", e.reason)
        print(f"Network error: {e.reason}", file=sys.stderr)
        return False
    except TimeoutError:
        log.debug("request timed out")
        print("Request timed out", file=sys.stderr)
        return False

    # DuckDNS responds with literally "OK" or "KO"
    log.debug("response: %r", body)
    if body == "OK":
        return True
    print(f"DuckDNS rejected the update (response: {body!r})", file=sys.stderr)
    print("Check that your subdomain and token are correct.", file=sys.stderr)
    return False


# ---------- Commands ----------

def cmd_status(cfg: dict) -> None:
    if not cfg:
        print("Not configured. Run with --setup or just run normally.")
        sys.exit(1)
    print(f"Config file: {config_path()}")
    print(f"Domain:      {cfg.get('domain', '?')}.duckdns.org")
    token = cfg.get("token", "")
    print(f"Token:       {token[:4]}…{token[-4:]}" if len(token) > 8 else "Token:       (set)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update a DuckDNS subdomain with this machine's public IP.",
    )
    parser.add_argument("--setup", action="store_true",
                        help="Re-run first-run setup (overwrites existing config)")
    parser.add_argument("--status", action="store_true",
                        help="Show current config (token redacted)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show debug logging")
    args = parser.parse_args()
    _configure_logging(verbose=args.verbose)

    if args.setup:
        first_run_setup()
        return

    cfg = load_config()

    if args.status:
        cmd_status(cfg)
        return

    if not cfg:
        cfg = first_run_setup()

    if not update(cfg):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)