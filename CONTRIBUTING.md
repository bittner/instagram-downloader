<!--
SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Contributing

Run the tool from a checkout with `uv run insta USERNAME`; uv installs the pinned dependencies on demand. `nix develop` provides a shell with uv, just, Chromium and ffmpeg.

Development tasks are defined in the `justfile`; run `just` to list them. Install the pre-commit hooks once with `uvx prek install`; they check file hygiene and, via gitlint, that commit messages have an imperative subject of at most 72 characters and a body wrapped at 72 characters.

```sh
just test            # run the test suite with coverage
just test-pythons    # run it against all supported Python versions
just codestyle       # ruff format and lint checks, pre-commit hooks, REUSE compliance
just types           # mypy static type checking
just clean           # remove build artifacts and caches
```

Commit messages use an imperative subject line and a descriptive body. The project follows the [REUSE](https://reuse.software/) specification: every file carries SPDX copyright and license tags, and `just reuse` checks them.

The package version is derived from Git tags by setuptools-scm. To release, publish a GitHub release with a `vX.Y.Z` tag; the release workflow builds and uploads the package to PyPI.
