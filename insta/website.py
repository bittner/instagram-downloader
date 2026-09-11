# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the HTML pages of the static website in site/.

Each site/USERNAME/ folder holds the downloaded photos and videos and an index.json; this
adds one page per account with all its posts, newest first, plus an overview page, and
copies the stylesheet and script from the package's static folder next to them. An
optional profile.json per account adds an "About" text and topic filters. The folder
is a self-contained static site that can be opened locally or deployed as is.
"""

import html
import importlib.metadata
import importlib.resources
import json
import re
import shutil
from pathlib import Path

from insta.topics import classify, compile_topics, hashtag_topics, load_profile

ROOT = Path.cwd()
SITE = ROOT / "site"
STATIC = importlib.resources.files("insta") / "static"
ASSETS = ("site.css", "site.js")
REPOSITORY = "https://github.com/bittner/instagram-offline"


def build(*, quiet: bool = False) -> None:
    """Generate the overview page and one page per account found in site/."""
    SITE.mkdir(exist_ok=True)
    for asset in ASSETS:
        with importlib.resources.as_file(STATIC / asset) as source:
            shutil.copyfile(source, SITE / asset)
    accounts = []
    for account in sorted(p for p in SITE.iterdir() if (p / "index.json").exists()):
        index = json.loads((account / "index.json").read_text())
        profile = load_profile(account)
        header = load_header(account)
        videos = [(c, e) for c, e in index.items() if e["files"]]
        if not profile["topics"]:
            profile["topics"] = hashtag_topics([e["caption"] for _, e in videos])
        if not profile["about"]:
            profile["about"] = header.get("biography", "")
        compiled = compile_topics(profile["topics"])
        posts = [(c, e, classify(e["caption"], compiled)) for c, e in videos]
        posts.sort(key=lambda p: p[1]["taken_at"], reverse=True)
        counts = {t["id"]: sum(1 for p in posts if t["id"] in p[2]) for t in profile["topics"]}
        accounts.append((account.name, len(posts), profile, counts, header))
        write_account_page(account.name, posts, profile, counts)
    write_overview(accounts)
    if not quiet:
        print(f"site: {len(accounts)} accounts -> {SITE / 'index.html'}")


def post_type(files: list[str]) -> str:
    """Classify a post by its files: carousel, video or photo."""
    if len(files) > 1:
        return "carousel"
    return "video" if files and files[0].endswith(".mp4") else "photo"


TYPES = (("all", "All"), ("photo", "Photos"), ("video", "Videos"), ("carousel", "Carousels"))


def medium(filename: str) -> str:
    """The HTML element showing one media file: a video player or an image."""
    if filename.endswith(".mp4"):
        return f'<video controls preload="metadata" src="{html.escape(filename)}"></video>'
    return f'<img src="{html.escape(filename)}" loading="lazy" draggable="false" alt="">'


def write_account_page(name: str, posts: list, profile: dict, counts: dict) -> None:
    """Write the page of one account with its video cards and topic filter chips."""
    names = {t["id"]: t["name"] for t in profile["topics"]}
    cards = []
    for code, e, topics in posts:
        videos = "".join(medium(f) for f in e["files"])
        if len(e["files"]) > 1:
            videos = (
                f'<div class="slides"><div class="track">{videos}</div>'
                f'<button class="prev" aria-label="previous">&lsaquo;</button>'
                f'<button class="next" aria-label="next">&rsaquo;</button>'
                f'<span class="count">1 / {len(e["files"])}</span></div>'
            )
        tags = "".join(f"<span>{html.escape(names[t])}</span>" for t in topics)
        cards.append(
            f'<div class="card" data-topics="{" ".join(topics)}" data-type="{post_type(e["files"])}">'
            f'{videos}<div class="meta">'
            f'<div class="when"><time>{e["date"]}</time> · <a href="https://www.instagram.com/p/{code}/">instagram</a></div>'
            f'<p>{linkify(e["caption"])}</p><div class="tags">{tags}</div></div></div>'
        )
    counts_by_type = {t: sum(1 for _, e, _ in posts if post_type(e["files"]) == t) for t, _ in TYPES}
    counts_by_type["all"] = len(posts)
    types = "".join(f'<button data-type="{t}">{label} · {counts_by_type[t]}</button>' for t, label in TYPES)
    chips = ""
    if profile["topics"]:
        chips = (
            f'<div class="chips"><button data-topic="all">All · {len(posts)}</button>'
            + "".join(
                f'<button data-topic="{t["id"]}">{html.escape(t["name"])} · {counts[t["id"]]}</button>'
                for t in profile["topics"]
            )
            + "</div>"
        )
    page(
        SITE / name / "index.html",
        f"@{name}",
        f'<header><div class="bar"><a href="../index.html">← all accounts</a> · <b>@{name}</b> · '
        f'{len(posts)} posts<span class="types">{types}</span></div>{chips}</header>'
        f'<main><div class="grid">{"".join(cards)}</div></main>',
        depth=1,
    )


LINKS = re.compile(r"(https?://[^\s<]+[^\s<.,;:!?)])|(?<!\w)@([\w.]+\w)|(?<!\w)#(\w+)")


def linkify(text: str) -> str:
    """Escape text for HTML and turn URLs, @mentions and #hashtags into links, as Instagram does."""

    def link(m: re.Match) -> str:
        url, user, tag = m.groups()
        if url:
            return f'<a href="{url}">{url}</a>'
        if user:
            return f'<a href="https://www.instagram.com/{user}/">@{user}</a>'
        return f'<a href="https://www.instagram.com/explore/tags/{tag}/">#{tag}</a>'

    return LINKS.sub(link, html.escape(text, quote=False))


