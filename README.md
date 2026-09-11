# instagram-downloader

Downloads all videos and reels of one or more Instagram accounts and builds a self-contained static site in `site/`, one folder per account.

## How it works

Instagram rejects scripted API clients (Instaloader, gallery-dl, yt-dlp) while a real browser session works fine. The downloader therefore drives a logged-in Chromium over the DevTools protocol: it scrolls the profile grid, harvests the post data Instagram sends to the page, and downloads the files from Instagram's CDN. Collaboration posts owned by another account are included. Re-runs only fetch new posts.

## Usage

```sh
uv run insta USERNAME
python -m http.server -d site
```

Log in to Instagram in the Chromium window on the first run.

An optional `site/USERNAME/profile.json` with an `about` text and a list of topics (name plus caption keywords) adds an "About" box to the overview and topic filters to the account page. Keywords match at the start of a word; a trailing space makes a keyword match whole words only.

`site/` is ignored here; keep it as a separate private Git repository. See [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under the GNU General Public License v3.0 or later, see [LICENSE](LICENSE).
