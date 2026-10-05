# KherveNote — the speech panel
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""What the microphone hears, beside the user's own notes: one line per
stretch of speech, each with the time it was said, the words being
spoken now underneath, and the links between the two — the lines said
around the paragraph being written are highlighted, and clicking a time
finds what was being written then."""
from __future__ import annotations

import html
from typing import Callable, Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMenu, QPushButton, QTextBrowser, QToolButton, QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .model import Segment


class SpeechPanel(QWidget):
    #: Put this text into the user's notes (text, session time).
    insert_requested = Signal(str, float)
    #: Show the user's notes written around this session time.
    jump_requested = Signal(float)
    #: Turn the selected speech (or all of it) into notes with the AI.
    notes_requested = Signal(str)
    fill_section_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.segments: list[Segment] = []
        self.label: Callable[[float], str] = lambda t: f"{t:.0f}"
        self._highlight: tuple[Optional[float], Optional[float]] = (None, None)

        listen = QToolButton()
        listen.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._listen = listen
        self.state = QLabel("Press Listen: what is said will be written here, line by "
                            "line, with the time.")
        self.state.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(listen)
        top.addWidget(self.state, 1)

        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self._clicked)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._menu)
        self.view.document().setDocumentMargin(8)

        self.live = QLabel("")
        self.live.setWordWrap(True)
        self.live.setVisible(False)

        notes = QPushButton(icons.sparkle(), "Make notes from the speech")
        notes.setToolTip("The AI turns what was said — the selected lines, or all of it — "
                         "into structured notes, added at the end of your note")
        notes.clicked.connect(lambda: self.notes_requested.emit(self.selected_text()))
        fill = QPushButton(icons.sparkle(), "Fill in my section")
        fill.setToolTip("The AI adds what was said during the section you are in, and "
                        "your notes miss, under a “From the speech” heading")
        fill.clicked.connect(self.fill_section_requested)
        row = QHBoxLayout()
        row.addWidget(notes)
        row.addWidget(fill)

        col = QVBoxLayout(self)
        col.setContentsMargins(8, 8, 8, 8)
        col.addLayout(top)
        col.addWidget(self.view, 1)
        col.addWidget(self.live)
        col.addLayout(row)
        self.apply_theme()

    def set_listen_action(self, action) -> None:
        self._listen.setDefaultAction(action)

    # ── content ────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self.live.setStyleSheet(f"color:{theme.hex_('muted')}; font-style:italic;"
                                f" padding:4px 2px;")
        self.render()

    def set_segments(self, segments: list[Segment], label: Callable[[float], str]) -> None:
        self.segments = segments
        self.label = label
        self._highlight = (None, None)
        self.render(follow=True)

    def add_segment(self, seg: Segment) -> None:
        bar = self.view.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 30
        if seg not in self.segments:
            self.segments.append(seg)
        self.render(follow=at_end)

    def set_live(self, text: str) -> None:
        self.live.setText(text)
        self.live.setVisible(bool(text))

    def set_state(self, text: str) -> None:
        self.state.setText(text)

    def highlight(self, start: Optional[float], end: Optional[float]) -> None:
        """Mark the lines said between *start* and *end* and bring the
        first into view."""
        if (start, end) == self._highlight:
            return
        self._highlight = (start, end)
        self.render()
        first = self._first_highlighted()
        if first is not None:
            self.view.scrollToAnchor(f"s{first}")

    def _in_highlight(self, t: float) -> bool:
        a, b = self._highlight
        return a is not None and a <= t <= (b if b is not None else t)

    def _first_highlighted(self) -> Optional[int]:
        return next((i for i, g in enumerate(self.segments) if self._in_highlight(g.t)), None)

    def render(self, follow: bool = False) -> None:
        bar = self.view.verticalScrollBar()
        keep = bar.value()
        muted, accent = theme.hex_("muted"), theme.hex_("accent")
        mark = theme.hex_("key_bg")
        rows = []
        for i, g in enumerate(self.segments):
            bg = f" style='background:{mark}'" if self._in_highlight(g.t) else ""
            rows.append(
                f"<tr{bg}><td style='white-space:nowrap; padding-right:8px; vertical-align:top'>"
                f"<a name='s{i}' href='seg:{i}' style='color:{accent}; text-decoration:none'>"
                f"{html.escape(self.label(g.t))}</a></td>"
                f"<td style='padding-bottom:4px'>{html.escape(g.text)}</td></tr>")
        if not rows:
            body = (f"<p style='color:{muted}'>Nothing has been said yet. Press "
                    "<b>Listen</b> — each line will show the time it was said. Click a "
                    "time to see what you were writing then.</p>")
        else:
            body = f"<table cellspacing='0' cellpadding='2' width='100%'>{''.join(rows)}</table>"
        self.view.setHtml(body)
        bar.setValue(bar.maximum() if follow else keep)

    def selected_text(self) -> str:
        return self.view.textCursor().selectedText().replace(" ", "\n").strip()

    # ── interaction ────────────────────────────────────────────────

    def _segment(self, href: str) -> Optional[Segment]:
        if not href.startswith("seg:"):
            return None
        i = int(href[4:])
        return self.segments[i] if 0 <= i < len(self.segments) else None

    def _clicked(self, url: QUrl) -> None:
        seg = self._segment(url.toString())
        if seg is not None:
            self.jump_requested.emit(seg.t)

    def _segment_at(self, pos) -> Optional[Segment]:
        href = self.view.anchorAt(pos)
        if href:
            return self._segment(href)
        # Anywhere on a row: the nearest time link above the click.
        cur = self.view.cursorForPosition(pos)
        block = cur.block()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fmt = it.fragment().charFormat()
                if fmt.isAnchor() and fmt.anchorHref().startswith("seg:"):
                    return self._segment(fmt.anchorHref())
                it += 1
            block = block.previous()
        return None

    def _menu(self, pos) -> None:
        seg = self._segment_at(pos)
        menu = QMenu(self)
        selected = self.selected_text()
        if selected:
            menu.addAction("Insert the selection into my notes",
                           lambda: self.insert_requested.emit(selected, seg.t if seg else 0.0))
            menu.addAction("Make notes from the selection (AI)",
                           lambda: self.notes_requested.emit(selected))
        if seg is not None:
            menu.addAction(f"Insert this line into my notes",
                           lambda: self.insert_requested.emit(seg.text, seg.t))
            menu.addAction(f"Show my notes at {self.label(seg.t)}",
                           lambda: self.jump_requested.emit(seg.t))
        if not menu.isEmpty():
            menu.addSeparator()
        menu.addAction("Copy", self.view.copy)
        menu.addAction("Select all", self.view.selectAll)
        menu.exec(self.view.viewport().mapToGlobal(pos))