def load_header(account_dir: Path) -> dict:
    """Read the captured profile header (account.json), or an empty dict if there is none."""
    f = account_dir / "account.json"
    return json.loads(f.read_text()) if f.exists() else {}


def header_line(header: dict) -> str:
    """Format the short form of a profile header for the account row: name and follower count."""
    parts = (
        [f'<span class="name">{html.escape(header["full_name"])}</span>'] if header.get("full_name") else []
    )
    if header.get("followers") is not None:
        parts.append(f"{header['followers']:,} followers")
    return " · ".join(parts)


def header_facts(header: dict) -> str:
    """Format the remaining profile facts for the expandable section: category, counts, links."""
    parts = [html.escape(header["category"])] if header.get("category") else []
    parts += [f"{header[k]:,} {k}" for k in ("posts", "following") if header.get(k) is not None]
    parts += [
        f'<a href="{html.escape(u)}">{html.escape(u.removeprefix("https://").rstrip("/"))}</a>'
        for u in header.get("links", [])
    ]
    if header.get("captured"):
        parts.append(f"captured {header['captured']}")
    return " · ".join(parts)


def write_overview(accounts: list) -> None:
    """Write the overview page listing all accounts with their About box."""
    boxes = []
    for name, n, profile, counts, header in accounts:
        about = ""
        if line := header_line(header):
            about = f'<span class="header">{line}</span>'
        if profile["about"]:
            topics = "".join(
                f'<a href="{name}/index.html#{t["id"]}">{html.escape(t["name"])} · {counts[t["id"]]}</a>'
                for t in profile["topics"]
            )
            about += (
                f"<details><summary>About @{name}</summary><p>{linkify(profile['about'])}</p>"
                f'<p class="facts">{header_facts(header)}</p><div class="topics">{topics}</div></details>'
            )
        boxes.append(
            f'<div class="account"><a href="{name}/index.html"><b>@{name}</b> · {n} posts</a>{about}</div>'
        )
    page(
        SITE / "index.html",
        "Instagram archive",
        f'<header><div class="bar"><b>Instagram archive</b></div></header><main>{"".join(boxes)}</main>',
        credit=True,
    )


def version() -> str:
    """The installed version of the package, empty when it is not installed as a package."""
    try:
        return importlib.metadata.version("instagram-offline")
    except importlib.metadata.PackageNotFoundError:
        return ""


def footer() -> str:
    """The credit line at the end of every page, linking to the project."""
    return f'<footer>Generated by <a href="{REPOSITORY}">instagram-offline</a> {version()}</footer>'


def page(path: Path, title: str, body: str, *, credit: bool = False, depth: int = 0) -> None:
    """Write a complete HTML document linking the shared stylesheet and script.

    ``depth`` is how many folders below site/ the page lives, for the relative links.
    """
    up = "../" * depth
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title><link rel="stylesheet" href="{up}site.css"></head>'
        f'<body>{body}{footer() if credit else ""}<script src="{up}site.js"></script></body></html>'
    )
