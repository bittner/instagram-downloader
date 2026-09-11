# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json

import pytest

from insta import download

VIDEO = {
    "code": "abc",
    "media_type": 2,
    "taken_at": 1700000000,
    "user": {"username": "alice"},
    "caption": {"text": "hello"},
    "video_versions": [{"width": 640, "url": "u640"}, {"width": 1080, "url": "u1080"}],
}
IMAGE = {
    "code": "img",
    "media_type": 1,
    "user": {"username": "alice"},
    "image_versions2": {"candidates": [{"width": 640, "url": "i640"}, {"width": 1080, "url": "i1080"}]},
}
BARE_IMAGE = {"code": "bare", "media_type": 1, "user": {"username": "alice"}}
CAROUSEL = {
    "code": "car",
    "media_type": 8,
    "user": {"username": "alice"},
    "carousel_media": [
        {"media_type": 1, "image_versions2": {"candidates": [{"width": 1, "url": "c1"}]}},
        {"media_type": 2, "video_versions": [{"width": 1, "url": "c2"}]},
    ],
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
    assert download.needs_detail(BARE_IMAGE) is True
    assert download.needs_detail(VIDEO) is False
    assert download.needs_detail({"code": "v", "media_type": 2}) is True
    assert download.needs_detail(CAROUSEL) is False
    assert (
        download.needs_detail({"code": "c", "media_type": 8, "carousel_media": [{"media_type": 2}]}) is True
    )
    assert download.needs_detail({"code": "?"}) is True


def test_media_urls_picks_the_largest_rendition_of_each_medium_in_order():
    assert download.media_urls(VIDEO) == [("video", "u1080")]
    assert download.media_urls(IMAGE) == [("image", "i1080")]
    assert download.media_urls(CAROUSEL) == [("image", "c1"), ("video", "c2")]
    assert download.media_urls(BARE_IMAGE) == []


def test_media_count_and_describe():
    assert download.media_count(CAROUSEL) == 2
    assert download.media_count(IMAGE) == 1
    assert download.describe([("image", "a"), ("image", "b"), ("video", "c")]) == "2 photos, 1 video"
    assert download.describe([("video", "c")]) == "1 video"


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
        "media": 1,
        "files": ["2023-11-14_abc.mp4"],
        "caption": "hello",
    }
    assert index["img"]["video"] is False
    (tmp_path / "2023-11-14_img.jpg").write_bytes(b"")
    assert download.rebuild_index(tmp_path)["img"]["files"] == ["2023-11-14_img.jpg"]


class Response:
    def __init__(self, status=200, headers=None):
        self.status_code, self.headers = status, headers or {}
        self.raw = io.BytesIO(b"data")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise download.requests.HTTPError(f"{self.status_code} Client Error", response=self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_download_streams_to_file_and_skips_existing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: calls.append(a) or Response())
    target = tmp_path / "v.mp4"
    download.download("http://x", target)
    assert target.read_bytes() == b"data"
    download.download("http://x", target)
    assert len(calls) == 1


def test_download_backs_off_on_rate_limiting_and_honours_retry_after(tmp_path, monkeypatch, capsys):
    responses = iter([Response(429, {"Retry-After": "7"}), Response(429), Response()])
    waits = []
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(download.time, "sleep", waits.append)
    download.download("http://x", tmp_path / "v.mp4")
    assert (tmp_path / "v.mp4").read_bytes() == b"data"
    assert waits == [7, 60]  # Retry-After first, then the exponential default for the second attempt
    assert "HTTP 429" in capsys.readouterr().err


def test_download_defers_when_rate_limiting_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: Response(429, {"Retry-After": "soon"}))
    waits = []
    monkeypatch.setattr(download.time, "sleep", waits.append)
    with pytest.raises(download.TransientError, match="429 persists"):
        download.download("http://x", tmp_path / "v.mp4")
    assert len(waits) == download.RETRY_ATTEMPTS - 1
    assert not (tmp_path / "v.mp4").exists()


def test_download_retries_a_server_error_once_then_defers(tmp_path, monkeypatch, capsys):
    responses = iter([Response(500), Response(502)])
    waits = []
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(download.time, "sleep", waits.append)
    with pytest.raises(download.TransientError, match="HTTP 502"):
        download.download("http://x", tmp_path / "v.mp4")
    assert waits == [download.QUICK_WAIT]
    assert "HTTP 500, retrying" in capsys.readouterr().err


def test_download_recovers_from_a_single_server_error(tmp_path, monkeypatch):
    responses = iter([Response(503), Response()])
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(download.time, "sleep", lambda _s: None)
    download.download("http://x", tmp_path / "v.mp4")
    assert (tmp_path / "v.mp4").exists()


