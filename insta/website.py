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

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from insta.topics import classify, compile_topics, hashtag_topics, load_profile

ROOT = Path.cwd()
SITE = ROOT / "site"
STATIC = importlib.resources.files("insta") / "static"
ASSETS = ("site.css", "site.js", "favicon.svg")
TEMPLATES = Environment(
    loader=PackageLoader("insta", "templates"),
    autoescape=select_autoescape(default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)
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


def write_account_page(name: str, posts: list, profile: dict, counts: dict) -> None:
    """Write the page of one account with its cards, type buttons and topic filter chips."""
    names = {t["id"]: t["name"] for t in profile["topics"]}
    cards = [
        {
            "code": code,
            "date": e["date"],
            "files": e["files"],
            "type": post_type(e["files"]),
            "topics": topics,
            "tags": [names[t] for t in topics],
            "caption": linkify(e["caption"]),
        }
        for code, e, topics in posts
    ]
    by_type = {t: sum(1 for card in cards if card["type"] == t) for t, _ in TYPES}
    by_type["all"] = len(cards)
    render(
        "account.html",
        SITE / name / "index.html",
        title=f"@{name}",
        up="../",
        name=name,
        posts=cards,
        types=[(t, label, by_type[t]) for t, label in TYPES],
        topics=[{"id": t["id"], "name": t["name"], "count": counts[t["id"]]} for t in profile["topics"]],
    )


LINKS = re.compile(r"(https?://[^\s<]+[^\s<.,;:!?)])|(?<!\w)@([\w.]+\w)|(?<!\w)#(\w+)")


def linkify(text: str) -> Markup:
    """Escape text for HTML and turn URLs, @mentions and #hashtags into links, as Instagram does."""

    def link(m: re.Match) -> str:
        url, user, tag = m.groups()
        if url:
            return f'<a href="{url}">{url}</a>'
        if user:
            return f'<a href="https://www.instagram.com/{user}/">@{user}</a>'
        return f'<a href="https://www.instagram.com/explore/tags/{tag}/">#{tag}</a>'

    return Markup(LINKS.sub(link, html.escape(text, quote=False)))


def load_header(account_dir: Path) -> dict:
    """Read the captured profile header (account.json), or an empty dict if there is none."""
    f = account_dir / "account.json"
    return json.loads(f.read_text()) if f.exists() else {}


def header_line(header: dict) -> Markup:
    """Format the short form of a profile header for the account row: name and follower count."""
    parts = (
        [f'<span class="name">{html.escape(header["full_name"])}</span>'] if header.get("full_name") else []
    )
    if header.get("followers") is not None:
        parts.append(f"{header['followers']:,} followers")
    return Markup(" · ".join(parts))


def header_facts(header: dict) -> Markup:
    """Format the remaining profile facts for the expandable section: category, counts, links."""
    parts = [html.escape(header["category"])] if header.get("category") else []
    if header.get("posts") is not None:
        parts.append(f"{header['posts']:,} post{'s' if header['posts'] != 1 else ''}")
    if header.get("following") is not None:
        parts.append(f"{header['following']:,} following")
    parts += [
        f'<a href="{html.escape(u)}">{html.escape(u.removeprefix("https://").rstrip("/"))}</a>'
        for u in header.get("links", [])
    ]
    if header.get("captured"):
        parts.append(f"captured {header['captured']}")
    return Markup(" · ".join(parts))


def write_overview(accounts: list) -> None:
    """Write the overview page listing all accounts with their About box."""
    rows = [
        {
            "name": name,
            "posts": n,
            "header_line": header_line(header),
            "about": linkify(profile["about"]) if profile["about"] else "",
            "facts": header_facts(header),
            "topics": [
                {"id": t["id"], "name": t["name"], "count": counts[t["id"]]} for t in profile["topics"]
            ],
        }
        for name, n, profile, counts, header in accounts
    ]
    render("overview.html", SITE / "index.html", title="Instagram archive", up="", accounts=rows, credit=True)


def version() -> str:
    """The installed version of the package, empty when it is not installed as a package."""
    try:
        return importlib.metadata.version("instagram-offline")
    except importlib.metadata.PackageNotFoundError:
        return ""


def render(template: str, path: Path, **context) -> None:
    """Render a page template into the site, with the credit footer if ``credit`` is set."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = TEMPLATES.get_template(template).render(repository=REPOSITORY, version=version(), **context)
    path.write_text(text)
