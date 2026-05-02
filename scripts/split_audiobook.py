#!/usr/bin/env python3
"""
split-audiobook — split an M4B/MP3 audiobook into per-chapter files.

Reads chapter markers embedded in the file (most M4Bs have them) and produces
one MP3 per chapter, named so they sort correctly when uploaded to Jellyfin.

Requires ffmpeg and ffprobe on your PATH:
  macOS:    brew install ffmpeg
  Windows:  winget install Gyan.FFmpeg
  Linux:    apt install ffmpeg  (or your distro's equivalent)

Usage:
  split-audiobook.py path/to/book.m4b
  split-audiobook.py path/to/book.m4b --output ~/Audiobooks/Goblet
  split-audiobook.py path/to/book.m4b --bitrate 96k
  split-audiobook.py path/to/book.m4b --dry-run

Output filenames look like:
  01 - The Riddle House.mp3
  02 - The Scar.mp3
  ...

If the file has no chapter markers, the script tells you and exits — splitting
a chapterless audiobook is a different problem (you'd need to split by time,
which is rarely what you want).
"""

import logging
import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from scripts.logging_setup import configure as _configure_logging

log = logging.getLogger(__name__)


# ---------- Pretty output ----------

def info(msg: str) -> None:
    print(msg)

def ok(msg: str) -> None:
    print(f"\u2713 {msg}")

def fail(msg: str, code: int = 1):
    print(f"\u2717 {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- Dependency check ----------

def check_tools() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        fail(
            f"Missing required tool(s): {', '.join(missing)}\n"
            f"  Install ffmpeg:\n"
            f"    macOS:   brew install ffmpeg\n"
            f"    Windows: winget install Gyan.FFmpeg\n"
            f"    Linux:   apt install ffmpeg"
        )


# ---------- Chapter extraction ----------

def get_chapters(audio_path: Path) -> List[Dict[str, Any]]:
    """Use ffprobe to read chapter markers from the file."""
    log.debug("ffprobe: %s", audio_path)
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_chapters",
            str(audio_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        fail(f"ffprobe failed: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    chapters = data.get("chapters", [])
    log.debug("found %d chapter markers", len(chapters))
    return chapters


# ---------- Filename safety ----------

def sanitize(name: str) -> str:
    """Make a string safe to use as a filename on macOS, Windows, and Linux."""
    # Forbidden on Windows: < > : " / \ | ? *
    # Also strip control chars and trailing dots/spaces (Windows hates those).
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad or ord(c) < 32 else c for c in name)
    cleaned = cleaned.strip().rstrip(". ")
    return cleaned or "Untitled"


def chapter_title(chapter: Dict[str, Any], index: int) -> str:
    tags = chapter.get("tags", {}) or {}
    return tags.get("title") or f"Chapter {index}"


# ---------- Splitting ----------

def split_chapters(
    audio_path: Path,
    output_dir: Path,
    chapters: List[Dict[str, Any]],
    bitrate: str,
    dry_run: bool,
) -> None:
    width = max(2, len(str(len(chapters))))  # "01" or "001" if >99 chapters

    output_dir.mkdir(parents=True, exist_ok=True)

    for i, ch in enumerate(chapters, 1):
        start = ch["start_time"]
        end = ch["end_time"]
        title = chapter_title(ch, i)
        filename = f"{str(i).zfill(width)} - {sanitize(title)}.mp3"
        out_path = output_dir / filename

        if dry_run:
            duration = float(end) - float(start)
            mins = int(duration // 60)
            secs = int(duration % 60)
            log.debug("  [%s] %r  start=%s end=%s", filename, title, start, end)
            info(f"  [{i:>{width}}] {filename}  ({mins}:{secs:02d})")
            continue

        info(f"  [{i:>{width}}/{len(chapters)}] {filename}")

        # ffmpeg copies + re-encodes audio to MP3 at the target bitrate.
        # -ss before -i is fast seek; -to is end time; -vn drops video/cover art
        # in the output (we copy cover separately if needed).
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-i", str(audio_path),
            "-ss", str(start),
            "-to", str(end),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            "-metadata", f"title={title}",
            "-metadata", f"track={i}/{len(chapters)}",
            str(out_path),
        ]
        log.debug("ffmpeg: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"ffmpeg failed on chapter {i}:\n{result.stderr.strip()}")
        log.debug("  → wrote %s", out_path)


# ---------- Main ----------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a chaptered audiobook (M4B/MP3) into per-chapter MP3 files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic split (output goes to a folder next to the input file):
    %(prog)s ~/Downloads/goblet-of-fire.m4b

  Custom output folder:
    %(prog)s book.m4b --output ~/Audiobooks/Goblet

  Lower bitrate to save space (default is 128k):
    %(prog)s book.m4b --bitrate 96k

  Preview what would be done without writing anything:
    %(prog)s book.m4b --dry-run
""",
    )
    parser.add_argument("input", help="Path to the audiobook file (M4B, MP3, etc.)")
    parser.add_argument("--output", help="Output directory (default: <input-name>_chapters next to the input file)")
    parser.add_argument("--bitrate", default="128k",
                        help="MP3 bitrate, e.g. 96k, 128k, 192k (default: 128k)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be split without writing files")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show debug logging")
    args = parser.parse_args()
    _configure_logging(verbose=args.verbose)
    # Check for help flag manually since we want to show it even if the required tools are missing.
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Check for ffmpeg/ffprobe before doing any work, so we fail fast if they're missing.
    check_tools()

    audio_path = Path(args.input).expanduser().resolve()
    if not audio_path.exists():
        fail(f"File not found: {audio_path}")
    if not audio_path.is_file():
        fail(f"Not a file: {audio_path}")

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        output_dir = audio_path.parent / f"{audio_path.stem}_chapters"

    info(f"Input:   {audio_path}")
    info(f"Output:  {output_dir}")
    info(f"Bitrate: {args.bitrate}")
    info("")

    info("Reading chapter markers\u2026")
    chapters = get_chapters(audio_path)
    if not chapters:
        fail(
            "No chapter markers found in this file.\n"
            "  Splitting an audiobook without chapter markers requires deciding\n"
            "  where the splits go (by time? by silence?). That's outside what\n"
            "  this script does \u2014 try MP3DirectCut, mp3splt, or similar."
        )
    info(f"Found {len(chapters)} chapters.\n")

    split_chapters(audio_path, output_dir, chapters, args.bitrate, args.dry_run)

    info("")
    if args.dry_run:
        ok(f"Dry run complete. {len(chapters)} files would be written to {output_dir}")
    else:
        ok(f"Done. {len(chapters)} files written to {output_dir}")
        info(
            "\nNext: in Jellyfin, scan your library so the new folder appears,\n"
            "then run yoto-create.py to make a playlist from the chapters."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        info("\nInterrupted.")
        sys.exit(130)