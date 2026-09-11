# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Archive the videos and reels of an Instagram profile via a real browser session.

Instagram blocks scripted API clients, so this drives a Chromium-based browser over
the DevTools protocol: it scrolls the profile, collects the post data Instagram sends to the page,
and downloads the video files from Instagram's CDN. Only posts containing video
(feed videos, reels, video slides in carousels) are saved, into site/USERNAME/.
Known posts are recorded in site/USERNAME/index.json; later runs stop scanning
once they reach known posts and only download what is new.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

ROOT = Path.cwd()
SITE = ROOT / "site"
CHROMIUM_PROFILE = ROOT / ".chromium"
CDP_PORT = 9222
BASE = "https://www.instagram.com"
MEDIA_MARKERS = re.compile(r'"(?:video_versions|carousel_media|media_type)"')


Progress = Callable[[], None]


def archive_all(
    usernames: list[str],
    *,
    full: bool = False,
    limit: int | None = None,
    browser: str | None = None,
    on_progress: Progress | None = None,
) -> None:
    """Archive several profiles in one browser session, starting the browser if needed.

    ``on_progress`` is called after every archived post, e.g. to rebuild the site.
    """
    proc = ensure_browser(browser)
    with sync_playwright() as p:
        cdp = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        page = cdp.contexts[0].new_page()
        for username in usernames:
            archive(page, username, full=full, limit=limit, on_progress=on_progress)
        page.close()
    if proc:
        proc.terminate()


def archive(
    page: Page, profile: str, *, full: bool, limit: int | None, on_progress: Progress | None = None
) -> None:
    """Download the new videos of one profile and update its index."""
    out = SITE / profile
    out.mkdir(parents=True, exist_ok=True)
    for part in out.glob("*.part"):  # left over from an interrupted download
        part.unlink()
    index_file = out / "index.json"
    complete = out / ".complete"  # present once a run has gone through the whole profile
    full = full or not complete.exists()
    complete.unlink(missing_ok=True)
    index: dict[str, dict] = json.loads(index_file.read_text()) if index_file.exists() else rebuild_index(out)
    items: dict[str, dict] = {}  # shortcode -> media item as sent by Instagram
    account: dict = {}  # the profile header (bio, name, counts) as sent by Instagram
    handler = lambda r: capture_response(r, items, profile, account)
    page.on("response", handler)

    print(f"@{profile}: {len(index)} posts known")
    run = Run(page, out, index, items, on_progress)
    pending = [c for c in load_pending(out) if c not in index]
    if pending:
        print(f"  {len(pending)} posts pending from the previous run, fetching them first")
        run.process_all(pending, fresh=True)
    codes = collect_shortcodes(page, profile, items, known=set() if full else set(index))
    if account:
        write_json(out / "account.json", account_summary(account))
        if on_progress:
            on_progress()  # show the profile header on the site right away
    if limit:
        codes = codes[:limit]
    todo = [c for c in codes if needs_fetch(index, c) and c not in run.queued]
    print(f"  {len(codes)} posts scanned, {len(todo)} to fetch")
    run.process_all(todo)
    run.retry_deferred(final=True)

    write_json(index_file, index)
    run.save_pending()
    page.remove_listener("response", handler)
    if not run.failed and not limit:
        complete.touch()
    n_video = sum(1 for e in index.values() if e["video"])
    failed = f", {run.failed} failed" if run.failed else ""
    print(f"  done: {len(index)} posts known, {n_video} with video{failed}")


def needs_fetch(index: dict, code: str) -> bool:
    """Whether a post is not archived yet: unknown, or known as a video without its files."""
    return code not in index or (index[code]["video"] and not index[code]["files"])


def load_pending(out: Path) -> list[str]:
    """Read the posts a previous run left to fetch, if it recorded any."""
    f = out / "pending.json"
    return json.loads(f.read_text()) if f.exists() else []


DEFER_ATTEMPTS = 3  # tries per post and run before it is left for the next run
DEFER_INTERVAL = 60.0  # seconds before a deferred post is tried again


