import os

from khervenote import history
from khervenote.knote_file import save_knote
from khervenote.model import Note


def _write(path, root, text):
    n = Note.new()
    n.meta.title = "Lecture"
    n.meta.id = "abc"
    n.add_block("typed", text)
    save_knote(n, path, root)


def test_versions_are_kept_spaced_and_capped(tmp_path, monkeypatch):
    note = tmp_path / "Lecture.knote"
    _write(note, tmp_path, "first")
    os.utime(note, (1000, 1000))
    assert history.snapshot(tmp_path, "abc", note) is not None
    # Saved again a minute later: too soon for another version.
    _write(note, tmp_path, "first edit")
    os.utime(note, (1060, 1060))
    assert history.snapshot(tmp_path, "abc", note) is None
    _write(note, tmp_path, "second, longer text")
    os.utime(note, (5000, 5000))
    assert history.snapshot(tmp_path, "abc", note) is not None
    vs = history.versions(tmp_path, "abc")
    assert len(vs) == 2 and vs[0].first_line == "second, longer text"
    assert vs[0].title == "Lecture"
    monkeypatch.setattr(history, "KEEP", 3)
    for i in range(5):
        os.utime(note, (6000 + i, 6000 + i))
        history.snapshot(tmp_path, "abc", note, force=True)
    assert len(history.versions(tmp_path, "abc")) == 3


def test_restore_makes_a_new_file(tmp_path):
    note = tmp_path / "Lecture.knote"
    _write(note, tmp_path, "keep me")
    v = history.snapshot(tmp_path, "abc", note)
    _write(note, tmp_path, "overwritten")
    copy = history.restore_copy(v, tmp_path, "Lecture (restored)")
    assert copy.name == "Lecture (restored).knote" and note.exists()
    assert history.versions(tmp_path, "abc")[0].first_line == "keep me"


def test_missing_note_or_id_is_ignored(tmp_path):
    assert history.snapshot(tmp_path, "", tmp_path / "x.knote") is None
    assert history.snapshot(tmp_path, "abc", tmp_path / "missing.knote") is None
    assert history.versions(tmp_path, "nobody") == []
