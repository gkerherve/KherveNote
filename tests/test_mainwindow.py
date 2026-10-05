import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch, tmp_path):
    from khervenote import mainwindow
    # Never read or write the user's real settings.
    ini = str(tmp_path / "settings.ini")
    QSettings(ini, QSettings.IniFormat).setValue("library/root", str(tmp_path / "lib"))
    monkeypatch.setattr(mainwindow, "QSettings",
                        lambda *a: QSettings(ini, QSettings.IniFormat))
    w = mainwindow.MainWindow()
    yield w
    w._mark_clean()
    w.session = None
    w.close()


class FakeSession:
    duration = 3.0
    stopped = False

    def stop(self):
        self.stopped = True


def _listening(win):
    s = FakeSession()
    win.session = s
    win.act_listen.setChecked(True)
    return s


def test_typing_keeps_listening_by_default(win):
    s = _listening(win)
    QTest.keyClick(win.editor, Qt.Key_Space)
    QTest.keyClick(win.editor, Qt.Key_Return)
    assert not s.stopped


def test_space_stops_listening_and_still_types(win):
    win.act_stop_on_key.setChecked(True)
    s = _listening(win)
    QTest.keyClicks(win.editor, "a")
    assert not s.stopped
    QTest.keyClick(win.editor, Qt.Key_Space)
    assert s.stopped and not win.act_listen.isChecked()
    assert win.editor.toPlainText() == "a "


def test_return_stops_listening(win):
    win.act_stop_on_key.setChecked(True)
    s = _listening(win)
    QTest.keyClick(win.editor, Qt.Key_Return)
    assert s.stopped


def test_ai_note_summary_can_be_undone(win):
    win.header.summary.setPlainText("mine")
    win._ai_done("summarise_note", None, "", ("ok", "From the AI."))
    assert win.header.summary.toPlainText() == "From the AI."
    win.header.summary.undo()
    assert win.header.summary.toPlainText() == "mine"


def test_ai_rephrase_is_one_undo_step(win):
    QTest.keyClicks(win.editor, "uh so the the photon")
    cur = win.editor.paragraph_range()
    win._ai_done("rephrase", cur, cur.selection().toPlainText(), ("ok", "The photon."))
    assert win.editor.toPlainText() == "The photon."
    win.editor.setFocus()
    win._undo()
    assert win.editor.toPlainText() == "uh so the the photon"


def test_manual_opens(win):
    from PySide6.QtWidgets import QTextBrowser
    win.show_manual()
    view = win._manual.findChild(QTextBrowser)
    assert "Sections and styles" in view.toPlainText()
    win._manual.close()


def test_a_note_saves_itself_into_the_library(win, tmp_path):
    lib = tmp_path / "lib"
    assert win.autosave() and not list(lib.glob("*.knote"))     # blank: no file
    QTest.keyClicks(win.editor, "first words")
    assert win.autosave()
    files = list(lib.glob("*.knote"))
    assert len(files) == 1 and files[0].stem.startswith("Note ")
    win.header.title.setText("XPS training")
    win._header_changed()
    win.autosave()
    assert [f.name for f in lib.glob("*.knote")] == ["XPS training.knote"]
    assert win.library.tree.topLevelItem(0).text(0) == "XPS training"


def test_new_note_goes_into_the_chosen_folder_and_switching_saves(win, tmp_path):
    from khervenote import library
    folder = library.make_folder(tmp_path / "lib", "Physics")
    QTest.keyClicks(win.editor, "note one")
    win.new_note(folder)
    QTest.keyClicks(win.editor, "note two")
    win.autosave()
    assert win.path.parent == folder
    assert len(list((tmp_path / "lib").rglob("*.knote"))) == 2
    first = next(p for p in (tmp_path / "lib").glob("*.knote"))
    win._open_from_library(first)
    assert win.editor.toPlainText() == "note one"


def test_moving_and_trashing_the_open_note(win, tmp_path):
    from khervenote import library
    QTest.keyClicks(win.editor, "x")
    win.autosave()
    old = win.path
    folder = library.make_folder(tmp_path / "lib", "Sub")
    new = library.move(old, folder)
    win._moved(old, new)
    assert win.path == new
    QTest.keyClicks(win.editor, "y")
    win.autosave()
    assert new.exists() and not old.exists()
    new.unlink()
    win._trashed(new)
    assert win.path is None and win.editor.toPlainText() == ""
    assert win.autosave() and not new.exists()


def test_date_picker_sets_the_date(win):
    from PySide6.QtCore import QDate
    win.header._pick_date(QDate(2026, 3, 14))
    assert win.header.date.text() == "14 March 2026"
    assert win.header._current_date() == QDate(2026, 3, 14)


