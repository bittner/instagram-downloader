# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import runpy

import pytest

from insta import cli, download, website


@pytest.fixture
def spies(monkeypatch):
    calls = {}
    monkeypatch.setattr(download, "archive_all", lambda *a, **k: calls.setdefault("archive", (a, k)))
    monkeypatch.setattr(website, "build", lambda: calls.setdefault("build", True))
    return calls


def test_usernames_are_archived_then_site_is_built(spies, monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["insta", "alice", "bob", "--full", "--max", "3", "--browser", "/opt/brave"]
    )
    assert cli.main() == 0
    assert spies["archive"] == ((["alice", "bob"],), {"full": True, "limit": 3, "browser": "/opt/brave"})
    assert spies["build"] is True


def test_site_only_skips_the_download(spies, monkeypatch):
    monkeypatch.setattr("sys.argv", ["insta", "--site-only"])
    assert cli.main() == 0
    assert "archive" not in spies
    assert spies["build"] is True


def test_username_is_required_without_site_only(spies, monkeypatch):
    monkeypatch.setattr("sys.argv", ["insta"])
    with pytest.raises(SystemExit):
        cli.main()
    assert "archive" not in spies


def test_python_dash_m_runs_the_cli(spies, monkeypatch):
    monkeypatch.setattr("sys.argv", ["insta", "--site-only"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("insta", run_name="__main__", alter_sys=True)
    assert exit_info.value.code == 0
    assert spies["build"] is True
