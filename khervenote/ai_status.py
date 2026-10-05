# KherveNote — the "AI is working" bar
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shown above the page while the local AI works: what it is doing, for
how long, the words it is writing as they come, and Cancel.  A small
model can take minutes over a long document; without this it looks as
if nothing is happening."""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from . import icons, theme


class AIStatusBar(QFrame):
    cancel = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aistatus")
        self.icon = QLabel()
        self.title = QLabel()
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        self.step = QLabel()
        self.clock = QLabel()
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)                 # busy, no end known
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        stop = QPushButton("Cancel")
        stop.clicked.connect(self.cancel)
        top = QHBoxLayout()
        top.addWidget(self.icon)
        top.addWidget(self.title)
        top.addWidget(self.step, 1)
        top.addWidget(self.clock)
        top.addWidget(stop)
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 8, 12, 8)
        col.addLayout(top)
        col.addWidget(self.bar)
        col.addWidget(self.preview)
        self._text = ""
        self._t0 = 0.0
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self._tick)
        self.setVisible(False)
        self.apply_theme()

    def apply_theme(self) -> None:
        self.setStyleSheet(f"#aistatus{{background:{theme.hex_('button')};"
                           f" border:1px solid {theme.hex_('border')}; border-radius:8px;}}")
        self.step.setStyleSheet(f"color:{theme.hex_('muted')};")
        self.clock.setStyleSheet(f"color:{theme.hex_('muted')};")
        self.preview.setStyleSheet(f"color:{theme.hex_('muted')}; font-style:italic;")
        self.icon.setPixmap(icons.sparkle().pixmap(18, 18))

    def start(self, title: str) -> None:
        self.title.setText(title)
        self.step.setText("starting the model…")
        self.preview.setText("")
        self.preview.setVisible(False)
        self._text = ""
        self._t0 = time.monotonic()
        self._tick()
        self._timer.start()
        self.setVisible(True)

    def set_step(self, text: str) -> None:
        self.step.setText(text)

    def add_text(self, piece: str) -> None:
        if not self._text:
            self.step.setText("writing…")
        self._text += piece
        tail = " ".join(self._text.split())[-260:]
        self.preview.setText(("…" if len(self._text) > 260 else "") + tail)
        self.preview.setVisible(True)

    def stop(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def _tick(self) -> None:
        s = int(time.monotonic() - self._t0)
        self.clock.setText(f"{s // 60}:{s % 60:02d}")