def test_speech_goes_beside_the_notes_with_clock_times_and_links(win):
    from datetime import datetime
    win.note.meta.started = datetime(2026, 10, 5, 14, 0, 0).isoformat()
    win._on_speech("photons hit the sample", 1864.0)
    win._on_speech("electrons come out", 1880.0)
    assert [g.text for g in win.note.transcript] == ["photons hit the sample",
                                                     "electrons come out"]
    assert win.editor.toPlainText() == ""                 # not in the page
    assert "14:31:04" in win.speech.view.toPlainText()
    win.act_clock_times.setChecked(False)
    assert win._time_label(1864.0) == "31:04"
    win.act_clock_times.setChecked(True)
    assert win._time_label(1864.0) == "14:31:04"
    # A paragraph written at 14:31:30 highlights the speech of the minute before.
    win.note.meta.started = datetime(2026, 10, 5, 14, 0, 0).isoformat()
    from khervenote.editor import BlockMeta
    QTest.keyClicks(win.editor, "my note")
    win.editor.document().firstBlock().setUserData(BlockMeta(1890.0))
    win._correlate()
    assert win.speech._highlight == (1830.0, 1895.0)
    saved = win._sync_note()
    assert len(saved.transcript) == 2


def test_speech_into_the_page_option(win):
    win.act_into_page.setChecked(True)
    win.settings.setValue("speech/into_page", True)
    win._on_speech("said in the page", 5.0)
    assert win.editor.toPlainText() == "said in the page" and not win.note.transcript


def test_earlier_versions_are_kept_when_a_note_is_saved_again(win, tmp_path):
    import os

    from khervenote import history
    QTest.keyClicks(win.editor, "version one")
    win.autosave()
    path = win.path
    os.utime(path, (1000, 1000))                 # saved long ago
    win._disk_mtime = 1000
    QTest.keyClicks(win.editor, " and two")
    win.autosave()
    kept = history.versions(tmp_path / "lib", win.note.meta.id)
    assert len(kept) == 1 and kept[0].first_line == "version one"
    assert not (tmp_path / "lib" / ".history").name in [i.text(0) for i in
                                                        win.library._all_items()]


def test_a_file_changed_elsewhere_is_never_overwritten(win, tmp_path, monkeypatch):
    import os

    from khervenote.knote_file import load_knote, save_knote
    from khervenote.model import Note
    QTest.keyClicks(win.editor, "mine")
    win.autosave()
    path = win.path
    other = Note.new()
    other.add_block("typed", "written by another window")
    save_knote(other, path, tmp_path)
    os.utime(path, (path.stat().st_mtime + 30,) * 2)
    warned = []
    monkeypatch.setattr(mainwindow_qmessagebox(), "warning", lambda *a, **k: warned.append(a))
    QTest.keyClicks(win.editor, " more")
    win.autosave()
    assert warned and win.path != path
    assert load_knote(path, tmp_path / "x").sections[0].blocks[0].text == "written by another window"
    assert load_knote(win.path, tmp_path / "y").sections[0].blocks[0].text == "mine more"


def mainwindow_qmessagebox():
    from khervenote import mainwindow
    return mainwindow.QMessageBox


def test_a_new_note_is_listed_at_once(win):
    QTest.keyClicks(win.editor, "first note")
    win.new_note()
    labels = [win.library.tree.topLevelItem(i).text(0)
              for i in range(win.library.tree.topLevelItemCount())]
    assert labels[0].startswith("New note") and "first note" in labels
    QTest.keyClicks(win.editor, "second note")
    win.autosave()
    labels = [win.library.tree.topLevelItem(i).text(0)
              for i in range(win.library.tree.topLevelItemCount())]
    assert sorted(labels) == ["first note", "second note"]


def test_leaving_a_note_finishes_listening_into_that_note(win, tmp_path):
    from PySide6.QtCore import QObject, QTimer, Signal

    class Session(QObject):
        finished = Signal()
        duration, t0, engine, preview = 4.0, 0.0, None, None

        def __init__(self, path):
            super().__init__()
            self.audio_path = str(path)

        def stop(self):
            QTimer.singleShot(20, self.finished.emit)
    (win.work_dir / "assets").mkdir(exist_ok=True)
    rec = win.work_dir / "assets" / "rec-1.ogg"
    rec.write_bytes(b"ogg")
    s = Session(rec)
    s.finished.connect(lambda: win._session_done(s, "base"))
    win.session = s
    win.act_listen.setChecked(True)
    QTest.keyClicks(win.editor, "lecture")
    first = None
    win.autosave()
    first = win.path
    win.new_note()
    assert win.session is None
    from khervenote.knote_file import load_knote
    saved = load_knote(first, tmp_path / "check")
    assert [r.path for r in saved.recordings] == ["assets/rec-1.ogg"]
    assert win.note.recordings == []


def test_an_ai_answer_never_lands_in_another_note(win, monkeypatch, app):
    import threading
    import time

    from khervenote import local_ai
    monkeypatch.setattr(local_ai, "list_models", lambda: ["m"])
    go = threading.Event()
    written = []
    QTest.keyClicks(win.editor, "note A")
    win._run_ai("test", lambda model: (go.wait(5), "answer")[1], written.append)
    win.new_note()                       # leaves note A while the AI works
    go.set()
    t = time.time()
    while win._ai_busy and time.time() - t < 5:
        app.processEvents()
        time.sleep(0.01)
    assert written == [] and win.editor.toPlainText() == ""