@dataclass
class Run:
    """The state of archiving one profile: the posts done, deferred and failed."""

    page: Page
    out: Path
    index: dict[str, dict]
    items: dict[str, dict]
    on_progress: Progress | None = None
    queued: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    last_try: dict[str, float] = field(default_factory=dict)
    failed: int = 0

    def process_all(self, codes: list[str], *, fresh: bool = False) -> None:
        """Archive the posts in order, retrying a deferred one after each success."""
        self.queued += codes
        self.save_pending()
        for i, code in enumerate(codes, 1):
            if self.process(code, f"[{i}/{len(codes)}]", fresh=fresh) == "ok":
                self.retry_deferred()
            self.save_pending()

    def save_pending(self) -> None:
        """Record the queued posts that are not archived yet, so the next run can start with them."""
        pending = [c for c in dict.fromkeys(self.queued) if needs_fetch(self.index, c)]
        f = self.out / "pending.json"
        if pending:
            write_json(f, pending)
        else:
            f.unlink(missing_ok=True)

    def process(self, code: str, label: str, *, fresh: bool = False) -> str:
        """Archive one post; returns "ok", "skip" (no data), "deferred" or "failed"."""
        item = None if fresh else self.items.get(code)
        if item is None or needs_detail(item):
            item = fetch_post(self.page, code, self.items)
        if item is None:
            print(f"  {label} {code}: no data", file=sys.stderr)
            return "skip"
        date = datetime.fromtimestamp(item.get("taken_at", 0), timezone.utc)
        stem = f"{date:%Y-%m-%d}_{code}"
        videos = video_urls(item)
        entry = {
            "date": f"{date:%Y-%m-%d}",
            "taken_at": item.get("taken_at", 0),
            "video": bool(videos),
            "files": [],
            "caption": caption(item),
        }
        if videos:
            print(f"  {label} {stem} ({len(videos)} video{'s' if len(videos) > 1 else ''})")
            try:
                save_videos(self.out, stem, videos, entry)
            except TransientError as e:
                return self.defer(code, str(e))
            except requests.RequestException as e:
                print(f"  failed, will retry on the next run: {e}", file=sys.stderr)
                self.failed += 1
                return "failed"
            write_json(self.out / f"{stem}.json", item)
        self.index[code] = entry
        write_json(self.out / "index.json", self.index)
        if self.on_progress:
            self.on_progress()
        time.sleep(PACE["seconds"])
        return "ok"

    def defer(self, code: str, reason: str) -> str:
        """Queue a post for a later attempt within this run, or give up on it for this run."""
        self.attempts[code] = self.attempts.get(code, 0) + 1
        self.last_try[code] = time.monotonic()
        if self.attempts[code] >= DEFER_ATTEMPTS:
            print(f"  {reason}, giving up on this post for this run", file=sys.stderr)
            self.failed += 1
            return "failed"
        print(f"  {reason}, deferring the post", file=sys.stderr)
        self.deferred.append(code)
        return "deferred"

    def retry_deferred(self, *, final: bool = False) -> None:
        """Retry one deferred post that has waited long enough, or all of them at the end of the run."""
        while self.deferred:
            due = [c for c in self.deferred if final or time.monotonic() - self.last_try[c] >= DEFER_INTERVAL]
            if not due:
                return
            code = due[0]
            self.deferred.remove(code)
            self.process(code, "[retry]", fresh=True)  # a reloaded page brings fresh video URLs
            if not final:
                return


def save_videos(out: Path, stem: str, urls: list[str], entry: dict) -> None:
    """Download a post's videos into the account folder, recording each file in the index entry."""
    for k, url in enumerate(urls, 1):
        name = f"{stem}.mp4" if len(urls) == 1 else f"{stem}_{k}.mp4"
        download(url, out / name)
        entry["files"].append(name)


