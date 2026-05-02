"""CLI entry point.

Parses arguments and orchestrates the modules. All real work happens in
the client classes; this just wires them together.
"""

import sys
import json
import argparse

from scripts import logging_setup
from . import config
from .pretty_output import info, ok, fail
from .jellyfin import Jellyfin
from .yoto_auth import YotoAuth
from .yoto_api import Yoto
from .payload import build_payload, redact_payload_for_display


def _build_clients() -> tuple:
    """Return (cfg, jellyfin, yoto) ready to use."""
    cfg = config.load_or_setup()

    jf = Jellyfin(cfg["jellyfin_url"], cfg["jellyfin_api_key"])
    auth = YotoAuth(cfg, save_cfg=config.save)
    yoto = Yoto(auth)
    return cfg, jf, yoto


def cmd_create(args: argparse.Namespace) -> None:
    cfg, jf, yoto = _build_clients()

    book = jf.find_audiobook(args.search)
    info(f"\nBook:   {book['Name']}")

    tracks = jf.get_tracks(book)
    if not tracks:
        fail("No audio tracks found in this folder. Is the book split into chapter files?")
    info(f"Tracks: {len(tracks)}")

    icons = [] if args.dry_run else yoto.get_public_icons()
    payload = build_payload(
        book=book,
        tracks=tracks,
        icons=icons,
        stream_url_for=jf.stream_url,
        existing_card_id=args.update,
    )

    if args.dry_run:
        info("\n--- DRY RUN: would send the following to Yoto ---\n")
        print(json.dumps(redact_payload_for_display(payload), indent=2))
        return

    info("\nSending to Yoto\u2026")
    result = yoto.create_or_update(payload)
    card = result.get("card", {})
    ok(f"{'Updated' if args.update else 'Created'}: {card.get('title')}")
    info(f"  Card ID: {card.get('cardId')}")
    if not args.update:
        info("\nNext: open the Yoto app \u2192 Make Your Own \u2192 select this card "
             "\u2192 link to a physical card.")


def cmd_list(_args: argparse.Namespace) -> None:
    _, _, yoto = _build_clients()
    cards = yoto.list_cards()
    if not cards:
        info("No MYO cards yet.")
        return
    info(f"{'CARD ID':<28} TITLE")
    info("-" * 60)
    for c in cards:
        info(f"{c.get('cardId',''):<28} {c.get('title','')}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="yoto-create-playlist",
        description="Turn a Jellyfin audiobook into a Yoto MYO playlist.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Create a card for an audiobook:
    %(prog)s "goblet of fire"

  See what would be created without actually doing it:
    %(prog)s --dry-run "goblet of fire"

  List your existing cards:
    %(prog)s --list

  Update an existing card with the latest chapters from Jellyfin:
    %(prog)s --update CARD_ID "goblet of fire"
""",
    )
    parser.add_argument("search", nargs="*", help="Search term for the audiobook")
    parser.add_argument("--list", action="store_true", help="List existing MYO cards")
    parser.add_argument("--update", metavar="CARD_ID",
                        help="Update the given card instead of creating new")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be sent without posting")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show debug logging (API calls, responses, etc.)")

    args = parser.parse_args(argv)
    logging_setup.configure(verbose=args.verbose)
    args.search = " ".join(args.search) if args.search else ""

    try:
        if args.list:
            cmd_list(args)
        elif args.update:
            if not args.search:
                fail("--update needs a search term too.")
            cmd_create(args)
        elif args.search:
            cmd_create(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        info("\nInterrupted.")
        sys.exit(130)