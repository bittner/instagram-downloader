# Contributing

Run the tool from a checkout with `uv run insta USERNAME`; uv installs the pinned dependencies on demand. `nix develop` provides a shell with uv, just, Chromium and ffmpeg.

Development tasks are defined in the `justfile`; run `just` to list them.

```sh
just test            # run the test suite with coverage
just test-pythons    # run it against all supported Python versions
just codestyle       # ruff format and lint checks
just types           # mypy static type checking
just clean           # remove build artifacts and caches
```

Commit messages use an imperative subject line and a descriptive body. The source code is licensed under GPL-3.0-or-later; every module carries an SPDX identifier.
