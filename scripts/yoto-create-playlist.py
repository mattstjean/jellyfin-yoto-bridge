import sys
import os
import json
from pathlib import Path

# ---------- Constants ----------
 
YOTO_API = "https://api.yotoplay.com"
YOTO_AUTH = "https://login.yotoplay.com"
YOTO_SCOPES = "user:content:manage user:icons:manage offline_access"

# ---------- Pretty output ----------
 
def info(msg): print(msg)
def ok(msg): print(f"\u2713 {msg}")
def warn(msg): print(f"! {msg}", file=sys.stderr)
def fail(msg, code=1):
    print(f"\u2717 {msg}", file=sys.stderr)
    sys.exit(code)

# ---------- Cross-platform config path ----------
def config_dir() -> Path:
    """Return the right config directory for this OS."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "yoto-create"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "yoto-create"
    else:
        # Linux + everything else: XDG
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "yoto-create"
    
def config_path() -> Path:
    return config_dir() / "config.json"

# ---------- Config management ----------
 
def load_config() -> dict:
    path = config_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}

def save_config(cfg: dict):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))
    try:
        path.chmod(0o600)
    except Exception:
        pass  # Windows doesn't really do chmod