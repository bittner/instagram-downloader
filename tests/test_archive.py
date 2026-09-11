# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the Chromium-driving code against a fake Playwright page."""

import json
import subprocess

import pytest

from insta import download

BASE = "https://www.instagram.com"


def item(code, owner="alice", taken_at=100, **extra):
    return {
        "code": code,
        "media_type": 2,
        "taken_at": taken_at,
        "user": {"username": owner},
        "caption": {"text": f"caption {code}"},
        "video_versions": [{"width": 1, "url": f"cdn/{code}"}],
        **extra,
    }


class FakeResponse:
    def __init__(self, url, body, resource_type="xhr"):
        self.url, self._body = url, body
        self.request = type("Req", (), {"resource_type": resource_type})()

    def text(self):
        if self._body is None:
            raise RuntimeError("body unavailable")
        return self._body


class FakePage:
    """Serves a profile grid whose links grow on every scroll, plus post pages with inline JSON."""

    def __init__(self, grid, posts, login_first=False):
        self.grid, self.posts, self.url = grid, posts, ""
        self.login_first = login_first
        self.scrolls = 0
        self.handlers = []
        self.mouse = type(
            "Mouse", (), {"wheel": lambda _s, _x, _y: setattr(self, "scrolls", self.scrolls + 1)}
        )()
        self.visited = []

    def goto(self, url, **_):
        self.visited.append(url)
        self.url = f"{BASE}/accounts/login/" if self.login_first else url
        self.login_first = False

    def wait_for_url(self, predicate, timeout):
        assert timeout == 0
        self.url = f"{BASE}/x/"
        assert predicate(self.url)

    def on(self, event, handler):
        self.handlers.append((event, handler))

    def remove_listener(self, event, handler):
        self.handlers.remove((event, handler))

    def emit(self, response):
        for _, handler in self.handlers:
            handler(response)

    def eval_on_selector_all(self, selector, _js):
        if selector.startswith("a["):
            return [f"{BASE}/p/{c}/" for c in self.grid[: 2 * (self.scrolls + 1)]]
        code = self.url.rstrip("/").rsplit("/", 1)[-1]
        return [json.dumps({"require": [self.posts[code]]})] if code in self.posts else ["{}"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "SITE", tmp_path)
    monkeypatch.setattr(download.time, "sleep", lambda _s: None)
    monkeypatch.setattr(download, "download", lambda url, path: path.write_text(url))
    return tmp_path


def test_archive_scans_grid_fetches_details_and_writes_index(env):
    posts = {
        "a": item("a", taken_at=200),
        "b": {"code": "b", "media_type": 1, "user": {"username": "alice"}},
        "c": item("c", owner="bob", coauthor_producers=[{"username": "alice"}]),
    }
    page = FakePage(["a", "b", "c"], posts)
    download.archive(page, "alice", full=True, limit=None)
    index = json.loads((env / "alice" / "index.json").read_text())
    assert index["a"]["files"] == ["1970-01-01_a.mp4"]
    assert (env / "alice" / "1970-01-01_a.mp4").read_text() == "cdn/a"
    assert json.loads((env / "alice" / "1970-01-01_a.json").read_text())["code"] == "a"
    assert index["b"] == {"date": "1970-01-01", "taken_at": 0, "video": False, "files": [], "caption": ""}
    assert index["c"]["video"] is True  # co-authored post accepted from its own page
    assert f"{BASE}/p/a/" in page.visited


def test_archive_uses_captured_responses_and_skips_known_posts(env):
    (env / "alice").mkdir()
    (env / "alice" / "index.json").write_text(
        json.dumps(
            {"old": {"date": "1970-01-01", "taken_at": 1, "video": True, "files": ["x.mp4"], "caption": ""}}
        )
    )
    page = FakePage(["new", "old"], {})
    original_goto = page.goto

    def goto_and_emit(url, **kw):
        original_goto(url, **kw)
        page.emit(FakeResponse(f"{BASE}/graphql/query", json.dumps({"data": [item("new")]})))
        page.emit(FakeResponse(f"{BASE}/graphql/query", None))  # unreadable body is ignored
        page.emit(FakeResponse("https://cdn.example/x", json.dumps(item("ignored")), "media"))

    page.goto = goto_and_emit
    download.archive(page, "alice", full=False, limit=None)
    index = json.loads((env / "alice" / "index.json").read_text())
    assert set(index) == {"old", "new"}
    assert index["new"]["files"] == ["1970-01-01_new.mp4"]
    assert not any("/p/new/" in u for u in page.visited)  # no detail page needed
    assert page.handlers == []  # listener removed again


