# KherveNote — user manual window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Help ▸ User manual: ``manual.md``, shown in a window.  The same file
is the manual on GitHub, so there is one text to keep up to date."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout

MANUAL = Path(__file__).with_name("manual.md")


class ManualDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("KherveNote — user manual")
        self.resize(760, 820)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.document().setDocumentMargin(18)
        view.setMarkdown(MANUAL.read_text(encoding="utf-8"))
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(view)
