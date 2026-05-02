"""Shared logging configuration for all scripts in this project.

Call configure() once at startup. Every other module just does:

    import logging
    log = logging.getLogger(__name__)

Toggle via --verbose flag, VERBOSE=1, or LOG_LEVEL=debug env var.
"""

import logging
import os
import sys

_RESET  = "\033[0m"
_GREY   = "\033[90m"
_CYAN   = "\033[36m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BOLD   = "\033[1m"

_LABELS = {
    logging.DEBUG:    ("debug",    _GREY),
    logging.INFO:     ("info",     _CYAN),
    logging.WARNING:  ("warn",     _YELLOW),
    logging.ERROR:    ("error",    _RED),
    logging.CRITICAL: ("critical", _BOLD + _RED),
}


class _Formatter(logging.Formatter):
    def __init__(self, color: bool) -> None:
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        label, clr = _LABELS.get(record.levelno, (record.levelname.lower(), ""))
        # Trim the "scripts." prefix so names stay readable.
        name = record.name.removeprefix("scripts.")
        msg  = record.getMessage()
        if self.color:
            return f"{clr}[{label}]{_RESET} {_GREY}{name}{_RESET}: {msg}"
        return f"[{label}] {name}: {msg}"


def configure(verbose: bool = False) -> None:
    """Set up the root logger. Call once at program startup.

    Priority order for level:
      1. verbose=True argument
      2. VERBOSE=1 env var
      3. LOG_LEVEL=<name> env var  (e.g. LOG_LEVEL=debug)
      4. Default: WARNING (silent on normal runs)
    """
    env_verbose = os.environ.get("VERBOSE", "").strip().lower() in ("1", "true", "yes")
    env_level   = os.environ.get("LOG_LEVEL", "").strip().upper()

    if verbose or env_verbose:
        level = logging.DEBUG
    elif env_level and hasattr(logging, env_level):
        level = getattr(logging, env_level)
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(_Formatter(color=sys.stderr.isatty()))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)