def test_download_raises_client_errors_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: Response(404))
    with pytest.raises(download.requests.HTTPError):
        download.download("http://x", tmp_path / "v.mp4")


def test_retry_after_parses_numbers_only():
    assert download.retry_after("12") == 12
    assert download.retry_after("-3") == 0
    assert download.retry_after("Wed, 21 Oct 2026 07:28:00 GMT") == 0
    assert download.retry_after(None) == 0


@pytest.fixture(autouse=True)
def default_pace(monkeypatch):
    monkeypatch.setitem(download.PACE, "seconds", 1.5)


def test_download_retries_a_connection_error_once_then_defers(tmp_path, monkeypatch):
    outcomes = iter([download.requests.ConnectionError(), download.requests.Timeout(), Response()])

    def get(*_a, **_k):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(download.requests, "get", get)
    waits = []
    monkeypatch.setattr(download.time, "sleep", waits.append)
    with pytest.raises(download.TransientError, match="Timeout"):
        download.download("http://x", tmp_path / "v.mp4")
    assert waits == [download.QUICK_WAIT]
    assert download.PACE["seconds"] == 1.5  # connection trouble is not rate limiting


def test_pace_never_exceeds_its_maximum(monkeypatch):
    monkeypatch.setattr(download.time, "sleep", lambda _s: None)
    monkeypatch.setitem(download.PACE, "seconds", 20.0)
    download.slow_down("HTTP 429", 1)
    assert download.PACE["seconds"] == download.PACE["max"]


USER = {
    "username": "alice",
    "full_name": "Alice A.",
    "biography": "Hi\nthere",
    "category": "Creator",
    "bio_links": [{"url": "https://a.example"}],
    "external_url": "https://b.example",
    "follower_count": 1234,
    "following_count": 5,
    "media_count": 7,
    "is_verified": False,
}


def test_harvest_account_finds_the_profiles_own_record():
    account = {}
    download.harvest_account(
        {"data": [{"username": "bob", "biography": "x"}, {"user": USER}]}, "alice", account
    )
    assert account["full_name"] == "Alice A."


def test_account_summary_reduces_the_record():
    summary = download.account_summary(USER)
    assert summary["links"] == ["https://b.example", "https://a.example"]
    assert summary["followers"] == 1234
    assert summary["posts"] == 7
    assert summary["category"] == "Creator"
    assert len(summary["captured"]) == 10
    assert download.account_summary({"username": "x", "biography": None})["biography"] == ""


def test_capture_response_captures_the_account_once(monkeypatch):
    class R:
        url = "https://www.instagram.com/api/graphql"
        request = type("Req", (), {"resource_type": "xhr"})()

        def __init__(self, body):
            self._body = body

        def text(self):
            return self._body

    account = {}
    download.capture_response(R(json.dumps({"user": USER})), {}, "alice", account)
    assert account["biography"] == "Hi\nthere"
    download.capture_response(R(json.dumps({"user": dict(USER, biography="changed")})), {}, "alice", account)
    assert account["biography"] == "Hi\nthere"  # the first capture stands


def test_save_media_names_files_by_slide_and_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "download", lambda url, path: path.write_text(url))
    entry = {"files": []}
    download.save_media(tmp_path, "2024-01-01_x", [("image", "a"), ("video", "b")], entry)
    download.save_media(tmp_path, "2024-01-01_y", [("image", "c")], entry)
    assert entry["files"] == ["2024-01-01_x_1.jpg", "2024-01-01_x_2.mp4", "2024-01-01_y.jpg"]


def test_needs_fetch_counts_files_against_expected_media(tmp_path):
    index = {
        "done": {"date": "2024-01-01", "media": 2, "files": ["a", "b"], "video": True},
        "half": {"date": "2024-01-01", "media": 2, "files": ["a"], "video": True},
        "old_photo": {"date": "2024-01-01", "files": [], "video": False},
        "old_video": {"date": "2024-01-01", "files": ["v.mp4"], "video": True},
        "old_mixed": {"date": "2024-01-01", "files": ["v.mp4"], "video": True},
    }
    (tmp_path / "2024-01-01_old_mixed.json").write_text(json.dumps(CAROUSEL))
    assert download.needs_fetch(index, "done", tmp_path) is False
    assert download.needs_fetch(index, "half", tmp_path) is True
    assert download.needs_fetch(index, "old_photo", tmp_path) is True  # archived before photos were saved
    assert download.needs_fetch(index, "old_video", tmp_path) is False
    assert download.needs_fetch(index, "old_mixed", tmp_path) is True  # the photo slide is missing
    assert download.needs_fetch(index, "unknown", tmp_path) is True
