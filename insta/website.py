"""Build the HTML pages of the static website in site/.

Each site/USERNAME/ folder holds the downloaded videos and an index.json; this adds
one page per account with all its videos, newest first, plus an overview page. The
folder is a self-contained static site that can be opened locally or deployed as is.
"""
import html
import json
from pathlib import Path

ROOT = Path.cwd()
SITE = ROOT / "site"

CSS = """
body{font-family:system-ui,sans-serif;margin:0;background:#fafafa;color:#222}
header{padding:1rem 2rem;background:#fff;border-bottom:1px solid #ddd}
header a{color:inherit;text-decoration:none}
main{padding:1rem 2rem;max-width:1400px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:1.5rem}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;overflow:hidden}
.card video{width:100%;aspect-ratio:9/16;background:#000;display:block}
.card .meta{padding:.75rem 1rem}
.card time{color:#666;font-size:.85rem}
.card p{white-space:pre-wrap;margin:.5rem 0 0;font-size:.9rem;max-height:9em;overflow:auto}
.accounts a{display:block;padding:1rem;margin:.5rem 0;background:#fff;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:inherit}
"""


def build() -> None:
    SITE.mkdir(exist_ok=True)
    accounts = []
    for account in sorted(p for p in SITE.iterdir() if (p / "index.json").exists()):
        index = json.loads((account / "index.json").read_text())
        posts = sorted((c, e) for c, e in index.items() if e["files"])
        posts.sort(key=lambda ce: ce[1]["taken_at"], reverse=True)
        accounts.append((account.name, len(posts)))
        write_account_page(account.name, posts)
    write_overview(accounts)
    print(f"site: {len(accounts)} accounts -> {SITE / 'index.html'}")


def write_account_page(name: str, posts: list) -> None:
    cards = []
    for code, e in posts:
        videos = "".join(
            f'<video controls preload="metadata" src="{html.escape(f)}"></video>' for f in e["files"])
        cards.append(
            f'<div class="card">{videos}<div class="meta">'
            f'<time>{e["date"]}</time> · <a href="https://www.instagram.com/p/{code}/">instagram</a>'
            f'<p>{html.escape(e["caption"])}</p></div></div>')
    page(SITE / name / "index.html", f"@{name}",
         f'<header><a href="../index.html">← all accounts</a> · <b>@{name}</b> · {len(posts)} videos</header>'
         f'<main><div class="grid">{"".join(cards)}</div></main>')


def write_overview(accounts: list) -> None:
    links = "".join(f'<a href="{n}/index.html"><b>@{n}</b> · {c} videos</a>' for n, c in accounts)
    page(SITE / "index.html", "Instagram archive",
         f'<header><b>Instagram archive</b></header><main class="accounts">{links}</main>')


def page(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                    f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>')

