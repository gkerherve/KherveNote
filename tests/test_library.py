from datetime import datetime

import pytest

from khervenote import library
from khervenote.knote_file import save_knote
from khervenote.model import Note


def _note(root, rel, title, body="", started="2026-10-05T09:00:00"):
    n = Note.new()
    n.meta.title, n.meta.started = title, started
    if body:
        n.add_block("typed", body)
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    save_knote(n, path, root)
    return path


def test_scan_builds_the_tree_newest_first(tmp_path):
    _note(tmp_path, "a.knote", "Old", started="2026-01-01T09:00:00")
    _note(tmp_path, "b.knote", "New", started="2026-10-01T09:00:00")
    _note(tmp_path, "Physics/XPS/c.knote", "XPS day 1")
    (tmp_path / ".hidden").mkdir()
    tree = library.scan(tmp_path)
    assert [n.title for n in tree.notes] == ["New", "Old"]
    assert [f.name for f in tree.folders] == ["Physics"]
    assert tree.folders[0].folders[0].notes[0].title == "XPS day 1"


def test_search_matches_title_text_and_folders(tmp_path):
    _note(tmp_path, "Physics/x.knote", "Lecture", body="Shirley background")
    _note(tmp_path, "Chem/y.knote", "Kinetics", body="rate law")
    tree = library.scan(tmp_path)
    hit = library.filter_tree(tree, "shirley")
    assert [f.name for f in hit.folders] == ["Physics"]
    assert library.filter_tree(tree, "chem").folders[0].notes[0].title == "Kinetics"
    assert library.filter_tree(tree, "rate kinetics") is not None
    assert library.filter_tree(tree, "nothing here") is None
    assert library.filter_tree(tree, "") is tree


def test_info_is_cached_until_the_file_changes(tmp_path):
    p = _note(tmp_path, "a.knote", "First")
    assert library.read_info(p).title == "First"
    import os
    import time
    _note(tmp_path, "a.knote", "Second")
    os.utime(p, (time.time() + 5, time.time() + 5))
    assert library.read_info(p).title == "Second"


def test_unreadable_file_still_listed(tmp_path):
    (tmp_path / "broken.knote").write_bytes(b"not a zip")
    assert library.scan(tmp_path).notes[0].label == "broken"


def test_names_paths_and_moves(tmp_path):
    assert library.safe_name('a/b:c*?"d') == "a b c d"
    p1 = library.new_note_path(tmp_path, "XPS: intro")
    assert p1.name == "XPS intro.knote"
    p1.write_bytes(b"")
    assert library.new_note_path(tmp_path, "XPS: intro").name == "XPS intro (2).knote"
    untitled = library.new_note_path(tmp_path, "", datetime(2026, 10, 5, 14, 30))
    assert untitled.name == "Note 2026-10-05 14.30.knote"

    folder = library.make_folder(tmp_path, "Physics")
    moved = library.move(p1, folder)
    assert moved == folder / "XPS intro.knote" and moved.exists() and not p1.exists()
    with pytest.raises(ValueError):
        library.move(folder, folder)
    renamed = library.rename(folder, "Surface science")
    assert renamed.name == "Surface science" and (renamed / "XPS intro.knote").exists()


def test_untitled_notes_are_labelled_by_their_first_words(tmp_path):
    _note(tmp_path, "a.knote", "", body="Photoemission basics and the three step model of it")
    info = library.scan(tmp_path).notes[0]
    assert info.label == "Photoemission basics and the three step model of…"
