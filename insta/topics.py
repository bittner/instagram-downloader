# SPDX-License-Identifier: GPL-3.0-or-later
"""Topic classification of posts by keyword rules.

Each account may ship a ``profile.json`` next to its ``index.json`` with an ``about``
text and a list of topics, each a name plus keywords. A keyword matches at the start of
a word (``ricicl`` matches ``riciclo`` and ``riciclabile``); a keyword ending in a space
matches a whole word only (``api `` matches ``api`` but not ``apice``). A post can have
several topics.
"""
import json
import re
from pathlib import Path


def load_profile(account_dir: Path) -> dict:
    f = account_dir / "profile.json"
    return json.loads(f.read_text()) if f.exists() else {"about": "", "topics": []}


def compile_topics(topics: list[dict]) -> list[tuple[str, re.Pattern]]:
    out = []
    for t in topics:
        parts = []
        for k in t["keywords"]:
            k = k.lower()
            whole = k.endswith(" ")
            parts.append(r"(?<!\w)" + re.escape(k.strip()) + (r"(?!\w)" if whole else ""))
        out.append((t["id"], re.compile("|".join(parts), re.I)))
    return out


def classify(caption: str, compiled: list[tuple[str, re.Pattern]]) -> list[str]:
    """Return the ids of all topics whose keywords occur in the caption."""
    return [tid for tid, rx in compiled if rx.search(caption)]
