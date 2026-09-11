# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

from insta import website

INDEX = {
    "new": {
        "date": "2024-02-01",
        "taken_at": 200,
        "video": True,
        "files": ["2024-02-01_new.mp4"],
        "caption": "riciclo <b>",
    },
    "old": {
        "date": "2024-01-01",
        "taken_at": 100,
        "video": True,
        "files": ["2024-01-01_old_1.mp4", "2024-01-01_old_2.mp4"],
        "caption": "plain",
    },
    "pic": {"date": "2024-01-02", "taken_at": 150, "video": False, "files": [], "caption": "x"},
}
PROFILE = {"about": "About <alice>", "topics": [{"id": "waste", "name": "Waste", "keywords": ["ricicl"]}]}


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(website, "SITE", tmp_path)
    (tmp_path / "alice").mkdir()
    (tmp_path / "alice" / "index.json").write_text(json.dumps(INDEX))
    return tmp_path


def test_build_writes_overview_and_account_page(site, capsys):
    website.build()
    overview = (site / "index.html").read_text()
    account = (site / "alice" / "index.html").read_text()
    assert "@alice</b> · 2 videos" in overview
    assert "<details>" not in overview
    assert account.index("2024-02-01_new.mp4") < account.index("2024-01-01_old_1.mp4")
    assert (
        '<div class="slides"><div class="track"><video controls preload="metadata" src="2024-01-01_old_1'
        in account
    )
    assert 'src="2024-01-01_old_2.mp4"></video></div><button class="prev"' in account
    assert '<span class="count">1 / 2</span>' in account
    assert account.count('class="slides"') == 1  # single videos get no slider
    assert "riciclo &lt;b&gt;" in account
    assert 'href="https://www.instagram.com/p/new/"' in account
    assert "1 accounts" in capsys.readouterr().out


def test_profile_adds_about_box_and_topic_filters(site):
    (site / "alice" / "profile.json").write_text(json.dumps(PROFILE))
    website.build()
    overview = (site / "index.html").read_text()
    account = (site / "alice" / "index.html").read_text()
    assert "<summary>About @alice</summary><p>About &lt;alice&gt;</p>" in overview
    assert 'href="alice/index.html#waste">Waste · 1</a>' in overview
    assert 'data-topic="all">All · 2</button>' in account
    assert 'data-topic="waste">Waste · 1</button>' in account
    assert 'data-topics="waste"' in account
    assert 'data-topics=""' in account


def test_folders_without_index_are_ignored(site):
    (site / "stray").mkdir()
    website.build()
    assert not (site / "stray" / "index.html").exists()


HEADER = {
    "username": "alice",
    "full_name": "Alice <A>",
    "biography": "Bio line 1\nline 2",
    "category": "Creator",
    "links": ["https://alice.example/"],
    "followers": 12345,
    "following": 1,
    "posts": 3,
    "verified": False,
}


def test_captured_header_provides_the_baseline_about_and_hashtag_topics(site):
    (site / "alice" / "account.json").write_text(json.dumps(HEADER))
    (site / "alice" / "index.json").write_text(
        json.dumps(
            dict(
                INDEX,
                new=dict(INDEX["new"], caption="#riciclo <b>"),
                old=dict(INDEX["old"], caption="#riciclo x"),
            )
        )
    )
    website.build()
    overview = (site / "index.html").read_text()
    account = (site / "alice" / "index.html").read_text()
    assert (
        '<span class="header"><span class="name">Alice &lt;A&gt;</span> · 12,345 followers</span><details>'
        in overview
    )
    assert "<p>Bio line 1\nline 2</p>" in overview
    assert (
        '<p class="facts">Creator · 3 posts · 1 following · <a href="https://alice.example/">alice.example</a>'
        in overview
    )
    assert 'data-topic="riciclo">#riciclo · 2</button>' in account


def test_hand_written_profile_wins_over_the_captured_header(site):
    (site / "alice" / "account.json").write_text(json.dumps(HEADER))
    (site / "alice" / "profile.json").write_text(json.dumps(PROFILE))
    website.build()
    overview = (site / "index.html").read_text()
    assert "<p>About &lt;alice&gt;</p>" in overview
    assert "Bio line 1" not in overview
    assert "12,345 followers" in overview  # the factual line is shown regardless


def test_header_line_and_facts_are_empty_without_a_header():
    assert website.header_line({}) == ""
    assert website.header_line({"followers": 0}) == "0 followers"
    assert website.header_facts({}) == ""
    assert website.header_facts({"captured": "2026-09-11"}) == "captured 2026-09-11"


def test_linkify_links_urls_mentions_and_hashtags_and_escapes_the_rest():
    out = website.linkify("See https://a.example/x?y=1. Thanks @grs.arch & #Casa2 <b>")
    assert '<a href="https://a.example/x?y=1">https://a.example/x?y=1</a>.' in out
    assert '<a href="https://www.instagram.com/grs.arch/">@grs.arch</a> &amp;' in out
    assert '<a href="https://www.instagram.com/explore/tags/Casa2/">#Casa2</a> &lt;b&gt;' in out


def test_linkify_leaves_emails_alone():
    assert website.linkify("mail me@example.com") == "mail me@example.com"


def test_captions_and_about_texts_are_linkified(site):
    (site / "alice" / "profile.json").write_text(json.dumps(dict(PROFILE, about="Hi @bob")))
    website.build()
    assert '<a href="https://www.instagram.com/bob/">@bob</a>' in (site / "index.html").read_text()
    assert "riciclo &lt;b&gt;" in (site / "alice" / "index.html").read_text()


def test_card_text_area_keeps_its_styling():
    assert ".card .meta{padding" in website.CSS
    assert ".card p{white-space:pre-wrap" in website.CSS


def test_pages_get_the_sticky_header_script(site):
    website.build()
    for page in (site / "index.html", site / "alice" / "index.html"):
        html_text = page.read_text()
        assert "header.away{transform:translateY(-100%)}" in html_text
        assert "hdr.classList.toggle('away'" in html_text
