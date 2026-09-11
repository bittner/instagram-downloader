# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a generated site in a real browser and check what the filters actually show.

These tests need a Chromium: one found on the PATH, or Playwright's own
(``uv run playwright install chromium``). They are skipped otherwise.
"""

import base64
import json
import shutil

import pytest
from playwright.sync_api import Error, sync_playwright

from insta import download, website

ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
INDEX = {
    "photo": {
        "date": "2024-03-01",
        "taken_at": 300,
        "video": False,
        "media": 1,
        "files": ["p.jpg"],
        "caption": "#a",
    },
    "video": {
        "date": "2024-02-01",
        "taken_at": 200,
        "video": True,
        "media": 1,
        "files": ["v.mp4"],
        "caption": "#a",
    },
    "carousel": {
        "date": "2024-01-01",
        "taken_at": 100,
        "video": True,
        "media": 2,
        "files": ["c_1.jpg", "c_2.mp4"],
        "caption": "#b",
    },
}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        executable = next((shutil.which(n) for n in download.BROWSER_NAMES if shutil.which(n)), None)
        try:
            b = p.chromium.launch(executable_path=executable)
        except Error as e:
            pytest.skip(f"no Chromium to run the browser tests: {str(e).splitlines()[0]}")
        yield b
        b.close()


@pytest.fixture
def account_page(tmp_path, monkeypatch):
    monkeypatch.setattr(website, "SITE", tmp_path)
    (tmp_path / "alice").mkdir()
    (tmp_path / "alice" / "index.json").write_text(json.dumps(INDEX))
    for photo in ("p.jpg", "c_1.jpg"):
        (tmp_path / "alice" / photo).write_bytes(base64.b64decode(ONE_PIXEL_PNG))
    website.build(quiet=True)
    return (tmp_path / "alice" / "index.html").as_uri()


def shown(page) -> int:
    return page.evaluate(
        "[...document.querySelectorAll('.card')].filter(c => c.getBoundingClientRect().height > 0).length"
    )


def test_type_filter_hides_the_other_cards(browser, account_page):
    page = browser.new_page()
    page.goto(account_page)
    assert shown(page) == 3
    full_height = page.evaluate("document.documentElement.scrollHeight")
    page.click('.types button[data-type="photo"]')
    assert shown(page) == 1
    assert page.evaluate("document.documentElement.scrollHeight") < full_height
    assert page.evaluate("location.hash") == "#type=photo"
    page.click('.types button[data-type="all"]')
    assert shown(page) == 3
    page.close()


def test_topic_filter_combines_with_the_type_filter(browser, account_page):
    page = browser.new_page()
    page.goto(account_page)
    page.click('.chips button[data-topic="a"]')
    assert shown(page) == 2
    page.click('.types button[data-type="video"]')
    assert shown(page) == 1
    assert page.evaluate("location.hash") == "#topic=a&type=video"
    page.close()


def test_lightbox_enlarges_photos_and_videos_alike(browser, account_page):
    page = browser.new_page()
    page.goto(account_page)
    box = page.locator(".lightbox")
    assert box.is_hidden()
    page.click('.card[data-type="photo"] .media img')
    assert box.is_visible()
    assert page.locator(".lightbox .stage img").get_attribute("src") == "p.jpg"
    assert page.locator(".lightbox .prev").is_hidden()  # a single photo has no slides
    page.keyboard.press("Escape")
    assert box.is_hidden()
    page.click('.card[data-type="carousel"] .media img')  # a real click, through the slider's pointer capture
    assert page.locator(".lightbox .stage img").get_attribute("src") == "c_1.jpg"
    assert page.locator(".lightbox .count").inner_text() == "1 / 2"
    page.keyboard.press("ArrowRight")
    assert page.locator(".lightbox .stage video").get_attribute("src") == "c_2.mp4"
    page.locator(".lightbox .close").click()
    assert box.is_hidden()
    page.locator('.card[data-type="video"] .expand').dispatch_event("click")
    assert page.locator(".lightbox .stage video").get_attribute("src") == "v.mp4"
    page.locator(".lightbox .close").click()
    page.click(
        '.card[data-type="video"] .media video', position={"x": 10, "y": 10}
    )  # plays, does not enlarge
    assert box.is_hidden()
    page.close()
