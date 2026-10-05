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


def test_recordings_round_trip_and_count_as_assets():
    from khervenote.model import Recording
    n = Note.new()
    n.recordings.append(Recording("assets/rec-1.ogg", t0=12.5, duration=60))
    back = Note.from_dict(n.to_dict())
    assert back.recordings == n.recordings
    assert "assets/rec-1.ogg" in back.asset_paths()


def test_plain_text_for_the_ai():
    n = Note.new()
    n.meta.title, n.meta.date = "XPS", ""
    n.add_block("transcript", "hello all")
    n.add_section("Sources")
    n.add_block("item", "Al", numbered=True)
    n.add_block("item", "line width", level=1)
    n.add_block("important", "10 nm")
    assert n.plain_text() == ("# XPS\n(said) hello all\n\n## Sources\n1. Al\n"
                              "  - line width\nKey point: 10 nm\n")


def test_attachments_round_trip_and_are_assets():
    from khervenote.model import Attachment
    n = Note.new()
    n.attachments.append(Attachment("assets/att-1.pdf", "Handbook.pdf"))
    back = Note.from_dict(n.to_dict())
    assert back.attachments == n.attachments
    assert "assets/att-1.pdf" in back.asset_paths()
    assert "Attached: Handbook.pdf" in back.plain_text()


def test_markdown_blocks():
    from khervenote.model import markdown_blocks
    blocks = markdown_blocks(
        "# Answer\nThe **Shirley** method\nis iterative.\n\n- one\n  - sub\n1. first\n\n## More\ntext")
    assert [(b.kind, b.text, b.level, b.numbered) for b in blocks] == [
        ("heading", "Answer", 2, False),
        ("typed", "The Shirley method is iterative.", 0, False),
        ("item", "one", 0, False), ("item", "sub", 1, False), ("item", "first", 0, True),
        ("heading", "More", 3, False), ("typed", "text", 0, False)]
    assert blocks[1].marks == [[4, 7, "b"]]
