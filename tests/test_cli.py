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
    args, kwargs = spies["archive"]
    assert args == (["alice", "bob"],)
    assert callable(kwargs.pop("on_progress"))
    assert kwargs == {"full": True, "limit": 3, "browser": "/opt/brave"}
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


def test_site_is_rebuilt_during_the_download_at_most_every_interval(monkeypatch):
    builds = []
    monkeypatch.setattr(website, "build", lambda quiet=False: builds.append(quiet))
    clock = iter([100.0, 100.0, 110.0, 131.0, 131.0])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(download, "archive_all", lambda *a, **k: [k["on_progress"]() for _ in range(3)])
    monkeypatch.setattr("sys.argv", ["insta", "alice"])
    assert cli.main() == 0
    assert builds == [True, True, False]  # two quiet rebuilds while downloading, one final full build


def test_throttled_runs_at_most_once_per_interval(monkeypatch):
    clock = iter([0.0, 0.0, 5.0, 31.0, 31.0])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    runs = []
    run = cli.throttled(lambda: runs.append(1), 30)
    run()
    run()
    run()
    assert len(runs) == 2


def test_interrupting_the_download_still_builds_the_site(spies, monkeypatch, capsys):
    def interrupted(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(download, "archive_all", interrupted)
    monkeypatch.setattr("sys.argv", ["insta", "alice"])
    assert cli.main() == 130
    assert spies["build"] is True
    assert "rerun to resume" in capsys.readouterr().err


def test_all_updates_every_archived_account(spies, monkeypatch, tmp_path):
    monkeypatch.setattr(download, "SITE", tmp_path)
    for name in ("zoe", "alice", "stray"):
        (tmp_path / name).mkdir()
    (tmp_path / "zoe" / "index.json").write_text("{}")
    (tmp_path / "alice" / "index.json").write_text("{}")
    monkeypatch.setattr("sys.argv", ["insta", "--all"])
    assert cli.main() == 0
    assert spies["archive"][0] == (["alice", "zoe"],)


def test_all_rejects_usernames_and_an_empty_site(spies, monkeypatch, tmp_path):
    monkeypatch.setattr(download, "SITE", tmp_path)
    monkeypatch.setattr("sys.argv", ["insta", "--all", "alice"])
    with pytest.raises(SystemExit):
        cli.main()
    monkeypatch.setattr("sys.argv", ["insta", "--all"])
    with pytest.raises(SystemExit):
        cli.main()
    assert "archive" not in spies


def test_version_option_prints_the_package_version(spies, monkeypatch, capsys):
    monkeypatch.setattr(website, "version", lambda: "1.2.3")
    monkeypatch.setattr("sys.argv", ["insta", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == "insta 1.2.3"
    assert "archive" not in spies
