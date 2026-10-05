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


def test_space_stops_listening_and_still_types(win):
    s = _listening(win)
    QTest.keyClicks(win.editor, "a")
    assert not s.stopped
    QTest.keyClick(win.editor, Qt.Key_Space)
    assert s.stopped and not win.act_listen.isChecked()
    assert win.editor.toPlainText() == "a "


def test_return_stops_listening(win):
    s = _listening(win)
    QTest.keyClick(win.editor, Qt.Key_Return)
    assert s.stopped


def test_option_keeps_listening_while_typing(win):
    win.act_stop_on_key.setChecked(False)
    s = _listening(win)
    QTest.keyClick(win.editor, Qt.Key_Space)
    QTest.keyClick(win.editor, Qt.Key_Return)
    assert not s.stopped


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
