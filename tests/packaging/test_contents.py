# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the distributions and check that they ship the static site files."""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = (
    "insta/static/site.css",
    "insta/static/site.js",
    "insta/templates/base.html",
    "insta/templates/overview.html",
    "insta/templates/account.html",
)


@pytest.fixture(scope="module")
def dist(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(["uv", "build", "--out-dir", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out


def test_wheel_ships_the_static_files(dist):
    (wheel,) = dist.glob("*.whl")
    with zipfile.ZipFile(wheel) as z:
        for name in STATIC:
            assert name in z.namelist()
            assert len(z.read(name)) > 100


def test_sdist_ships_the_static_files(dist):
    (sdist,) = dist.glob("*.tar.gz")
    with tarfile.open(sdist) as t:
        names = {m.name.split("/", 1)[1] for m in t.getmembers() if "/" in m.name}
    for name in STATIC:
        assert name in names


def test_installed_package_serves_the_static_files(dist, tmp_path):
    """Install the wheel into a fresh environment and build a site with it."""
    (wheel,) = dist.glob("*.whl")
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", "-q", str(venv)], check=True)
    subprocess.run(["uv", "pip", "install", "-q", "--python", str(venv), str(wheel)], check=True)
    site = tmp_path / "work" / "site" / "alice"
    site.mkdir(parents=True)
    (site / "index.json").write_text("{}")
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        [str(python), "-m", "insta", "--site-only"], cwd=tmp_path / "work", check=True, capture_output=True
    )
    assert (tmp_path / "work" / "site" / "site.css").read_text().startswith("/* SPDX")
    assert (tmp_path / "work" / "site" / "site.js").read_text().startswith("// SPDX")
