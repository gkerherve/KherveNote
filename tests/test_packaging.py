"""What a release build relies on: the stamped version and the bundled
TeX cache being copied where tectonic looks."""
import sys
from pathlib import Path

from khervenote import __version__, compiler, mainwindow


def test_version_from_checkout_has_three_parts():
    # A local release build leaves its stamped khervenote/VERSION behind.
    if (Path(mainwindow.__file__).with_name("VERSION")).is_file():
        import pytest
        pytest.skip("a build's stamped VERSION file is present")
    v = mainwindow.version_string()
    assert v.startswith(__version__ + ".")
    assert "+" in v


def test_stamped_version_file_wins(tmp_path, monkeypatch):
    pkg = tmp_path / "khervenote"
    pkg.mkdir()
    (pkg / "VERSION").write_text("9.9.42+abcdef0\n")
    monkeypatch.setattr(mainwindow, "__file__", str(pkg / "mainwindow.py"))
    assert mainwindow.version_string() == "9.9.42+abcdef0"


def test_seed_copies_missing_files_only(tmp_path, monkeypatch):
    meipass = tmp_path / "bundle"
    src = meipass / "khervenote" / "tectonic_cache"
    (src / "files").mkdir(parents=True)
    (src / "files" / "a.sty").write_text("new")
    (src / "files" / "b.sty").write_text("new")
    dest = tmp_path / "cache"
    (dest / "files").mkdir(parents=True)
    (dest / "files" / "a.sty").write_text("user's")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(compiler, "find_tectonic", lambda: "tectonic")
    monkeypatch.setattr(compiler, "tectonic_cache_dir", lambda t: dest)
    assert compiler.seed_tectonic_cache() == 1
    assert (dest / "files" / "a.sty").read_text() == "user's"
    assert (dest / "files" / "b.sty").read_text() == "new"


def test_no_seed_from_source():
    assert compiler.bundled_cache() is None
    assert compiler.seed_tectonic_cache() == 0


def test_cache_dir_is_the_root_not_bundles(monkeypatch, tmp_path):
    import subprocess

    class P:
        returncode = 0
        stdout = str(tmp_path / "Tectonic" / "bundles") + "\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: P())
    assert compiler.tectonic_cache_dir("tectonic") == tmp_path / "Tectonic"
