# Contributing

Run the tool from a checkout with `uv run insta USERNAME`; uv installs the pinned dependencies on demand.

Before committing, remove Python build artifacts and caches:

```sh
uvx pyclean .
```

## Content repository

The generated `site/` folder is not part of this repository. Track it separately as a private, local repository. The videos are ignored there; only the metadata, index and HTML pages are versioned:

```sh
cd site
git init
printf '*.mp4\n*.part\n' > .gitignore
git add .
git commit -m "Add archive"
```

After each download run, commit the changes in `site/`.
