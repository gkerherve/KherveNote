# KherveNote — earlier versions of a note
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""File ▸ Earlier versions of this note: pick one to open as a copy."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout,
)

from .history import Version


class VersionsDialog(QDialog):
    def __init__(self, versions: list[Version], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Earlier versions of this note")
        self.resize(640, 460)
        self.chosen: Optional[Version] = None
        info = QLabel(
            "KherveNote keeps an earlier version of each note every few minutes while you "
            "work. Opening one makes a <b>new note</b> next to this one — the note you have "
            "now is not changed.")
        info.setWordWrap(True)
        self.list = QListWidget()
        for v in versions:
            what = v.title.strip() or v.first_line or "(empty)"
            it = QListWidgetItem(f"{v.when:%a %d %b %Y  %H:%M:%S}   —   {what}"
                                 f"   ({v.size // 1024 or 1} kB)")
            it.setToolTip(v.first_line)
            it.setData(Qt.UserRole, v)
            self.list.addItem(it)
        if not versions:
            self.list.addItem("No earlier versions yet — they are kept from the moment a "
                              "note is saved a second time.")
            self.list.setEnabled(False)
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Open).setText("Open as a copy")
        buttons.button(QDialogButtonBox.Open).setEnabled(bool(versions))
        buttons.accepted.connect(self._open)
        buttons.rejected.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _it: self._open())
        if versions:
            self.list.setCurrentRow(0)
        col = QVBoxLayout(self)
        col.addWidget(info)
        col.addWidget(self.list, 1)
        col.addWidget(buttons)

    def _open(self) -> None:
        item = self.list.currentItem()
        if item is not None and item.data(Qt.UserRole) is not None:
            self.chosen = item.data(Qt.UserRole)
            self.accept()
