# KherveNote — choosing which speech goes with a section
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""People write a section heading after they have heard what it is
about, often minutes later, so the speech that belongs to a section
starts before its heading was written.  This window shows the suggested
stretch of speech as From / To clock times, highlights it in the Speech
panel as it changes, and lets the user take their own selection."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QTime, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QTimeEdit, QVBoxLayout,
)

from .model import Note, Segment


class SpeechRangeDialog(QDialog):
    #: The range being shown, as session times, so the panel can follow.
    range_changed = Signal(float, float)

    def __init__(self, note: Note, section: str, start: float, end: float,
                 selected: Optional[tuple[float, float]] = None, parent=None) -> None:
        super().__init__(parent)
        self.note = note
        self.setWindowTitle("Which speech goes with this section?")
        self.resize(620, 480)
        self._base = note.clock(0.0) or datetime(2000, 1, 1)
        intro = QLabel(
            f"<p>The AI will compare <b>{section or 'this part of your notes'}</b> with "
            "what was said between these times and add what your notes miss.</p>"
            "<p>The times start a little <i>before</i> the section was written, because "
            "people usually write after they have heard. Adjust them, or select lines in "
            "the Speech panel first and use those.</p>")
        intro.setWordWrap(True)
        self.start = QTimeEdit()
        self.end = QTimeEdit()
        for w, t in ((self.start, start), (self.end, end)):
            w.setDisplayFormat("HH:mm:ss")
            w.setTime(self._qtime(t))
            w.timeChanged.connect(self._update)
        form = QFormLayout()
        form.addRow("From", self.start)
        form.addRow("To", self.end)
        self.count = QLabel()
        self.lines = QListWidget()
        mine = QPushButton("Use the lines I selected")
        mine.setEnabled(selected is not None)
        if selected is not None:
            mine.clicked.connect(lambda: self.set_range(*selected))
        whole = QPushButton("All the speech")
        whole.clicked.connect(lambda: self.set_range(
            note.transcript[0].t if note.transcript else 0.0,
            note.transcript[-1].t if note.transcript else 0.0))
        row = QHBoxLayout()
        row.addWidget(mine)
        row.addWidget(whole)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Fill in the section")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok = buttons.button(QDialogButtonBox.Ok)
        col = QVBoxLayout(self)
        col.addWidget(intro)
        col.addLayout(form)
        col.addLayout(row)
        col.addWidget(self.count)
        col.addWidget(self.lines, 1)
        col.addWidget(buttons)
        self._update()

    def _qtime(self, t: float) -> QTime:
        when = self._base + timedelta(seconds=max(0.0, t))
        return QTime(when.hour, when.minute, when.second)

    def _t(self, qt: QTime) -> float:
        when = self._base.replace(hour=qt.hour(), minute=qt.minute(), second=qt.second(),
                                  microsecond=0)
        if when < self._base - timedelta(hours=12):
            when += timedelta(days=1)              # a talk running past midnight
        return (when - self._base).total_seconds()

    def set_range(self, start: float, end: float) -> None:
        self.start.setTime(self._qtime(start))
        self.end.setTime(self._qtime(end))

    @property
    def span(self) -> tuple[float, float]:
        # Whole seconds on screen: include all of the last second shown.
        return self._t(self.start.time()), self._t(self.end.time()) + 0.999

    def segments(self) -> list[Segment]:
        a, b = self.span
        return self.note.speech_between(a, b)

    def _update(self, *_) -> None:
        segs = self.segments()
        self.count.setText(f"{len(segs)} line(s) of speech" if segs else
                           "No speech between these times.")
        self.lines.clear()
        for g in segs:
            self.lines.addItem(f"{self.note.time_label(g.t)}  {g.text}")
        self._ok.setEnabled(bool(segs))
        self.range_changed.emit(*self.span)
