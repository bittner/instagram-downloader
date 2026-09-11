# Contributing

Run the tool from a checkout with `uv run insta USERNAME`; uv installs the pinned dependencies on demand. `nix develop` provides a shell with uv, Chromium and ffmpeg.

Before committing, remove Python build artifacts and caches:

```sh
uvx pyclean .
```

Commit messages use an imperative subject line and a descriptive body. The source code is licensed under GPL-3.0-or-later; every module carries an SPDX identifier.
