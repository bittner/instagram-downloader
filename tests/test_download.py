# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import json

from insta import download

VIDEO = {
    "code": "abc",
    "media_type": 2,
    "taken_at": 1700000000,
    "user": {"username": "alice"},
    "caption": {"text": "hello"},
    "video_versions": [{"width": 640, "url": "u640"}, {"width": 1080, "url": "u1080"}],
}
IMAGE = {"code": "img", "media_type": 1, "user": {"username": "alice"}}
CAROUSEL = {
    "code": "car",
    "media_type": 8,
    "user": {"username": "alice"},
    "carousel_media": [{"media_type": 1}, {"media_type": 2, "video_versions": [{"width": 1, "url": "c2"}]}],
}
COLLAB = {
    "code": "col",
    "media_type": 2,
    "user": {"username": "bob"},
    "coauthor_producers": [{"username": "alice"}],
    "video_versions": [{"width": 1, "url": "x"}],
}


def test_shortcode_of_accepts_posts_and_reels():
    assert download.shortcode_of("https://www.instagram.com/p/AbC_1-2/") == "AbC_1-2"
    assert download.shortcode_of("https://www.instagram.com/reel/XYZ/?x=1") == "XYZ"
    assert download.shortcode_of("https://www.instagram.com/alice/") is None


def test_harvest_keeps_items_of_the_profile_only():
    items = {}
    download.harvest(
        {"a": [VIDEO, {"code": "other", "media_type": 2, "user": {"username": "bob"}}]}, items, "alice"
    )
    assert list(items) == ["abc"]


def test_harvest_accepts_coauthored_posts_and_any_owner_when_unfiltered():
    items = {}
    download.harvest(COLLAB, items, "alice")
    assert "col" in items
    items = {}
    download.harvest({"code": "z", "media_type": 2, "user": {"username": "nobody"}}, items, None)
    assert "z" in items


def test_harvest_prefers_the_richer_item():
    items = {}
    download.harvest({"code": "abc", "media_type": 2}, items, None)
    download.harvest(VIDEO, items, None)
    assert items["abc"] is VIDEO
    download.harvest({"code": "abc", "media_type": 2}, items, None)
    assert items["abc"] is VIDEO


def test_needs_detail():
    assert download.needs_detail(IMAGE) is False
    assert download.needs_detail(VIDEO) is False
    assert download.needs_detail({"code": "v", "media_type": 2}) is True
    assert download.needs_detail(CAROUSEL) is False
    assert (
        download.needs_detail({"code": "c", "media_type": 8, "carousel_media": [{"media_type": 2}]}) is True
    )
    assert download.needs_detail({"code": "?"}) is True


def test_video_urls_picks_widest_and_carousel_videos():
    assert download.video_urls(VIDEO) == ["u1080"]
    assert download.video_urls(CAROUSEL) == ["c2"]
    assert download.video_urls(IMAGE) == []


def test_caption_handles_dict_string_and_missing():
    assert download.caption(VIDEO) == "hello"
    assert download.caption({"caption": "plain"}) == "plain"
    assert download.caption({"caption": None}) == ""
    assert download.caption({}) == ""


def test_parse_json_blobs_handles_json_and_ndjson():
    assert list(download.parse_json_blobs('{"a": 1}')) == [{"a": 1}]
    assert list(download.parse_json_blobs('{"a": 1}\nnot json\n{"b": 2}')) == [{"a": 1}, {"b": 2}]


def test_rebuild_index_from_post_files(tmp_path):
    (tmp_path / "2023-11-14_abc.json").write_text(json.dumps(VIDEO))
    (tmp_path / "2023-11-14_abc.mp4").write_bytes(b"")
    (tmp_path / "2023-11-14_img.json").write_text(json.dumps(IMAGE))
    index = download.rebuild_index(tmp_path)
    assert index["abc"] == {
        "date": "2023-11-14",
        "taken_at": 1700000000,
        "video": True,
        "files": ["2023-11-14_abc.mp4"],
        "caption": "hello",
    }
    assert index["img"]["video"] is False


def test_download_streams_to_file_and_skips_existing(tmp_path, monkeypatch):
    class Response:
        raw = __import__("io").BytesIO(b"data")

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    calls = []
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: calls.append(a) or Response())
    target = tmp_path / "v.mp4"
    download.download("http://x", target)
    assert target.read_bytes() == b"data"
    download.download("http://x", target)
    assert len(calls) == 1
