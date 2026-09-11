# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Command line interface: ``uv run insta USERNAME [USERNAME ...]``."""

import argparse
import sys
import time
from collections.abc import Callable

from insta import download, website

REBUILD_INTERVAL = 30  # seconds between site rebuilds while downloading


def main() -> int:
    """Parse the command line, archive the accounts and rebuild the site."""
    ap = argparse.ArgumentParser(
        description="Download all videos and reels of Instagram accounts and build a local site.",
    )
    ap.add_argument("usernames", nargs="*", metavar="USERNAME", help="Instagram account(s) to archive")
    ap.add_argument("--full", action="store_true", help="scan the whole profile, not just until known posts")
    ap.add_argument("--max", type=int, default=None, help="stop after N posts (for testing)")
    ap.add_argument("--site-only", action="store_true", help="only rebuild the HTML pages in site/")
    ap.add_argument(
        "--browser",
        metavar="EXECUTABLE",
        help="Chromium-based browser executable to use; default: $BROWSER if it is Chromium-based, "
        "otherwise the first of "
        + ", ".join(download.BROWSER_NAMES)
        + " found on the PATH, then Nix, then Playwright's own Chromium",
    )
    args = ap.parse_args()
    status = 0
    if not args.site_only:
        if not args.usernames:
            ap.error("USERNAME is required unless --site-only is given")
        try:
            download.archive_all(
                args.usernames,
                full=args.full,
                limit=args.max,
                browser=args.browser,
                on_progress=throttled(lambda: website.build(quiet=True), REBUILD_INTERVAL),
            )
        except KeyboardInterrupt:
            print("\nInterrupted; the posts archived so far are kept, rerun to resume.", file=sys.stderr)
            status = 130
    website.build()
    return status


def throttled(action: Callable[[], None], interval: float) -> Callable[[], None]:
    """Return a callable that runs the action at most once per interval of seconds."""
    last = float("-inf")  # the first call always runs

    def run() -> None:
        nonlocal last
        if time.monotonic() - last >= interval:
            action()
            last = time.monotonic()

    return run
