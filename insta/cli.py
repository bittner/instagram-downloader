"""Command line interface: ``uv run insta USERNAME [USERNAME ...]``."""
import argparse

from insta import download, website


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="insta",
        description="Download all videos and reels of Instagram accounts and build a local site.")
    ap.add_argument("usernames", nargs="*", metavar="USERNAME", help="Instagram account(s) to archive")
    ap.add_argument("--full", action="store_true", help="scan the whole profile, not just until known posts")
    ap.add_argument("--max", type=int, default=None, help="stop after N posts (for testing)")
    ap.add_argument("--site-only", action="store_true", help="only rebuild the HTML pages in site/")
    args = ap.parse_args()
    if not args.site_only:
        if not args.usernames:
            ap.error("USERNAME is required unless --site-only is given")
        download.archive_all(args.usernames, full=args.full, limit=args.max)
    website.build()
    return 0
