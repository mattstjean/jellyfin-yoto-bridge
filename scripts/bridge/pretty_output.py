"""Tiny pretty-print helpers used everywhere."""

import sys
from typing import NoReturn


def info(msg: str) -> None:
    print(msg)


def ok(msg: str) -> None:
    print(f"\u2713 {msg}")


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)


def fail(msg: str, code: int = 1) -> None:
    print(f"\u2717 {msg}", file=sys.stderr)