def test_archive_keeps_going_after_a_failed_download_and_rescans_next_time(env, monkeypatch, capsys):
    def flaky(url, path):
        if "bad" in url:
            raise download.requests.HTTPError("429 Client Error")
        path.write_text(url)

    monkeypatch.setattr(download, "download", flaky)
    posts = {"bad": item("bad", taken_at=300), "good": item("good", taken_at=200)}
    download.archive(FakePage(["bad", "good"], posts), "alice", full=False, limit=None)
    index = json.loads((env / "alice" / "index.json").read_text())
    assert list(index) == ["good"]  # the failed post is left for the next run
    assert "1 failed" in capsys.readouterr().out
    assert not (env / "alice" / ".complete").exists()
    # the next run must not stop early at the known post, so it reaches the failed one
    monkeypatch.setattr(download, "download", lambda url, path: path.write_text(url))
    page = FakePage(["good", "bad"], posts)
    download.archive(page, "alice", full=False, limit=None)
    assert set(json.loads((env / "alice" / "index.json").read_text())) == {"good", "bad"}
    assert (env / "alice" / ".complete").exists()


def test_archive_stops_early_only_after_a_complete_run(env):
    posts = {f"p{i}": item(f"p{i}", taken_at=i) for i in range(20)}
    download.archive(FakePage(list(posts), posts), "alice", full=True, limit=None)
    assert (env / "alice" / ".complete").exists()
    page = FakePage(list(posts), posts)
    download.archive(page, "alice", full=False, limit=None)
    assert page.scrolls < 10  # stopped early, everything was known


def test_fetch_post_treats_a_failing_page_as_no_data(env, capsys):
    page = FakePage([], {})

    def broken(url, **_):
        raise download.PlaywrightError("net::ERR_CONNECTION_RESET\nCall log: ...")

    page.goto = broken
    assert download.fetch_post(page, "x", {}) is None
    assert "page failed: net::ERR_CONNECTION_RESET" in capsys.readouterr().err


def test_archive_reports_posts_without_data_and_honours_limit(env, capsys):
    page = FakePage(["ghost", "second"], {})
    download.archive(page, "alice", full=True, limit=1)
    assert "ghost: no data" in capsys.readouterr().err
    assert "second" not in json.loads((env / "alice" / "index.json").read_text())
    assert not (env / "alice" / ".complete").exists()


def test_scan_stops_early_when_only_known_posts_appear(env):
    page = FakePage([f"k{i}" for i in range(20)], {})
    codes = download.collect_shortcodes(page, "alice", {}, known={f"k{i}" for i in range(20)})
    assert 0 < len(codes) < 20


def test_goto_waits_for_login(env, capsys):
    page = FakePage([], {}, login_first=True)
    download.goto(page, f"{BASE}/alice/")
    assert "Log in to Instagram" in capsys.readouterr().out
    assert page.visited == [f"{BASE}/alice/", f"{BASE}/alice/"]


def test_ensure_browser_returns_none_when_already_running(monkeypatch):
    monkeypatch.setattr(download, "cdp_alive", lambda: True)
    assert download.ensure_browser() is None


def test_ensure_browser_starts_and_waits_for_it(monkeypatch):
    alive = iter([False, False, True])
    monkeypatch.setattr(download, "cdp_alive", lambda: next(alive))
    monkeypatch.setattr(download.time, "sleep", lambda _s: None)
    monkeypatch.setattr(download, "browser_command", lambda _e: ["/bin/chromium"])
    started = {}
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.setdefault("cmd", cmd) and "proc")
    assert download.ensure_browser("/bin/chromium") == "proc"
    assert started["cmd"][0] == "/bin/chromium"
    assert f"--remote-debugging-port={download.CDP_PORT}" in started["cmd"]


