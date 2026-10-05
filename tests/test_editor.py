import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from khervenote.editor import NoteEditor, block_kind, document_to_note, load_note
from khervenote.model import Note


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ed(app):
    clock = iter(range(100, 10000))
    return NoteEditor(lambda: float(next(clock)))


def _note():
    n = Note.new()
    n.add_block("typed", "lead in", t=1)
    n.add_section("Kinetics", t=5)
    n.add_block("typed", "rate is fast", t=6, marks=[[8, 4, "b"]])
    n.add_block("heading", "Order", t=7, level=2)
    n.add_block("item", "first", numbered=True, t=8)
    n.add_block("item", "sub", level=1, numbered=True, t=9)
    n.add_block("item", "dot", level=1, t=10)
    n.add_block("important", "key", t=11)
    n.add_block("question", "why?", t=12)
    n.add_block("transcript", "and so on\nnext line", t=13)
    return n


def test_round_trip(ed):
    n = _note()
    load_note(ed, n)
    back = document_to_note(ed.document(), Note.new())

    def strip(note):
        return [(s.title, s.t, [(b.kind, b.text, b.t, b.level, b.numbered, b.marks)
                                for b in s.blocks]) for s in note.sections]
    assert strip(back) == strip(n)


def test_typed_markers_start_lists_and_tab_nests(ed):
    load_note(ed, Note.new())
    ed.setFocus()
    QTest.keyClicks(ed, "1. ")
    QTest.keyClicks(ed, "one")
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClick(ed, Qt.Key_Tab)
    QTest.keyClicks(ed, "sub")
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClick(ed, Qt.Key_Return)      # empty item: back out one level
    QTest.keyClicks(ed, "two")
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClick(ed, Qt.Key_Return)      # empty item at top level: leave the list
    QTest.keyClicks(ed, "- dot")
    blocks = document_to_note(ed.document(), Note.new()).sections[0].blocks
    assert [(b.kind, b.text, b.level, b.numbered) for b in blocks] == [
        ("item", "one", 0, True), ("item", "sub", 1, True),
        ("item", "two", 0, True), ("item", "dot", 0, False)]
    assert ed.document().findBlockByNumber(2).textList().itemNumber(
        ed.document().findBlockByNumber(2)) == 1   # "two" continues as 2.


def test_new_section_and_enter_after_heading(ed):
    load_note(ed, Note.new())
    QTest.keyClicks(ed, "before")
    ed.new_section("Results")
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClicks(ed, "body")
    n = document_to_note(ed.document(), Note.new())
    assert [s.title for s in n.sections] == ["", "Results"]
    assert n.sections[1].blocks[0].kind == "typed"
    assert ed.headings() == [(1, "Results", 1)]


def test_new_paragraphs_get_the_clock_time(ed):
    load_note(ed, Note.new())
    QTest.keyClicks(ed, "a")
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClicks(ed, "b")
    blocks = document_to_note(ed.document(), Note.new()).sections[0].blocks
    assert blocks[0].t is not None and blocks[1].t > blocks[0].t


def test_style_change_keeps_user_bold_but_not_heading_bold(ed):
    n = Note.new()
    n.add_block("typed", "plain bold", marks=[[6, 4, "b"]])
    load_note(ed, n)
    block = ed.document().begin()
    ed.setTextCursor(QTextCursor(block))
    ed.set_style("heading", 2)
    ed.set_style("important")
    out = document_to_note(ed.document(), Note.new()).sections[0].blocks[0]
    assert out.kind == "important" and out.marks == []
    assert block_kind(ed.document().begin()) == ("important", 0)


def _texts(ed):
    out = []
    b = ed.document().begin()
    while b.isValid():
        out.append((block_kind(b)[0], b.text()))
        b = b.next()
    return out


def test_transcript_goes_to_the_end_and_joins_quick_speech(ed):
    load_note(ed, Note.new())
    ed.append_transcript("Good morning.", 1.0)
    ed.append_transcript("Today: XPS.", 5.0)
    ed.append_transcript("Much later.", 60.0)
    assert _texts(ed) == [("transcript", "Good morning. Today: XPS."),
                          ("transcript", "Much later.")]


def test_transcript_does_not_disturb_typing_in_the_last_paragraph(ed):
    load_note(ed, Note.new())
    ed.append_transcript("Speech one.", 1.0)
    cur = ed.textCursor()
    cur.movePosition(QTextCursor.End)
    ed.setTextCursor(cur)
    QTest.keyClick(ed, Qt.Key_Return)
    QTest.keyClicks(ed, "my no")
    ed.append_transcript("Speech two.", 70.0)
    QTest.keyClicks(ed, "te")
    assert _texts(ed) == [("transcript", "Speech one."), ("transcript", "Speech two."),
                          ("typed", "my note")]


