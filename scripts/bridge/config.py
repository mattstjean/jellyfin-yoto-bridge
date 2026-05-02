"""Config file management.

Stores config at the platform-appropriate location:
  macOS:   ~/Library/Application Support/yoto-create-playlist/config.json
  Windows: %APPDATA%/yoto-create-playlist/config.json
  Linux:   $XDG_CONFIG_HOME/yoto-create-playlist/config.json (or ~/.config/...)

Migrates from the legacy ~/.yoto-create-playlist.json if present.
"""

from . import http
import logging
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

from .pretty_output import info, ok, fail

log = logging.getLogger(__name__)

LEGACY_CONFIG = Path.home() / ".yoto-create-playlist.json"


def config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "yoto-create-playlist"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "yoto-create-playlist"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "yoto-create-playlist"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> Dict[str, Any]:
    """Load config, migrating from legacy location if needed."""
    path = config_path()
    if path.exists():
        log.debug("loading config: %s", path)
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            fail(f"Invalid JSON in config file: {path}. Please fix or delete this file to continue.")

    if LEGACY_CONFIG.exists():
        log.debug("migrating legacy config: %s → %s", LEGACY_CONFIG, path)
        info(f"Migrating config from {LEGACY_CONFIG} to {path}")
        cfg = json.loads(LEGACY_CONFIG.read_text())
        save(cfg)
        try:
            LEGACY_CONFIG.unlink()
        except Exception:
            pass
        return cfg

    log.debug("no config found at %s", path)
    return {}


