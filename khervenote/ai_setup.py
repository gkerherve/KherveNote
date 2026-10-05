# KherveNote — setting up the local AI
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""AI ▸ Set up the local AI: is Ollama there, where to get it, which
model to install for notes, and how the models differ — with a button to
install one."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import local_ai, theme

DOWNLOAD_URL = "https://ollama.com/download"
LIBRARY_URL = "https://ollama.com/library/"

#: (model, size on disk, who makes it, what it is good for)
RECOMMENDED = (
    ("qwen3.5:4b", "3.4 GB", "Qwen — Alibaba",
     "Recommended. The best all-rounder for notes: good summaries and rewriting, "
     "works well in many languages (English, French, German, Chinese…), and copes "
     "with long documents."),
    ("granite4:micro-h", "1.9 GB", "Granite — IBM",
     "Small and fast, and light on memory even with long texts. Plain, factual "
     "style; fewer languages than Qwen. A good choice on a laptop with 8 GB."),
    ("gemma3:4b", "≈ 3.3 GB", "Gemma — Google",
     "Natural, readable writing and several languages. Similar size to Qwen."),
    ("llama3.2:3b", "≈ 2 GB", "Llama — Meta",
     "Quick, with good English; weaker on long documents and other languages."),
)


class _Signals(QObject):
    progress = Signal(float, str)
    done = Signal(str)            # "" on success, else the error


class AISetupDialog(QDialog):
    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Set up the local AI")
        self.resize(820, 640)
        self._pulling = False

        intro = QLabel(
            "<p>KherveNote's AI features — rephrase, summarise, and questions about "
            "documents — use <b>Ollama</b>, a free program that runs AI models <b>on this "
            "computer</b>. Nothing is sent to the internet.</p>")
        intro.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        step1 = QLabel(
            "<h3>1. Install Ollama</h3>"
            "<p>Download it from <a href='https://ollama.com/download'>ollama.com/download</a> "
            "(Mac, Windows, Linux) and open it once — on a Mac it then runs in the menu bar. "
            "On a Mac you can also install it from Terminal with "
            "<code>brew install ollama</code>.</p>")
        step1.setWordWrap(True)
        step1.setOpenExternalLinks(True)
        get = QPushButton("Download Ollama…")
        get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DOWNLOAD_URL)))
        again = QPushButton("Check again")
        again.clicked.connect(self.refresh)
        row1 = QHBoxLayout()
        row1.addWidget(get)
        row1.addWidget(again)
        row1.addStretch(1)

        step2 = QLabel(
            "<h3>2. Install a model, and choose it</h3>"
            "<p>A model is the AI itself. Bigger models write better but are slower and "
            "need more memory — as a rough guide, keep the model under a third of the "
            "computer's memory. Each name links to its page on ollama.com, where larger "
            "and smaller versions are listed.</p>")
        step2.setWordWrap(True)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Model", "Size", "What it is good for", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar_label = QLabel()

        other = QLabel(
            "<p><i>Models made for another purpose, such as the <b>xps-expert</b> models "
            "built for KherveFitting, carry their own instructions and are not meant for "
            "notes.</i></p>")
        other.setWordWrap(True)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        col = QVBoxLayout(self)
        for w in (intro, self.status, step1):
            col.addWidget(w)
        col.addLayout(row1)
        col.addWidget(step2)
        col.addWidget(self.table, 1)
        col.addWidget(self.bar_label)
        col.addWidget(self.bar)
        col.addWidget(other)
        end = QHBoxLayout()
        end.addStretch(1)
        end.addWidget(close)
        col.addLayout(end)
        self.refresh()

    # state

    def _installed(self) -> list[str]:
        try:
            return local_ai.list_models()
        except local_ai.OllamaError:
            return []

    def refresh(self) -> None:
        running = local_ai.is_running()
        models = self._installed() if running else []
        current = local_ai.pick_default(models, self.settings.value("ai/ollama_model", ""))
        if not running:
            self.status.setText(f"<p style='color:{theme.hex_('red')}'>○ Ollama is not "
                                "running on this computer — install it (step 1), open it, "
                                "then press <b>Check again</b>.</p>")
        else:
            self.status.setText(
                f"<p>● Ollama is running — {len(models)} model(s) installed. "
                f"KherveNote uses: <b>{current or 'none yet'}</b>.</p>")
        self.table.setRowCount(0)
        for name, size, maker, good in RECOMMENDED:
            r = self.table.rowCount()
            self.table.insertRow(r)
            link = QLabel(f"<a href='{LIBRARY_URL}{name.split(':')[0]}'>{name}</a><br>"
                          f"<span style='color:{theme.hex_('muted')}'>{maker}</span>")
            link.setOpenExternalLinks(True)
            link.setContentsMargins(6, 4, 6, 4)
            self.table.setCellWidget(r, 0, link)
            self.table.setItem(r, 1, QTableWidgetItem(size))
            self.table.setItem(r, 2, QTableWidgetItem(good))
            self.table.setCellWidget(r, 3, self._action(name, models, current, running))
        self.table.resizeRowsToContents()

    def _action(self, name: str, models: list[str], current: str, running: bool) -> QWidget:
        if name == current:
            b = QPushButton("In use ✓")
            b.setEnabled(False)
        elif name in models:
            b = QPushButton("Use this")
            b.clicked.connect(lambda: self._use(name))
        else:
            b = QPushButton("Install")
            b.setEnabled(running and not self._pulling)
            b.clicked.connect(lambda: self._install(name))
        return b

    def _use(self, name: str) -> None:
        self.settings.setValue("ai/ollama_model", name)
        self.refresh()

    def _install(self, name: str) -> None:
        self._pulling = True
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        self.bar_label.setText(f"Installing {name}…")
        self.refresh()
        sig = _Signals(self)

        def show(frac: float, text: str) -> None:
            if frac < 0:                     # no size known yet
                self.bar.setRange(0, 0)
            else:
                self.bar.setRange(0, 1000)
                self.bar.setValue(int(frac * 1000))
            self.bar_label.setText(f"Installing {name}: {text}")

        def finished(error: str) -> None:
            self._pulling = False
            self.bar.setVisible(False)
            if error:
                self.bar_label.setText(f"Could not install {name}: {error}")
            else:
                self.bar_label.setText(f"{name} is installed.")
                self.settings.setValue("ai/ollama_model", name)
            self.refresh()
        sig.progress.connect(show)
        sig.done.connect(finished)

        def work() -> None:
            try:
                local_ai.pull(name, lambda f, t: sig.progress.emit(-1.0 if f is None else f, t))
                sig.done.emit("")
            except local_ai.OllamaError as exc:
                sig.done.emit(str(exc))
        threading.Thread(target=work, daemon=True).start()
