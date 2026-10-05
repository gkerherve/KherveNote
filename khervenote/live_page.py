# KherveNote — the continuous live page
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""One endless page: header, then sections, each a run of blocks.

Widgets edit the model objects they were built from in place and emit
``changed``; anything that alters the structure (a new section, a split,
a deletion) goes through the main window, which changes the model and
rebuilds or appends.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget,
)

from .model import Block, Note, Section
from .serializer import format_time

#: (marker, colour) shown in the left gutter of each block kind.
_MARKERS = {
    "typed": ("", "#222222"),
    "transcript": ("…", "#7a7a7a"),
    "important": ("★", "#d96b00"),
    "question": ("?", "#1a6dd8"),
    "image": ("▣", "#4a8a4a"),
}
_PAGE_WIDTH = 860


class AutoText(QTextEdit):
    """Frameless plain-text editor that grows to fit its text."""

    edited = Signal(str)

    def __init__(self, text: str = "", parent: Optional[QWidget] = None,
                 placeholder: str = "") -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setPlaceholderText(placeholder)
        self.setPlainText(text)
        self.document().setDocumentMargin(2)
        self.textChanged.connect(self._on_change)
        self._fit()

    def _on_change(self) -> None:
        self._fit()
        self.edited.emit(self.toPlainText())

    def _fit(self) -> None:
        self.document().setTextWidth(max(50, self.viewport().width()))
        h = int(self.document().size().height()) + 4
        if h != self.height():
            self.setFixedHeight(h)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._fit()


class BlockWidget(QFrame):
    changed = Signal()
    split_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, block: Block, work_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.block = block
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        stamp = QLabel(format_time(block.t))
        stamp.setFixedWidth(52)
        stamp.setAlignment(Qt.AlignRight | Qt.AlignTop)
        stamp.setStyleSheet("color:#9a9a9a; font-size:10px; padding-top:4px;")
        row.addWidget(stamp)

        mark, color = _MARKERS[block.kind]
        marker = QLabel(mark)
        marker.setFixedWidth(14)
        marker.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        marker.setStyleSheet(f"color:{color}; font-weight:bold; padding-top:2px;")
        row.addWidget(marker)

        if block.kind == "image":
            col = QVBoxLayout()
            pic = QLabel()
            px = QPixmap(str(work_dir / block.path))
            if px.isNull():
                pic.setText(f"[missing image: {block.path}]")
            else:
                pic.setPixmap(px.scaledToWidth(min(px.width(), 560),
                                               Qt.SmoothTransformation))
            col.addWidget(pic)
            cap = QLineEdit(block.text)
            cap.setPlaceholderText("Caption")
            cap.setFrame(False)
            cap.setStyleSheet("color:#555; font-style:italic;")
            cap.textEdited.connect(self._set_text)
            col.addWidget(cap)
            row.addLayout(col, 1)
        else:
            self.editor = AutoText(block.text)
            style = {"transcript": "color:#6b6b6b;",
                     "important": "background:#fbeee2;",
                     "question": "color:#1a4f9c; font-style:italic;"}
            self.editor.setStyleSheet(
                "QTextEdit{background:transparent;%s}" % style.get(block.kind, ""))
            self.editor.edited.connect(self._set_text)
            row.addWidget(self.editor, 1)

    def _set_text(self, text: str) -> None:
        self.block.text = text
        self.changed.emit()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        menu.addAction("Start a section here",
                       lambda: self.split_requested.emit(self.block.id))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_requested.emit(self.block.id))
        menu.exec(event.globalPos())


class SectionWidget(QFrame):
    changed = Signal()
    title_changed = Signal()
    remove_requested = Signal(str)

    def __init__(self, section: Section, first: bool, parent=None) -> None:
        super().__init__(parent)
        self.section = section
        self.first = first
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 10 if first else 22, 0, 0)
        col.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(72, 0, 0, 4)
        self.title = QLineEdit(section.title)
        self.title.setFrame(False)
        self.title.setPlaceholderText(
            "Section title (optional)" if first else "Section title")
        f = QFont()
        f.setPointSize(17)
        f.setBold(True)
        self.title.setFont(f)
        self.title.setStyleSheet("color:#1a3f75; background:transparent;")
        self.title.textEdited.connect(self._set_title)
        head.addWidget(self.title, 1)
        if section.t is not None:
            t = QLabel(format_time(section.t))
            t.setStyleSheet("color:#9a9a9a;")
            head.addWidget(t)
        col.addLayout(head)
        if not first:
            rule = QFrame()
            rule.setFrameShape(QFrame.HLine)
            rule.setStyleSheet("color:#c9d6ea; margin-left:72px;")
            col.addWidget(rule)

        self.blocks = QVBoxLayout()
        self.blocks.setSpacing(0)
        col.addLayout(self.blocks)

    def _set_title(self, text: str) -> None:
        self.section.title = text
        self.changed.emit()
        self.title_changed.emit()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        label = "Clear section title" if self.first else "Remove section (keep its notes)"
        menu.addAction(label, lambda: self.remove_requested.emit(self.section.id))
        menu.exec(event.globalPos())


