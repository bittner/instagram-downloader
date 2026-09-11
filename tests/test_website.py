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