def save(cfg: Dict[str, Any]) -> None:
    path = config_path()
    log.debug("saving config: %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))
    try:
        path.chmod(0o600)
    except Exception:
        pass  # Windows: chmod is mostly a no-op


def first_run_setup() -> Dict[str, Any]:
    info("Welcome to the Yoto Create Playlist setup!")
    info("To create Yoto cards from your Jellyfin audiobooks, we need to connect to both your Jellyfin server and the Yoto Dashboard. Let's set that up now.\n")
    info("You can find all of this information in the Jellyfin Dashboard and the Yoto Dashboard, so have those open in your browser to copy and paste from.\n")
    info("Don't worry, this is a one-time setup. After this, you can just run the command to create playlists without any prompts.\n")

    # Check if we have a partially completed config from a previous failed setup
    partial_cfg = load()
    info("1. Jellyfin server URL")
    info("   Example: https://your-name.duckdns.org")
    if partial_cfg.get("jellyfin_url"):
        info(f"   (found existing URL in config: {partial_cfg['jellyfin_url']})")
    jf_url = input("   Jellyfin URL: ").strip() or partial_cfg.get("jellyfin_url", "")

    if not test_input_url(jf_url):
        # If the URL test fails, we will likely also fail to get a valid API key, so we should stop here and let the user fix the URL witout going through the rest of the setup.
        fail("Please fix the URL and run the setup again.")
        # Let them try entering it again incase they just made a mistake, but if they keep failing we'll exit after 3 attempts to avoid an infinite loop.
        attempts = 1
        while attempts < 3:
            jf_url = input("   Jellyfin URL: ").strip() or partial_cfg.get("jellyfin_url", "")
            if test_input_url(jf_url):
                break
            fail("URL test failed. Please check the URL and your network connection, then try again.")
            attempts += 1
        else:
            fail("Too many failed attempts. Please fix the URL and run the setup again.")
            sys.exit(1)

    info("\n2. Jellyfin API key")
    info("   In Jellyfin: Dashboard \u2192 API Keys \u2192 New API Key")
    if partial_cfg.get("jellyfin_api_key"):
        info(f"   (found existing API key in config: {partial_cfg['jellyfin_api_key'][:4]}...{partial_cfg['jellyfin_api_key'][-4:]})")
    jf_key = input("   API key: ").strip() or partial_cfg.get("jellyfin_api_key", "")

    if not test_input_api_key(jf_key, jf_url):
        fail("API key test failed. Please check the API key and your Jellyfin URL, then run the setup again.")
        # Let them try entering it again incase they just made a mistake, but if they keep failing we'll exit after 3 attempts to avoid an infinite loop.
        attempts = 1
        while attempts < 3:
            jf_key = input("   API key: ").strip() or partial_cfg.get("jellyfin_api_key", "")
            if test_input_api_key(jf_key, jf_url):
                break
            fail("API key test failed. Please check the API key and your Jellyfin URL, then try again.")
            attempts += 1
        else:
            fail("Too many failed attempts. Please fix the API key and run the setup again.")
            sys.exit(1)

    info("\n3. Yoto Client ID")
    info("   Get one at https://dashboard.yoto.dev (create a Public Client)")
    if partial_cfg.get("yoto_client_id"):
        info(f"   (found existing Client ID in config: {partial_cfg['yoto_client_id'][:4]}...{partial_cfg['yoto_client_id'][-4:]})")
    yoto_id = input("   Client ID: ").strip() or partial_cfg.get("yoto_client_id", "")

    if not test_input_yoto_client_id(yoto_id):
        fail("Yoto Client ID test failed. Please check the Client ID and your network connection, then run the setup again.")
        # Let them try entering it again incase they just made a mistake, but if they keep failing we'll exit after 3 attempts to avoid an infinite loop.
        attempts = 1
        while attempts < 3:
            yoto_id = input("   Client ID: ").strip() or partial_cfg.get("yoto_client_id", "")
            if test_input_yoto_client_id(yoto_id):
                break
            fail("Yoto Client ID test failed. Please check the Client ID and your network connection, then try again.")
            attempts += 1
        else:
            fail("Too many failed attempts. Please fix the Client ID and run the setup again.")
            sys.exit(1)

    cfg = {
        "jellyfin_url": jf_url,
        "jellyfin_api_key": jf_key,
        "yoto_client_id": yoto_id,
    }
    
    save(cfg)
    ok(f"Saved config to {config_path()}\n")
    return cfg

def load_or_setup() -> Dict[str, Any]:
    """Load config, or run first-run setup if none exists."""
    cfg = load()
    if not cfg.get("jellyfin_url"):
        cfg = first_run_setup()
    return cfg


def test_input_url(url: str) -> bool:
    """Test if the URL is valid and reachable."""
    if not url.startswith("http://") and not url.startswith("https://"):
        fail("URL must start with http:// or https://")
        return False
    try:
        info(f"Testing URL reachability: {url} ...")
        status, body = http.request("GET", url)
        info(f"Received status code {status} from {url}")
        if status == 200:
            info("Successfully reached the URL.")
            return True
        else:
            fail(f"URL is reachable but returned status code {status}")
            return False
    except Exception as e:
        fail(f"Error reaching URL: {e}")
        return False
    
def test_input_api_key(api_key: str, url: str) -> bool:
    """Test if the API key is valid by making an authenticated request to the Jellyfin server."""
    try:
        status, _ = http.request(
            "GET",
            f"{url}/System/Info",
            headers={"X-Emby-Token": api_key},
        )
        if status == 200:
            info("Successfully connected to Jellyfin server with API key.")
            return True
        elif status == 401:
            fail("Unauthorized: Jellyfin rejected the API key. Please check the key and try again.")
            return False
        else:
            fail(f"Error connecting to Jellyfin server with API key (status code: {status}). Please check the key and try again.")
            return False
    except Exception as e:
        fail(f"Error connecting to Jellyfin server: {e}. Please check the API key and your network connection, then try again.")
        return False 
    
def test_input_yoto_client_id(client_id: str) -> bool:
    """Test if the Yoto Client ID is valid by making an authenticated request to the Yoto Dashboard API leveraging yoto_auth."""
    from .yoto_auth import YotoAuth
    auth = YotoAuth({"yoto_client_id": client_id}, save_cfg=lambda x: None)
    try:
        token = auth.access_token()
        if token:
            info("Successfully authenticated with Yoto Dashboard API using the Client ID.")
            return True
        else:
            fail("Failed to obtain access token with the provided Yoto Client ID. Please check the Client ID and try again.")
            return False
    except Exception as e:
        fail(f"Error authenticating with Yoto Dashboard API: {e}. Please check the Client ID and your network connection, then try again.")
        return False