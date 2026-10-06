# KherveNote — setting up the local AI
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""AI ▸ Set up the local AI: is Ollama there, where to get it, which
model to install for notes, and how the models differ — with a button to
install one."""
from __future__ import annotations

import os
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

#: (model, GB on disk, who makes it, what it is good for) — sizes from
#: ollama.com (October 2026), smallest last within each tier.
RECOMMENDED = (
    ("qwen3.5:9b", 6.6, "Qwen 3.5 — Alibaba",
     "The best for notes if the computer has 16 GB: clearly better summaries and "
     "rewriting than the 4b, many languages, long documents."),
    ("gemma4:e4b", 6.6, "Gemma 4 — Google",
     "Google's newest small model: natural writing, many languages; can read images too."),
    ("ministral-3:8b", 6.0, "Ministral 3 — Mistral AI",
     "From a French company: strong in French and other European languages."),
    ("aya-expanse:8b", 5.1, "Aya Expanse — Cohere",
     "Made for 23 languages — a good choice when talks are not in English."),
    ("gemma4:e2b", 4.6, "Gemma 4 — Google", "The lighter Gemma 4: quicker, still good."),
    ("granite4:7b-a1b-h", 4.2, "Granite 4 — IBM",
     "A bigger Granite that stays very fast; plain, factual style."),
    ("qwen3.5:4b", 3.3, "Qwen 3.5 — Alibaba",
     "The best small all-rounder: good summaries and rewriting, many languages. "
     "Fine on 8 GB."),
    ("ministral-3:3b", 3.0, "Ministral 3 — Mistral AI", "Small and quick, good French."),
    ("phi4-mini", 2.5, "Phi-4 mini — Microsoft", "Small and quick; decent summaries."),
    ("llama3.2:3b", 2.0, "Llama 3.2 — Meta",
     "Quick, with good English; weaker on long documents and other languages."),
    ("granite4:micro-h", 1.9, "Granite 4 micro — IBM",
     "The smallest here: fast and light even on long texts; plain style, mostly English."),
)


def memory_gb() -> float:
    """This computer's memory, for saying which models fit."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (ValueError, OSError, AttributeError):
        return 0.0


def fits(size_gb: float, memory: float) -> bool:
    # The model, Whisper, the app and the system share the memory; a
    # model over ~40 % of it makes everything crawl.
    return memory <= 0 or size_gb <= 0.42 * memory


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
            "need more memory; each is marked <i>fits this computer</i> or <i>needs more "
            f"memory</i> for this computer's {memory_gb():.0f} GB. Installing two or three "
            "and comparing them on a real note is the best way to choose. Each name links "
            "to its page on ollama.com.</p>"
            "<p><i>Too big for most laptops: gpt-oss:20b (OpenAI, 14 GB), "
            "mistral-small3.2 (15 GB), qwen3.6 / qwen3.8 (18 GB and up) — they need 32 GB "
            "or more.</i></p>")
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
        memory = memory_gb()
        for name, size, maker, good in RECOMMENDED:
            r = self.table.rowCount()
            self.table.insertRow(r)
            ok = fits(size, memory)
            link = QLabel(f"<a href='{LIBRARY_URL}{name.split(':')[0]}'>{name}</a><br>"
                          f"<span style='color:{theme.hex_('muted')}'>{maker}</span>")
            link.setOpenExternalLinks(True)
            link.setContentsMargins(6, 4, 6, 4)
            self.table.setCellWidget(r, 0, link)
            size_item = QTableWidgetItem(f"{size:g} GB\n" + ("fits this computer" if ok
                                                              else "needs more memory"))
            size_item.setForeground(theme.color("text" if ok else "muted"))
            self.table.setItem(r, 1, size_item)
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
