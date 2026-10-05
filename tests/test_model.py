from datetime import datetime

import pytest

from khervenote.model import Block, Note


def test_new_note_has_one_untitled_section():
    n = Note.new(datetime(2026, 10, 5, 9, 0, 0))
    assert len(n.sections) == 1 and n.sections[0].title == ""
    assert n.meta.date == "05 October 2026"
    assert n.elapsed(datetime(2026, 10, 5, 9, 1, 30)) == 90


def test_blocks_go_into_the_current_section():
    n = Note.new()
    n.add_block("typed", "before")
    n.add_section("Kinetics", t=12)
    b = n.add_block("important", "rate law")
    assert n.current.title == "Kinetics"
    assert n.sections[1].blocks == [b]
    assert [blk.text for blk in n.sections[0].blocks] == ["before"]


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        Block(kind="video")


def test_split_moves_the_block_and_the_rest():
    n = Note.new()
    a, b, c = (n.add_block("typed", x, t=i) for i, x in enumerate("abc"))
    new = n.split_at(b.id, "Part two")
    assert [x.text for x in n.sections[0].blocks] == ["a"]
    assert new.title == "Part two" and new.t == 1
    assert [x.text for x in new.blocks] == ["b", "c"]


def test_remove_section_merges_into_previous():
    n = Note.new()
    n.add_block("typed", "a")
    s = n.add_section("S")
    n.add_block("typed", "b")
    n.remove_section(s.id)
    assert len(n.sections) == 1
    assert [x.text for x in n.sections[0].blocks] == ["a", "b"]
    n.sections[0].title = "Intro"
    n.remove_section(n.sections[0].id)
    assert len(n.sections) == 1 and n.sections[0].title == ""


def test_round_trip():
    n = Note.new()
    n.meta.title, n.meta.layout = "XPS training", "paged"
    n.summary = "short"
    n.add_block("typed", "x", t=3.14159)
    n.add_section("Two")
    n.add_block("image", "cap", path="assets/a.png")
    back = Note.from_dict(n.to_dict())
    assert back.to_dict() == n.to_dict()
    assert back.sections[0].blocks[0].t == 3.14


def test_newer_format_is_refused():
    with pytest.raises(ValueError):
        Note.from_dict({"format": 99})


def test_bad_layout_falls_back_to_continuous():
    n = Note.from_dict({"meta": {"layout": "scroll"}})
    assert n.meta.layout == "continuous"
