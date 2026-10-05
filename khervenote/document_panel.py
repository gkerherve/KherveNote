# KherveNote — attached documents in the window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""The hint that documents can be dropped into a note, and the Document
panel: a document's sections, a search through it, and the questions and
summaries the local AI writes back into the note."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import icons, theme
from .documents import Document, find


class DropHint(QLabel):
    """Shown under the note's title while the note has no documents, so
    people know they can drop one in."""

    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("\U0001F4CE  Drag a PDF, Word or PowerPoint file onto the page to add "
                         "it to this note — or click here", parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("The document appears as an icon in the note: click it to summarise "
                        "it, see its sections, find words or ask the AI about it")
        self.apply_theme()

    def apply_theme(self) -> None:
        self.setStyleSheet(f"QLabel{{color:{theme.hex_('muted')}; border:1px dashed "
                           f"{theme.hex_('border')}; border-radius:6px; padding:6px 10px;"
                           f" margin-top:6px;}}")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()


class DocumentPanel(QWidget):
    """One attached document: summarise it, its sections, find in it,
    and ask the AI about it."""

    summarise = Signal()
    summarise_all = Signal()
    summarise_section = Signal(int)
    insert_section = Signal(int)
    insert_quote = Signal(object)      # Hit
    ask = Signal(str)
    open_file = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.doc: Optional[Document] = None

        self.title = QLabel("No document")
        self.title.setWordWrap(True)
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        self.title.setFont(f)
        open_btn = QToolButton()
        open_btn.setText("Open")
        open_btn.setToolTip("Open with its own app")
        open_btn.clicked.connect(self.open_file)
        top = QHBoxLayout()
        top.addWidget(self.title, 1)
        top.addWidget(open_btn)

        self.question = QLineEdit()
        self.question.setPlaceholderText("Ask the AI about this document…")
        self.question.returnPressed.connect(self._ask)
        ask = QPushButton("Ask")
        ask.setToolTip("The answer is written into the note as a new section")
        ask.clicked.connect(self._ask)
        qrow = QHBoxLayout()
        qrow.addWidget(self.question, 1)
        qrow.addWidget(ask)
        self.summary_btn = QPushButton(icons.sparkle(), "Summarise the whole document")
        self.summary_btn.clicked.connect(self.summarise)
        self.sections_btn = QPushButton(icons.sparkle(), "Summarise every section")
        self.sections_btn.setToolTip("A summary of each section, one after the other, "
                                     "written into the note")
        self.sections_btn.clicked.connect(self.summarise_all)

        self.sections = QTreeWidget()
        self.sections.setHeaderHidden(True)
        self.sections.setColumnCount(2)
        self.sections.setRootIsDecorated(False)
        self.sections.itemDoubleClicked.connect(lambda it, _c: self._section_action(it, False))
        self.sections.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sections.customContextMenuRequested.connect(self._section_menu)
        insert = QPushButton("Insert into note")
        insert.setToolTip("Copy the selected section into the note as a new section")
        insert.clicked.connect(lambda: self._section_action(self.sections.currentItem(), False))
        summ = QPushButton("Summarise section")
        summ.clicked.connect(lambda: self._section_action(self.sections.currentItem(), True))
        srow = QHBoxLayout()
        srow.addWidget(insert)
        srow.addWidget(summ)

        self.find = QLineEdit()
        self.find.setPlaceholderText("Find words or a sentence…")
        self.find.setClearButtonEnabled(True)
        self._find_timer = QTimer(self, singleShot=True, interval=250)
        self._find_timer.timeout.connect(self._search)
        self.find.textChanged.connect(self._find_timer.start)
        self.found = QLabel("")
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.itemDoubleClicked.connect(
            lambda it: self.insert_quote.emit(it.data(Qt.UserRole)))
        self.results.setToolTip("Double-click to quote it in the note")

        col = QVBoxLayout(self)
        col.setContentsMargins(8, 8, 8, 8)
        col.addLayout(top)
        col.addWidget(self.summary_btn)
        col.addWidget(self.sections_btn)
        col.addLayout(qrow)
        col.addWidget(_caption("Sections"))
        col.addWidget(self.sections, 2)
        col.addLayout(srow)
        col.addWidget(_caption("Find"))
        col.addWidget(self.find)
        col.addWidget(self.found)
        col.addWidget(self.results, 2)
        self._enable(False)

    def _enable(self, on: bool) -> None:
        for w in (self.summary_btn, self.sections_btn, self.question, self.sections, self.find,
                  self.results):
            w.setEnabled(on)

    def set_loading(self, name: str) -> None:
        self.doc = None
        self.title.setText(f"{name}\n(reading…)")
        self.sections.clear()
        self.results.clear()
        self.found.setText("")
        self._enable(False)

    def set_failed(self, name: str, message: str) -> None:
        self.title.setText(f"{name}\n{message}")

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.title.setText(doc.name)
        self.sections.clear()
        for i, sec in enumerate(doc.sections):
            label = ("    " * (sec.level - 1)) + (sec.title or "(start)")
            it = QTreeWidgetItem([label, f"p. {sec.page}" if sec.page else ""])
            it.setData(0, Qt.UserRole, i)
            it.setForeground(1, theme.color("muted"))
            it.setToolTip(0, sec.text[:400])
            self.sections.addTopLevelItem(it)
        self.sections.resizeColumnToContents(1)
        self._enable(True)
        self._search()

    def _ask(self) -> None:
        q = self.question.text().strip()
        if q and self.doc is not None:
            self.ask.emit(q)

    def _section_action(self, item, summarise: bool) -> None:
        if item is None:
            return
        i = item.data(0, Qt.UserRole)
        (self.summarise_section if summarise else self.insert_section).emit(i)

    def _section_menu(self, pos) -> None:
        item = self.sections.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        menu.addAction("Insert into note", lambda: self._section_action(item, False))
        menu.addAction("Summarise section with the AI", lambda: self._section_action(item, True))
        menu.exec(self.sections.viewport().mapToGlobal(pos))

    def _search(self) -> None:
        self.results.clear()
        query = self.find.text().strip()
        if not query or self.doc is None:
            self.found.setText("")
            return
        hits = find(self.doc, query)
        self.found.setText(f"{len(hits)} found" + (" — double-click one to quote it"
                                                    if hits else ""))
        for h in hits:
            it = QListWidgetItem(f"{h.where}:  {h.snippet}")
            it.setData(Qt.UserRole, h)
            self.results.addItem(it)


def _caption(text: str) -> QLabel:
    lab = QLabel(text)
    f = lab.font()
    f.setBold(True)
    lab.setFont(f)
    lab.setStyleSheet(f"color:{theme.hex_('muted')}; margin-top:6px;")
    return lab
