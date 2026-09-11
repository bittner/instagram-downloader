# instagram-downloader

Downloads all videos and reels of one or more Instagram accounts and builds a self-contained static site in `site/`, one folder per account.

## How it works

Instagram rejects scripted API clients (Instaloader, gallery-dl, yt-dlp) while a real browser session works fine. The downloader therefore drives a logged-in Chromium over the DevTools protocol: it scrolls the profile grid, harvests the post data Instagram sends to the page, and downloads the files from Instagram's CDN. Collaboration posts owned by another account are included. Re-runs only fetch new posts.

## Usage

```sh
uv run insta cotoncri
python -m http.server -d site
```

Log in to Instagram in the Chromium window on the first run.

`site/` is ignored here; keep it as a separate private Git repository with `*.mp4` tracked by git-lfs. See [CONTRIBUTING.md](CONTRIBUTING.md).
