import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from khervenote.mainwindow import Composer


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _type(c, text):
    QTest.keyClicks(c, text)


def _shift_enter(c):
    QTest.keyClick(c, Qt.Key_Return, Qt.ShiftModifier)


def test_shift_enter_continues_and_tab_nests(app):
    c = Composer()
    _type(c, "1. one")
    _shift_enter(c)
    _type(c, "two")
    _shift_enter(c)
    QTest.keyClick(c, Qt.Key_Tab)
    _type(c, "sub")
    _shift_enter(c)
    _type(c, "sub2")
    assert c.toPlainText() == "1. one\n2. two\n  1. sub\n  2. sub2"
    QTest.keyClick(c, Qt.Key_Backtab)
    assert c.toPlainText().splitlines()[-1] == "1. sub2"


def test_empty_item_ends_the_list_and_enter_submits(app):
    c = Composer()
    got = []
    c.submitted.connect(got.append)
    _type(c, "- a")
    _shift_enter(c)
    _shift_enter(c)
    _type(c, "after")
    QTest.keyClick(c, Qt.Key_Return)
    assert got == ["- a\nafter"] and c.toPlainText() == ""


def test_toggle_marker(app):
    c = Composer()
    _type(c, "point")
    c.toggle_marker(False)
    assert c.toPlainText() == "- point"
    c.toggle_marker(True)
    assert c.toPlainText() == "1. point"
    c.toggle_marker(True)
    assert c.toPlainText() == "point"
