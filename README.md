# instagram-offline [![Vibe coded responsibly][badge]][contributing]

Downloads all videos and reels of one or more Instagram accounts and builds a self-contained static site in `site/`, one folder per account.

## How it works

Instagram rejects scripted API clients (Instaloader, gallery-dl, yt-dlp) while a real browser session works fine. The downloader therefore drives a logged-in Chromium-based browser over the DevTools protocol: it scrolls the profile grid, harvests the post data Instagram sends to the page, and downloads the files from Instagram's CDN. Collaboration posts owned by another account are included. Re-runs only fetch new posts.

## Usage

```sh
uvx instagram-offline USERNAME
python -m http.server -d site
```

From a checkout, `uv run insta USERNAME` does the same.

Log in to Instagram in the browser window on the first run.

Any Chromium-based browser works: Chromium, Chrome, Brave, Edge, Vivaldi or Opera are found automatically on Linux, macOS and Windows; `--browser EXECUTABLE` or `INSTA_BROWSER` selects one explicitly. Without any, Playwright's own Chromium is downloaded on first use. Firefox and Safari are not supported, as they lack the DevTools protocol the tool relies on.

An optional `site/USERNAME/profile.json` with an `about` text and a list of topics (name plus caption keywords) adds an "About" box to the overview and topic filters to the account page. Keywords match at the start of a word; a trailing space makes a keyword match whole words only.

### Versioning the content

`site/` is ignored by this repository. To track changes of the archive, keep it as a separate, private Git repository that ignores the video files and versions only the metadata, index and HTML pages:

```sh
cd site
git init
printf '*.mp4\n*.part\n' > .gitignore
git add .
git commit -m "Add archive"
```

After each download run, commit the changes in `site/`.

## Legal notice

This project is not affiliated with, endorsed by or connected to Instagram or Meta Platforms, Inc. in any way. This software is provided for research and educational purposes only. Downloading content from Instagram in an automated way, in particular with a logged-in account, may violate Instagram's Terms of Use and Meta's platform policies and may result in restrictions or termination of the account used. All downloaded content remains the intellectual property of its respective creators and rights holders. Whether making a copy for private use is permitted depends on the copyright law of your jurisdiction; distributing, publishing or otherwise making the downloaded content or the generated website available to the public without the rights holders' permission constitutes copyright infringement and may violate personality, image and data-protection rights.

You are solely responsible for ensuring that your use of this software complies with all applicable laws, regulations and contractual terms. The authors and contributors accept no liability for any claims, damages or other liability arising from the use of this software or the content obtained with it. Nothing in this document constitutes legal advice.

Licensed under the GNU General Public License v3.0 or later, see [LICENSE](LICENSE).

[badge]: https://img.shields.io/badge/vibe_coded-responsibly-ff69b4?logo=claude&logoColor=white
[contributing]: CONTRIBUTING.md
