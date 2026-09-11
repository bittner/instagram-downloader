# Contributing

Run the tool from a checkout with `uv run insta USERNAME`; uv installs the pinned dependencies on demand.

Before committing, remove Python build artifacts and caches:

```sh
uvx pyclean .
```

## Content repository

The generated `site/` folder is not part of this repository. Track it separately as a private, local repository with the videos in git-lfs:

```sh
cd site
git init
git lfs install --local
git lfs track '*.mp4'
git add .gitattributes .
git commit -m "Add archive"
```

After each download run, commit the changes in `site/`.