def test_transcript_after_a_new_heading_keeps_the_cursor_in_it(ed):
    load_note(ed, Note.new())
    ed.append_transcript("Intro.", 1.0)
    ed.new_section("Res")
    ed.append_transcript("Results now.", 90.0)
    QTest.keyClicks(ed, "ults")
    assert _texts(ed) == [("transcript", "Intro."), ("heading", "Results"),
                          ("transcript", "Results now.")]
    n = document_to_note(ed.document(), Note.new())
    assert n.sections[1].blocks[0].t == 90.0


def test_image_survives_save_and_reopen(ed, tmp_path):
    from PySide6.QtGui import QColor, QImage

    from khervenote.knote_file import load_knote, save_knote
    work = tmp_path / "work"
    (work / "assets").mkdir(parents=True)
    img = QImage(80, 40, QImage.Format_RGB32)
    img.fill(QColor("red"))
    img.save(str(work / "assets/a.png"))
    ed.work_dir = work
    load_note(ed, Note.new())
    QTest.keyClicks(ed, "before")
    ed.insert_image("assets/a.png", img, "Slide 1")
    QTest.keyClicks(ed, "after")
    note = document_to_note(ed.document(), Note.new())
    kinds = [(b.kind, b.text, b.path) for b in note.sections[0].blocks]
    assert kinds == [("typed", "before", ""), ("image", "Slide 1", "assets/a.png"),
                     ("typed", "after", "")]
    save_knote(note, tmp_path / "n.knote", work)
    other = tmp_path / "other"
    back = load_knote(tmp_path / "n.knote", other)
    ed.work_dir = other
    load_note(ed, back)
    again = document_to_note(ed.document(), Note.new())
    assert [(b.kind, b.text, b.path) for b in again.sections[0].blocks] == kinds


def test_live_words_are_shown_but_never_part_of_the_note(ed):
    load_note(ed, Note.new())
    ed.append_transcript("Done sentence.", 1.0)
    undo = ed.document().availableUndoSteps()
    ed.show_partial("words being spo")
    block = ed.document().lastBlock()
    assert block.layout().preeditAreaText() == " words being spo"
    assert ed.document().toPlainText() == "Done sentence."
    assert ed.document().availableUndoSteps() == undo
    assert not ed.document().isModified() or undo
    ed.append_transcript("Words being spoken.", 3.0)     # final text replaces it
    assert block.layout().preeditAreaText() == ""
    assert ed.document().toPlainText() == "Done sentence. Words being spoken."


def test_live_words_after_a_heading_start_their_own_line(ed):
    load_note(ed, Note.new())
    ed.new_section("Results")
    ed.show_partial("hello")
    host = ed.document().lastBlock()
    assert host.layout().preeditAreaText() == " hello"
    ed.show_partial("")
    assert host.layout().preeditAreaText() == ""


def test_attachment_icon_in_the_page_round_trips_and_is_clickable(ed, app):
    from khervenote.model import Attachment
    load_note(ed, Note.new())
    QTest.keyClicks(ed, "before")
    ed.insert_attachment("assets/att-1.pdf", "Handbook.pdf")
    QTest.keyClicks(ed, "after")
    n = document_to_note(ed.document(), Note.new())
    assert [(b.kind, b.text, b.path) for b in n.sections[0].blocks] == [
        ("typed", "before", ""), ("attachment", "Handbook.pdf", "assets/att-1.pdf"),
        ("typed", "after", "")]
    assert n.attachments == [Attachment("assets/att-1.pdf", "Handbook.pdf")]
    load_note(ed, n)
    again = document_to_note(ed.document(), Note.new())
    assert [b.kind for b in again.sections[0].blocks] == ["typed", "attachment", "typed"]
    # Clicking the icon asks for the document.
    ed.resize(900, 600)
    ed.show()
    app.processEvents()
    block = ed.document().findBlockByNumber(1)
    rect = ed.document().documentLayout().blockBoundingRect(block)
    seen = []
    ed.attachment_action.connect(lambda *a: seen.append(a))
    QTest.mouseClick(ed.viewport(), Qt.LeftButton, pos=rect.center().toPoint()
                     - QPoint(int(rect.width() / 2) - 40, 0))
    assert seen and seen[0] == ("open", "assets/att-1.pdf", "Handbook.pdf")
    ed._remove_chip_at("assets/att-1.pdf")
    assert document_to_note(ed.document(), Note.new()).attachments == []
    ed.hide()


def test_notes_from_0_12_get_their_icons(ed):
    from khervenote.model import Attachment
    n = Note.new()
    n.add_block("typed", "x")
    n.attachments = [Attachment("assets/att-2.docx", "Plan.docx")]
    load_note(ed, n)
    back = document_to_note(ed.document(), Note.new())
    assert back.sections[0].blocks[0].kind == "attachment"


def test_a_paragraph_is_timed_when_typing_starts_not_on_return(ed):
    load_note(ed, Note.new())
    QTest.keyClicks(ed, "first")
    QTest.keyClick(ed, Qt.Key_Return)          # empty line: no time yet
    assert ed.document().lastBlock().userData() is None
    QTest.keyClicks(ed, "second")
    first, second = (b.t for b in document_to_note(ed.document(), Note.new()).sections[0].blocks)
    assert second > first
