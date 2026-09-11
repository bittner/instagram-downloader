# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the HTML pages of the static website in site/.

Each site/USERNAME/ folder holds the downloaded videos and an index.json; this adds
one page per account with all its videos, newest first, plus an overview page. An
optional profile.json per account adds an "About" text and topic filters. The folder
is a self-contained static site that can be opened locally or deployed as is.
"""

import html
import json
from pathlib import Path

from insta.topics import classify, compile_topics, load_profile

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
.slides{position:relative}
.slides video[hidden]{display:none}
.slides button{position:absolute;top:50%;transform:translateY(-50%);width:2.2rem;height:2.2rem;border:0;
 border-radius:50%;background:rgba(255,255,255,.85);color:#222;font-size:1.2rem;cursor:pointer}
.slides .prev{left:.5rem}.slides .next{right:.5rem}
.slides .count{position:absolute;top:.5rem;right:.5rem;background:rgba(0,0,0,.6);color:#fff;font-size:.75rem;
 padding:.15rem .5rem;border-radius:999px}
.card .meta{padding:.75rem 1rem}
.card time{color:#666;font-size:.85rem}
.card p{white-space:pre-wrap;margin:.5rem 0 0;font-size:.9rem;max-height:9em;overflow:auto}
.tags{margin-top:.5rem}
.tags span,.chips button{display:inline-block;font-size:.75rem;border:1px solid #ccc;border-radius:999px;
 padding:.1rem .6rem;margin:.15rem .2rem 0 0;background:#f4f4f4;color:#444}
.chips{margin:0 0 1.5rem}
.chips button{font-size:.85rem;padding:.3rem .9rem;cursor:pointer}
.chips button.active{background:#222;color:#fff;border-color:#222}
.account{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 1.5rem;padding:1rem;margin:.5rem 0;
 background:#fff;border:1px solid #ddd;border-radius:8px}
.account a{color:inherit}
.account details{display:contents}
.account summary{cursor:pointer;color:#555;font-size:.9rem}
.account details p{flex-basis:100%;line-height:1.5;max-width:70em;margin:.75rem 0 0}
.account .topics{flex-basis:100%}
.account .topics a{display:inline-block;font-size:.85rem;border:1px solid #ccc;border-radius:999px;
 padding:.15rem .7rem;margin:.2rem .2rem 0 0;background:#f4f4f4;text-decoration:none}
"""

JS = """
const chips=document.querySelectorAll('.chips button'),cards=document.querySelectorAll('.card');
document.querySelectorAll('.slides').forEach(s=>{const v=s.querySelectorAll('video');let i=0;
 const show=n=>{v[i].pause();v[i].hidden=true;i=(n+v.length)%v.length;v[i].hidden=false;
  s.querySelector('.count').textContent=`${i+1} / ${v.length}`;};
 s.querySelector('.prev').onclick=()=>show(i-1);s.querySelector('.next').onclick=()=>show(i+1);});
function apply(t){chips.forEach(b=>b.classList.toggle('active',b.dataset.topic===t));
 cards.forEach(c=>c.hidden=t!=='all'&&!(' '+c.dataset.topics+' ').includes(' '+t+' '));
 history.replaceState(null,'',t==='all'?location.pathname:'#'+t);}
chips.forEach(b=>b.onclick=()=>apply(b.dataset.topic));
apply(location.hash.slice(1)||'all');
"""


def build() -> None:
    """Generate the overview page and one page per account found in site/."""
    SITE.mkdir(exist_ok=True)
    accounts = []
    for account in sorted(p for p in SITE.iterdir() if (p / "index.json").exists()):
        index = json.loads((account / "index.json").read_text())
        profile = load_profile(account)
        compiled = compile_topics(profile["topics"])
        posts = [(c, e, classify(e["caption"], compiled)) for c, e in index.items() if e["files"]]
        posts.sort(key=lambda p: p[1]["taken_at"], reverse=True)
        counts = {t["id"]: sum(1 for p in posts if t["id"] in p[2]) for t in profile["topics"]}
        accounts.append((account.name, len(posts), profile, counts))
        write_account_page(account.name, posts, profile, counts)
    write_overview(accounts)
    print(f"site: {len(accounts)} accounts -> {SITE / 'index.html'}")


def write_account_page(name: str, posts: list, profile: dict, counts: dict) -> None:
    """Write the page of one account with its video cards and topic filter chips."""
    names = {t["id"]: t["name"] for t in profile["topics"]}
    cards = []
    for code, e, topics in posts:
        videos = "".join(
            f'<video controls preload="metadata" src="{html.escape(f)}"{" hidden" if k else ""}></video>'
            for k, f in enumerate(e["files"])
        )
        if len(e["files"]) > 1:
            videos = (
                f'<div class="slides">{videos}<button class="prev" aria-label="previous">&lsaquo;</button>'
                f'<button class="next" aria-label="next">&rsaquo;</button>'
                f'<span class="count">1 / {len(e["files"])}</span></div>'
            )
        tags = "".join(f"<span>{html.escape(names[t])}</span>" for t in topics)
        cards.append(
            f'<div class="card" data-topics="{" ".join(topics)}">{videos}<div class="meta">'
            f'<time>{e["date"]}</time> · <a href="https://www.instagram.com/p/{code}/">instagram</a>'
            f'<p>{html.escape(e["caption"])}</p><div class="tags">{tags}</div></div></div>'
        )
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
        f'<header><a href="../index.html">← all accounts</a> · <b>@{name}</b> · {len(posts)} videos</header>'
        f'<main>{chips}<div class="grid">{"".join(cards)}</div></main><script>{JS}</script>',
    )


def write_overview(accounts: list) -> None:
    """Write the overview page listing all accounts with their About box."""
    boxes = []
    for name, n, profile, counts in accounts:
        about = ""
        if profile["about"]:
            topics = "".join(
                f'<a href="{name}/index.html#{t["id"]}">{html.escape(t["name"])} · {counts[t["id"]]}</a>'
                for t in profile["topics"]
            )
            about = (
                f"<details><summary>About @{name}</summary><p>{html.escape(profile['about'])}</p>"
                f'<div class="topics">{topics}</div></details>'
            )
        boxes.append(
            f'<div class="account"><a href="{name}/index.html"><b>@{name}</b> · {n} videos</a>{about}</div>'
        )
    page(
        SITE / "index.html",
        "Instagram archive",
        f"<header><b>Instagram archive</b></header><main>{''.join(boxes)}</main>",
    )


def page(path: Path, title: str, body: str) -> None:
    """Write a complete HTML document with the shared stylesheet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"
    )