def test_ensure_browser_gives_up(monkeypatch):
    monkeypatch.setattr(download, "cdp_alive", lambda: False)
    monkeypatch.setattr(download.time, "sleep", lambda _s: None)
    monkeypatch.setattr(download, "browser_command", lambda _e: ["/bin/chromium"])
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        download.ensure_browser()


@pytest.fixture
def no_browser(monkeypatch):
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.setattr(download.shutil, "which", lambda _n: None)
    monkeypatch.setattr(download.sys, "platform", "linux")


def test_browser_command_prefers_the_explicit_executable(no_browser):
    assert download.browser_command("/opt/brave") == ["/opt/brave"]


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ("/usr/bin/google-chrome-stable", "/usr/bin/google-chrome-stable"),
        ("brave %s", "brave"),
        ("chromium:firefox", "chromium"),
        ("firefox", None),
        ("xdg-open", None),
        ("", None),
    ],
)
def test_preferred_browser_honours_a_chromium_based_dollar_browser(monkeypatch, env, expected):
    monkeypatch.setenv("BROWSER", env)
    assert download.preferred_browser() == expected


def test_browser_command_uses_dollar_browser_before_searching(no_browser, monkeypatch):
    monkeypatch.setenv("BROWSER", "/opt/vivaldi/vivaldi")
    assert download.browser_command() == ["/opt/vivaldi/vivaldi"]


def test_browser_command_finds_a_browser_on_the_path(monkeypatch):
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.setattr(download.shutil, "which", lambda n: "/usr/bin/brave" if n == "brave" else None)
    assert download.browser_command() == ["/usr/bin/brave"]


def test_browser_command_finds_platform_application_bundles(no_browser, monkeypatch):
    monkeypatch.setattr(download.sys, "platform", "darwin")
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    monkeypatch.setattr(download.Path, "exists", lambda self: str(self) == chrome)
    assert download.browser_command() == [chrome]


def test_browser_command_falls_back_to_nix(no_browser, monkeypatch):
    monkeypatch.setattr(download.shutil, "which", lambda n: "/run/nix" if n == "nix" else None)
    assert download.browser_command()[:3] == ["nix", "run", "nixpkgs#chromium"]


def test_browser_command_installs_playwright_chromium_as_last_resort(no_browser, monkeypatch, capsys):
    monkeypatch.setattr(download.Path, "exists", lambda self: False)
    runs = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: runs.append(cmd))
    chromium = type("Ch", (), {"executable_path": "/pw/chromium"})()
    pw = type("PW", (), {"chromium": chromium, "__enter__": lambda s: s, "__exit__": lambda *_a: None})()
    monkeypatch.setattr(download, "sync_playwright", lambda: pw)
    assert download.browser_command() == ["/pw/chromium"]
    assert runs[0][-3:] == ["playwright", "install", "chromium"]
    assert "Playwright's own Chromium" in capsys.readouterr().out


def test_cdp_alive(monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: None)
    assert download.cdp_alive() is True

    def refuse(*_a, **_k):
        raise download.requests.ConnectionError

    monkeypatch.setattr(download.requests, "get", refuse)
    assert download.cdp_alive() is False


def test_archive_all_drives_one_page_per_account(monkeypatch):
    calls = []
    page = type("P", (), {"close": lambda _s: calls.append("close")})()
    ctx = type("C", (), {"new_page": lambda _s: page})()
    browser = type("B", (), {"contexts": [ctx]})()
    chromium = type("Ch", (), {"connect_over_cdp": lambda _s, _u: browser})()
    pw = type("PW", (), {"chromium": chromium, "__enter__": lambda s: s, "__exit__": lambda *_a: None})()
    monkeypatch.setattr(download, "sync_playwright", lambda: pw)
    proc = type("Proc", (), {"terminate": lambda _s: calls.append("terminate")})()
    monkeypatch.setattr(download, "ensure_browser", lambda _e: proc)
    monkeypatch.setattr(download, "archive", lambda p, u, **kw: calls.append((u, kw)))
    download.archive_all(["alice", "bob"], full=True, limit=2, browser="/bin/chromium")
    assert calls == [
        ("alice", {"full": True, "limit": 2}),
        ("bob", {"full": True, "limit": 2}),
        "close",
        "terminate",
    ]