def write_json(path: Path, data: dict | list) -> None:
    """Write data as readable JSON."""
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def rebuild_index(out: Path) -> dict[str, dict]:
    """Recreate the index from post JSON files already on disk."""
    index = {}
    for f in sorted(out.glob("????-??-??_*.json")):
        item = json.loads(f.read_text())
        code, date = item["code"], f.name[:10]
        files = sorted(p.name for p in out.glob(f"{date}_{code}*.mp4"))
        index[code] = {
            "date": date,
            "taken_at": item.get("taken_at", 0),
            "video": bool(files),
            "files": files,
            "caption": caption(item),
        }
    return index


# ---------------------------------------------------------------- browser


BROWSER_NAMES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "chrome",
    "brave",
    "brave-browser",
    "microsoft-edge",
    "msedge",
    "vivaldi",
    "opera",
)
BROWSER_APPS = {
    "darwin": (
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
    ),
    "win32": (
        r"C:\Program Files\Chromium\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ),
}


CHROMIUM_FAMILY = ("chromium", "chrome", "brave", "edge", "vivaldi", "opera")


def preferred_browser() -> str | None:
    """Return the browser from the conventional $BROWSER variable if it is Chromium-based.

    $BROWSER may hold a colon-separated list and a %s placeholder for the URL, as
    the convention allows; only the first entry is used, without the placeholder.
    """
    first = os.environ.get("BROWSER", "").split(":")[0].replace("%s", "").strip()
    if first and any(name in Path(first).name.lower() for name in CHROMIUM_FAMILY):
        return first
    return None


def browser_command(explicit: str | None = None) -> list[str]:
    """Return the command that starts a Chromium-based browser.

    Looks for the given executable first, then for a Chromium-based $BROWSER, then
    for the common browsers on the PATH and in the platform's application folders,
    then for Nix, and finally falls back to Playwright's own Chromium, which is
    downloaded on first use.
    """
    if explicit:
        return [explicit]
    if preferred := preferred_browser():
        return [preferred]
    for name in BROWSER_NAMES:
        if exe := shutil.which(name):
            return [exe]
    for app in BROWSER_APPS.get(sys.platform, ()):
        if Path(app).exists():
            return [app]
    if shutil.which("nix"):
        return ["nix", "run", "nixpkgs#chromium", "--"]
    print("No Chromium-based browser found; using Playwright's own Chromium...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    with sync_playwright() as p:
        return [p.chromium.executable_path]


def ensure_browser(explicit: str | None = None) -> subprocess.Popen | None:
    """Start the browser unless one is listening; return its process if this run started it."""
    if cdp_alive():
        return None
    cmd = [
        *browser_command(explicit),
        f"--user-data-dir={CHROMIUM_PROFILE}",
        "--password-store=basic",
        "--no-first-run",
        f"--remote-debugging-port={CDP_PORT}",
        "about:blank",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        time.sleep(1)
        if cdp_alive():
            return proc
    sys.exit("The browser did not start")


def cdp_alive() -> bool:
    """Return whether a Chromium DevTools endpoint answers on the configured port."""
    try:
        requests.get(f"http://localhost:{CDP_PORT}/json/version", timeout=2)
    except requests.ConnectionError:
        return False
    return True


def goto(page: Page, url: str) -> None:
    """Open the URL, waiting for the user to log in first if Instagram asks for it."""
    page.goto(url, wait_until="domcontentloaded")
    if "/accounts/login" in page.url or "/challenge" in page.url:
        print("Log in to Instagram in the Chromium window...")
        page.wait_for_url(lambda u: "/accounts/login" not in u and "/challenge" not in u, timeout=0)
        page.goto(url, wait_until="domcontentloaded")
    time.sleep(3)


def collect_shortcodes(page: Page, profile: str, items: dict, known: set[str]) -> list[str]:
    """Scroll the profile grid, returning shortcodes newest first.

    Stops early once a few consecutive scroll batches bring only known posts
    (a few pinned posts at the top are tolerated by the batch counter).
    """
    goto(page, f"{BASE}/{profile}/")
    capture_inline(page, items, profile)
    seen: list[str] = []
    idle = stale = 0
    while idle < 5 and stale < 3:
        hrefs = page.eval_on_selector_all('a[href*="/p/"], a[href*="/reel/"]', "els => els.map(e => e.href)")
        new = list(dict.fromkeys(c for h in hrefs if (c := shortcode_of(h)) and c not in seen))
        seen += new
        idle = 0 if new else idle + 1
        stale = stale + 1 if known and new and all(c in known for c in new) else 0
        page.mouse.wheel(0, 6000)
        time.sleep(2)
        print(f"\r  scanning profile: {len(seen)} posts", end="", flush=True)
    print()
    return seen


def fetch_post(page: Page, code: str, items: dict) -> dict | None:
    """Open a post page and return the media item captured from it, None if the page fails."""
    try:
        goto(page, f"{BASE}/p/{code}/")
        capture_inline(page, items, None)  # the code came from the profile grid; accept any owner
    except PlaywrightError as e:
        print(f"  page failed: {str(e).splitlines()[0]}", file=sys.stderr)
        return None
    return items.get(code)


# ---------------------------------------------------------------- data capture


def shortcode_of(href: str) -> str | None:
    """Extract the post shortcode from a post or reel URL."""
    m = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)/", href)
    return m.group(1) if m else None


def capture_response(r, items: dict, profile: str, account: dict | None = None) -> None:
    """Harvest media items, and the profile header, from an XHR/fetch response of the page."""
    if "instagram.com" not in r.url or r.request.resource_type not in ("xhr", "fetch"):
        return
    try:
        body = r.text()
    except Exception:
        return
    if MEDIA_MARKERS.search(body):
        for obj in parse_json_blobs(body):
            harvest(obj, items, profile)
    if account is not None and not account and '"biography"' in body:
        for obj in parse_json_blobs(body):
            harvest_account(obj, profile, account)


def harvest_account(obj, profile: str, account: dict) -> None:
    """Walk any JSON structure and keep the profile's own user record with its biography."""
    if isinstance(obj, dict):
        if obj.get("username") == profile and "biography" in obj:
            account.update(obj)
            return
        for v in obj.values():
            harvest_account(v, profile, account)
    elif isinstance(obj, list):
        for v in obj:
            harvest_account(v, profile, account)


def account_summary(user: dict) -> dict:
    """Reduce Instagram's user record to the fields the site shows."""
    links = [link.get("url") for link in user.get("bio_links") or [] if link.get("url")]
    if user.get("external_url") and user["external_url"] not in links:
        links.insert(0, user["external_url"])
    return {
        "username": user.get("username"),
        "full_name": user.get("full_name") or "",
        "biography": user.get("biography") or "",
        "category": user.get("category") or user.get("category_name") or "",
        "links": links,
        "followers": user.get("follower_count"),
        "following": user.get("following_count"),
        "posts": user.get("media_count"),
        "verified": bool(user.get("is_verified")),
        "captured": f"{datetime.now(timezone.utc):%Y-%m-%d}",
    }


def capture_inline(page: Page, items: dict, profile: str | None) -> None:
    """Harvest media items from the JSON embedded in the page's script tags."""
    for text in page.eval_on_selector_all(
        'script[type="application/json"]', "els => els.map(e => e.textContent)"
    ):
        if MEDIA_MARKERS.search(text):
            for obj in parse_json_blobs(text):
                harvest(obj, items, profile)


def parse_json_blobs(text: str):
    """Yield the JSON documents in a response body, which may be newline-delimited."""
    try:
        blob = json.loads(text)
    except ValueError:
        blob = None
    if blob is not None:
        yield blob
        return
    for line in text.splitlines():  # some GraphQL responses are newline-delimited JSON
        try:
            yield json.loads(line)
        except ValueError:
            continue


def harvest(obj, items: dict, profile: str | None) -> None:
    """Walk any JSON structure and keep media items owned or co-authored by the profile (any, if None)."""
    if isinstance(obj, dict):
        if "code" in obj and ("video_versions" in obj or "carousel_media" in obj or "media_type" in obj):
            authors = [obj.get("user") or obj.get("owner") or {}] + (obj.get("coauthor_producers") or [])
            if profile is None or profile in (a.get("username") for a in authors):
                old = items.get(obj["code"])
                if old is None or len(json.dumps(obj)) > len(json.dumps(old)):
                    items[obj["code"]] = obj
        for v in obj.values():
            harvest(v, items, profile)
    elif isinstance(obj, list):
        for v in obj:
            harvest(v, items, profile)


def needs_detail(item: dict) -> bool:
    """True if the captured item lacks the fields needed to download it."""
    mt = item.get("media_type")
    if mt == 1:
        return False
    if mt == 2:
        return not item.get("video_versions")
    if mt == 8:
        return not item.get("carousel_media") or any(
            m.get("media_type") == 2 and not m.get("video_versions") for m in item["carousel_media"]
        )
    return True


def video_urls(item: dict) -> list[str]:
    """Return the best video URL of a post, or one per video slide of a carousel."""

    def best(m):
        vv = m.get("video_versions") or []
        return max(vv, key=lambda v: v.get("width", 0))["url"] if vv else None

    if item.get("media_type") == 8:
        return [u for m in item.get("carousel_media", []) if (u := best(m))]
    return [u] if (u := best(item)) else []


def caption(item: dict) -> str:
    """Return the caption text of a media item, empty if it has none."""
    c = item.get("caption")
    return (c.get("text") if isinstance(c, dict) else c) or ""


RETRY_ATTEMPTS = 6  # back-offs on rate limiting before a post is deferred
QUICK_RETRIES = 1  # immediate retries on server errors and dropped connections before deferring
QUICK_WAIT = 5
PACE = {"seconds": 1.5, "max": 30.0}  # pause between posts; doubled whenever the CDN throttles us


class TransientError(Exception):
    """A download failed in a way that is worth retrying later in the same run."""


def download(url: str, path: Path) -> None:
    """Stream the URL into the file unless it already exists.

    Rate limiting is retried with an exponential back-off, honouring a Retry-After
    header when the CDN sends one. Server errors and dropped connections get one
    quick retry; after that a TransientError leaves the post for a later attempt.
    """
    if path.exists():
        return
    tmp = path.with_suffix(".part")
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 429:
                    if attempt == RETRY_ATTEMPTS - 1:
                        reason = "HTTP 429 persists"
                        raise TransientError(reason)
                    slow_down("HTTP 429", retry_after(r.headers.get("Retry-After")) or 30 * 2**attempt)
                    continue
                if r.status_code >= 500:
                    reason = f"HTTP {r.status_code}"
                    if attempt >= QUICK_RETRIES:
                        raise TransientError(reason)
                    quick_retry(reason)
                    continue
                r.raise_for_status()
                with tmp.open("wb") as f:
                    shutil.copyfileobj(r.raw, f)
        except (requests.ConnectionError, requests.Timeout) as e:
            reason = type(e).__name__
            if attempt >= QUICK_RETRIES:
                raise TransientError(reason) from e
            quick_retry(reason)
            continue
        tmp.rename(path)
        return


def quick_retry(reason: str) -> None:
    """Wait a moment before retrying once."""
    print(f"  {reason}, retrying in {QUICK_WAIT}s", file=sys.stderr)
    time.sleep(QUICK_WAIT)


def slow_down(reason: str, wait: int) -> None:
    """Wait before a retry and stretch the pause between posts for the rest of the run."""
    PACE["seconds"] = min(PACE["seconds"] * 2, PACE["max"])
    print(f"  {reason}, waiting {wait}s before retrying (pace now {PACE['seconds']:g}s)", file=sys.stderr)
    time.sleep(wait)


def retry_after(header: str | None) -> int:
    """Return the seconds a Retry-After header asks for, 0 if absent or not a number."""
    try:
        return max(0, int(header or ""))
    except ValueError:
        return 0
