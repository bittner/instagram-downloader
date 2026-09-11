# Project development tasks
# Run 'just' or 'just --list' to see all available commands.

set ignore-comments := true

# Show this usage screen (default)
@help:
    just --list --unsorted

# Run code style checks and the test suite on all supported Python versions
[group('lifecycle')]
all: codestyle types test-pythons clean

# Remove build artifacts and reports (use -v for verbose, -n for dry-run)
[group('lifecycle')]
clean *args:
    uvx pyclean . {{ args }} --debris all --erase .coverage coverage.xml 'dist/*' dist --yes

# Check Python dependencies are up-to-date (uv.lock)
[group('lifecycle')]
requirements:
    uvx uv lock --upgrade
    git diff --color --exit-code uv.lock

# Run all code style checks (format, lint)
[group('codestyle')]
codestyle: format lint

# Check Python code style (use -- to apply, --diff to preview)
[group('codestyle')]
format *args=('--check'):
    uvx ruff format {{ args }}

# Lint the Python code (use -- for details, --fix to autocorrect)
[group('codestyle')]
lint *args=('--statistics'):
    uvx ruff check {{ args }}

# Static type checking (use --pretty for error details)
[group('safety')]
types *args:
    uv run --extra=mypy mypy insta {{ args }}

# Run the test suite and show coverage
[group('tests')]
test: pytest coverage

# Run pytest (use -q for silent, -v for verbose, -s for debug, -x to stop on error)
[group('tests')]
pytest *args:
    uv run --extra=unittest coverage run -m pytest {{ args }}

# Run the test suite against the given Python versions (default: all supported)
[group('tests')]
test-pythons *v='3.10 3.11 3.12 3.13 3.14':
    set -e; for py in {{ v }}; do echo "--- Python $py"; UV_PYTHON=$py just pytest -q; done
    just coverage

# Display test coverage report
[group('tests')]
coverage:
    uvx coverage[toml] report

# Build the Python package and check its metadata renders for PyPI
[group('release')]
package *args:
    uv build {{ args }}
    uvx twine check dist/*.whl dist/*.tar.gz

# Verify the package version is the same as the Git tag
[group('release')]
ensure_version_matches tag:
    uv run python -c '\
    from importlib.metadata import version ;\
    ver = version("instagram-offline") ;\
    tag = "{{ tag }}".removeprefix("v") ;\
    error = f"`{ver}` != `{tag}`" ;\
    abort = f"Package version does not match the Git tag ({error}). ABORTING." ;\
    raise SystemExit(0 if ver and tag and ver == tag else abort)'

# Build and upload the package to PyPI (use UV_PUBLISH_URL to target a different index)
[group('release')]
publish: package
    just ensure_version_matches ${GIT_TAG}
    uv publish