class HeaderWidget(QFrame):
    changed = Signal()

    def __init__(self, note: Note, parent=None) -> None:
        super().__init__(parent)
        m = note.meta
        col = QVBoxLayout(self)
        col.setContentsMargins(72, 18, 8, 6)
        self.title = QLineEdit(m.title)
        self.title.setPlaceholderText("Lecture / training title")
        self.title.setFrame(False)
        f = QFont()
        f.setPointSize(24)
        f.setBold(True)
        self.title.setFont(f)
        col.addWidget(self.title)
        row = QHBoxLayout()
        self.speaker = self._field(m.speaker, "Speaker", row)
        self.date = self._field(m.date, "Date", row)
        self.place = self._field(m.place, "Place", row)
        col.addLayout(row)
        self.summary = AutoText(note.summary, placeholder=(
            "Summary — write one, or let Claude write it (coming in v0.3)"))
        self.summary.setStyleSheet(
            "QTextEdit{background:#eef4fc; border-left:3px solid #1a6dd8;}")
        col.addWidget(self.summary)

        def sync(*_):
            m.title, m.speaker = self.title.text(), self.speaker.text()
            m.date, m.place = self.date.text(), self.place.text()
            note.summary = self.summary.toPlainText()
            self.changed.emit()
        for w in (self.title, self.speaker, self.date, self.place):
            w.textEdited.connect(sync)
        self.summary.edited.connect(sync)

    @staticmethod
    def _field(text: str, placeholder: str, row: QHBoxLayout) -> QLineEdit:
        w = QLineEdit(text)
        w.setPlaceholderText(placeholder)
        w.setFrame(False)
        w.setStyleSheet("color:#555;")
        row.addWidget(w)
        return w


class LivePage(QScrollArea):
    changed = Signal()
    titles_changed = Signal()
    split_requested = Signal(str)
    delete_requested = Signal(str)
    remove_section_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{background:#d0d4d8; border:none;}")
        self.note: Optional[Note] = None
        self.work_dir = Path(".")
        self.section_widgets: list[SectionWidget] = []

    # ── building ───────────────────────────────────────────────────

    def rebuild(self, note: Note, work_dir: Path) -> None:
        self.note, self.work_dir = note, work_dir
        desk = QWidget()
        desk.setObjectName("desk")
        # Scoped by name: an unscoped background would paint every child
        # of the page grey too.
        desk.setStyleSheet("#desk{background:#d0d4d8;}")
        outer = QHBoxLayout(desk)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addStretch(1)
        page = QFrame()
        page.setObjectName("page")
        page.setStyleSheet("#page{background:white; border:1px solid #b8bcc1;}"
                           "QLineEdit,QTextEdit{background:transparent;}")
        page.setMaximumWidth(_PAGE_WIDTH)
        page.setMinimumWidth(420)
        outer.addWidget(page, 100)
        outer.addStretch(1)

        self._col = QVBoxLayout(page)
        self._col.setContentsMargins(0, 0, 40, 40)
        self._col.setSpacing(0)
        header = HeaderWidget(note)
        header.changed.connect(self.changed)
        self._col.addWidget(header)
        self.section_widgets = []
        for i, sec in enumerate(note.sections):
            sw = self._add_section_widget(sec, i == 0)
            for blk in sec.blocks:
                self._add_block_widget(sw, blk)
        self._col.addStretch(1)
        self.setWidget(desk)

    def _add_section_widget(self, sec: Section, first: bool) -> SectionWidget:
        sw = SectionWidget(sec, first)
        sw.changed.connect(self.changed)
        sw.title_changed.connect(self.titles_changed)
        sw.remove_requested.connect(self.remove_section_requested)
        # Before the trailing stretch, once that exists.
        self._col.insertWidget(len(self.section_widgets) + 1, sw)
        self.section_widgets.append(sw)
        return sw

    def _add_block_widget(self, sw: SectionWidget, blk: Block) -> BlockWidget:
        bw = BlockWidget(blk, self.work_dir)
        bw.changed.connect(self.changed)
        bw.split_requested.connect(self.split_requested)
        bw.delete_requested.connect(self.delete_requested)
        sw.blocks.addWidget(bw)
        return bw

    # ── live appends (no rebuild, so the scroll position holds) ────

    def _at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum() - 60

    def _follow(self, was_at_bottom: bool) -> None:
        if was_at_bottom:
            QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()))

    def append_block(self, blk: Block) -> None:
        follow = self._at_bottom()
        self._add_block_widget(self.section_widgets[-1], blk)
        self._follow(follow)

    def append_section(self, sec: Section) -> None:
        follow = self._at_bottom()
        sw = self._add_section_widget(sec, False)
        sw.title.setFocus()
        self._follow(follow)

    def scroll_to_section(self, index: int) -> None:
        if 0 <= index < len(self.section_widgets):
            sw = self.section_widgets[index]
            top = sw.mapTo(self.widget(), sw.rect().topLeft()).y()
            self.verticalScrollBar().setValue(top - 8)
