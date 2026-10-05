import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from khervenote import permissions


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_from_source_skips_qt_and_runs(app, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(QApplication, "checkPermission",
                        lambda *a: pytest.fail("Qt permission API used from source"))
    ran = []
    permissions.with_permission("microphone", None, lambda: ran.append(1))
    assert ran == [1]


def test_bundled_refusal_asks_once_and_stops(app, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    asked, warned, ran = [], [], []

    class Answer:
        def status(self):
            return Qt.PermissionStatus.Denied
    monkeypatch.setattr(QApplication, "checkPermission",
                        lambda self, p: Qt.PermissionStatus.Undetermined)
    monkeypatch.setattr(QApplication, "requestPermission",
                        lambda self, p, ctx, cb: (asked.append(1), cb(Answer())))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(1))
    permissions.with_permission("microphone", None, lambda: ran.append(1))
    assert asked == [1] and warned == [1] and ran == []
