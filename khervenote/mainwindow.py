# KherveNote — main window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: toolbar, the Notes library, the note header and the endless page."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, QEvent, QEventLoop, QFile, QFileSystemWatcher, QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QDesktopServices, QImage, QKeySequence, QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDockWidget, QInputDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox,
    QMenu, QProgressBar, QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from . import (
    __version__, compiler, documents, history, icons, khervepdf_link, library, local_ai, recovery,
    theme, vocabulary,
)
from .editor import (
    STYLES, NoteEditor, block_kind, document_to_note, insert_section, load_note,
)
from .knote_file import EXTENSION, load_knote, save_knote
from .library_panel import LibraryPanel
from .model import Note
from .audio import input_devices
from .ai_status import AIStatusBar
from .document_panel import DocumentPanel, DropHint
from .player import LinePlayer
from .speech_panel import SpeechPanel
from .speech_range import SpeechRangeDialog
from .model import Attachment, Recording, Segment, markdown_blocks
from .permissions import with_permission
from .serializer import CONTINUOUS_LIMIT_MM, format_time, to_latex
from .transcriber import DEFAULT_MODEL, LANGUAGES, MODELS, ListenSession, download_progress, missing_packages


def version_string() -> str:
    """``<major>.<minor>.<commits>+<sha7>`` from a checkout, else the
    bare version (a frozen build has no repository next to it)."""
    root = Path(__file__).resolve().parent.parent
    try:
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", *a], cwd=root, capture_output=True, text=True,
            timeout=3, stdin=subprocess.DEVNULL).stdout.strip()
        count, sha = run("rev-list", "--count", "HEAD"), run("rev-parse", "--short=7", "HEAD")
        if count and sha:
            return f"{__version__}.{count}+{sha}"
    except (OSError, subprocess.SubprocessError):
        pass
    return __version__


class NoteHeader(QFrame):
    """Title, speaker, date, place and the summary, on the page colour so
    the header and the page read as one surface."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("noteheader")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 14, 0, 0)
        col.setSpacing(2)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Title of the lecture or training")
        f = self.title.font()
        f.setPointSize(24)
        f.setBold(True)
        self.title.setFont(f)
        row = QHBoxLayout()
        self.speaker, self.date, self.place = (QLineEdit() for _ in range(3))
        for w, ph in ((self.speaker, "Speaker"), (self.date, "Date"), (self.place, "Place")):
            w.setPlaceholderText(ph)
            row.addWidget(w)
            if w is self.date:
                self.date_button = QToolButton()
                self.date_button.setToolTip("Pick the date on a calendar")
                self.date_button.setAutoRaise(True)
                self.date_button.setPopupMode(QToolButton.InstantPopup)
                self.date_button.setStyleSheet("QToolButton::menu-indicator{image:none;}")
                calendar = QCalendarWidget()
                calendar.setGridVisible(True)
                calendar.clicked.connect(self._pick_date)
                menu = QMenu(self.date_button)
                act = QWidgetAction(menu)
                act.setDefaultWidget(calendar)
                menu.addAction(act)
                menu.aboutToShow.connect(lambda c=calendar: c.setSelectedDate(self._current_date()))
                self.date_button.setMenu(menu)
                self._calendar = calendar
                row.addWidget(self.date_button)
        self.summary = QTextEdit()
        self.summary.setAcceptRichText(False)
        self.summary.setPlaceholderText("Summary")
        self.summary.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.summary.setVisible(False)
        self.summary.textChanged.connect(self._fit_summary)
        for w in (self.title, self.speaker, self.date, self.place):
            w.setFrame(False)
            w.textEdited.connect(self.changed)
        self.summary.textChanged.connect(self.changed)
        self.drop_hint = DropHint()
        self._col = col
        col.addWidget(self.title)
        col.addLayout(row)
        col.addWidget(self.drop_hint)
        col.addWidget(self.summary)

    def _current_date(self) -> QDate:
        for fmt in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                d = datetime.strptime(self.date.text().strip(), fmt)
                return QDate(d.year, d.month, d.day)
            except ValueError:
                continue
        return QDate.currentDate()

    def _pick_date(self, date: QDate) -> None:
        self.date.setText(datetime(date.year(), date.month(), date.day()).strftime("%d %B %Y"))
        self.date_button.menu().hide()
        self.changed.emit()

    def set_column(self, left: int, right: int) -> None:
        self._col.setContentsMargins(left, 14, right, 4)
        QTimer.singleShot(0, self._fit_summary)

    def _fit_summary(self) -> None:
        # Grow with the text rather than scroll inside the header.
        doc = self.summary.document()
        doc.setTextWidth(self.summary.viewport().width())
        self.summary.setFixedHeight(min(300, int(doc.size().height()) + 6))

    def apply_theme(self) -> None:
        page, muted, text = theme.hex_("page"), theme.hex_("muted"), theme.hex_("text")
        self.setStyleSheet(
            f"#noteheader{{background:{page};}}"
            f"QLineEdit{{background:{page}; color:{text}; border:none;}}"
            f"QTextEdit{{background:{theme.hex_('button')}; color:{text};"
            f" border:none; border-left:3px solid {theme.hex_('accent')};}}")
        for w in (self.speaker, self.date, self.place):
            w.setStyleSheet(f"color:{muted};")
        self.date_button.setIcon(icons.calendar())
        self.drop_hint.apply_theme()

    def load(self, note: Note) -> None:
        m = note.meta
        for w, v in ((self.title, m.title), (self.speaker, m.speaker),
                     (self.date, m.date), (self.place, m.place)):
            w.setText(v)
            w.setCursorPosition(0)        # show a long title from its start
        self.summary.blockSignals(True)
        self.summary.setPlainText(note.summary)
        self.summary.blockSignals(False)
        self.summary.setVisible(bool(note.summary.strip()))

    def store(self, note: Note) -> None:
        m = note.meta
        m.title, m.speaker = self.title.text(), self.speaker.text()
        m.date, m.place = self.date.text(), self.place.text()
        note.summary = self.summary.toPlainText()


class Page(QWidget):
    """Header over editor, sharing one column so their text lines up;
    the AI bar sits between them while the AI works."""

    def __init__(self, header: NoteHeader, editor: NoteEditor, ai_bar: QWidget) -> None:
        super().__init__()
        self.header, self.editor, self.ai_bar = header, editor, ai_bar
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(header)
        self._bar_row = QHBoxLayout()
        self._bar_row.addWidget(ai_bar)
        col.addLayout(self._bar_row)
        col.addWidget(editor, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._align)

    def _align(self) -> None:
        m = self.editor.viewportMargins()
        margin = int(self.editor.document().documentMargin())
        self.header.set_column(m.left() + margin, m.right() + margin)
        self._bar_row.setContentsMargins(m.left() + margin - 12, 6, m.right() + margin - 12, 0)


_AUTO_NAME = re.compile(r"^Note \d{4}-\d\d-\d\d \d\d\.\d\d( \(\d+\))?$")


class _Signals(QObject):
    done = Signal(object)


class _AISignals(QObject):
    done = Signal(object)
    text = Signal(str)
    step = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, path: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowIcon(icons.app_icon())
        self.resize(1200, 860)
        self.settings = QSettings("KherveTools", "KherveNote")
        self._version = version_string()
        self.path: Optional[Path] = None
        self.note = Note.new()
        self._header_dirty = False
        self._tmp = tempfile.TemporaryDirectory(prefix="khervenote-")
        self.work_dir = Path(self._tmp.name)
        self._compiling = False

        self.editor = NoteEditor(lambda: self.note.elapsed())
        self.editor.work_dir = self.work_dir
        self.editor.document().modificationChanged.connect(lambda *_: self._update_title())
        self.editor.outline_changed.connect(
            lambda: self.library.set_sections(self.editor.headings()))
        self.editor.document().contentsChanged.connect(self._schedule_autosave)
        self.editor.style_at_cursor.connect(self._show_style)
        self.editor.image_pasted.connect(self._add_image)
        self.editor.ai_requested.connect(self.run_ai)
        self.editor.installEventFilter(self)
        self._ai_busy = False
        self.header = NoteHeader()
        self.header.changed.connect(self._header_changed)
        self.ai_bar = AIStatusBar()
        self.ai_bar.cancel.connect(self._cancel_ai)
        self._ai_job = None
        self.setCentralWidget(Page(self.header, self.editor, self.ai_bar))

        self.library = LibraryPanel(Path(self.settings.value(
            "library/root", str(library.default_root()))))
        self.library.open_note.connect(self._open_from_library)
        self.library.new_note.connect(self.new_note)
        self.library.go_to_section.connect(self.editor.go_to_block)
        self.library.moved.connect(self._moved)
        self.library.trashed.connect(self._trashed)
        dock = QDockWidget("Notes", self)
        dock.setObjectName("notes")
        dock.setWidget(self.library)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.doc_panel = DocumentPanel()
        self.doc_dock = QDockWidget("Document", self)
        self.doc_dock.setObjectName("document")
        self.doc_dock.setWidget(self.doc_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.doc_dock)
        self.doc_dock.hide()
        self.speech = SpeechPanel()
        self.speech_dock = QDockWidget("Speech", self)
        self.speech_dock.setObjectName("speech")
        self.speech_dock.setWidget(self.speech)
        self.addDockWidget(Qt.RightDockWidgetArea, self.speech_dock)
        self.speech.jump_requested.connect(self.editor.go_to_time)
        self.speech.insert_requested.connect(lambda text, t: self.editor.insert_paragraph(text))
        self.speech.notes_requested.connect(self._notes_from_speech)
        self.speech.fill_section_requested.connect(self._fill_section)
        self.speech.vocabulary_changed.connect(self._set_vocabulary)
        self.player = LinePlayer(self)
        self.speech.playable = lambda t: self._audio_at(t) is not None
        self.speech.play_requested.connect(self.play_speech)
        self.player.state.connect(self.speech.show_playing)
        self.speech.pause_btn.clicked.connect(self.player.toggle)
        self.speech.stop_btn.clicked.connect(lambda: (self.player.stop(),
                                                      self.speech.show_playing(False, "")))
        self.speech.suggest_requested.connect(self.suggest_vocabulary)
        self._corr_timer = QTimer(self, singleShot=True, interval=200)
        self._corr_timer.timeout.connect(self._correlate)
        self.editor.cursorPositionChanged.connect(self._corr_timer.start)
        self.editor.time_label = self._time_label
        self._docs: dict[str, object] = {}
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._attachment_changed)
        self._watched: dict[str, str] = {}
        self._doc_att: Optional[Attachment] = None
        self.header.drop_hint.clicked.connect(self.attach_dialog)
        self.editor.attachment_action.connect(self._attachment_action)
        self.editor.outline_changed.connect(self._update_drop_hint)
        self.doc_panel.summarise_all.connect(self._doc_summarise_sections)
        self.setAcceptDrops(True)
        self.doc_panel.open_file.connect(
            lambda: self._doc_att and self._attachment_action("open", self._doc_att.path,
                                                              self._doc_att.name))
        self.doc_panel.directions.setPlainText(self.settings.value("ai/directions", ""))
        self.doc_panel.directions.textChanged.connect(lambda: self.settings.setValue(
            "ai/directions", self.doc_panel.directions_text()))
        self.doc_panel.summarise.connect(self._doc_summarise)
        self.doc_panel.summarise_section.connect(self._doc_summarise_section)
        self.doc_panel.insert_section.connect(self._doc_insert_section)
        self.doc_panel.insert_quote.connect(self._doc_quote)
        self.doc_panel.ask.connect(self._doc_ask)
        self.editor.files_dropped.connect(self.add_files)
        self._new_note_folder: Optional[Path] = None
        self._disk_mtime: Optional[float] = None
        self._unsaved_recordings: list[Path] = []
        self._autosave_timer = QTimer(self, singleShot=True, interval=2000)
        self._autosave_timer.timeout.connect(self.autosave)

        self.listen_label = QLabel()
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setTextVisible(False)
        self.meter.setFixedSize(90, 10)
        for w in (self.listen_label, self.meter):
            w.setVisible(False)
            self.statusBar().addPermanentWidget(w)
        self.session = None
        self._engine = None
        self._preview = None
        self._listen_hint = ""
        self._download_timer = QTimer(self, interval=1000)
        self._download_timer.timeout.connect(self._show_download)
        self._listen_start = 0.0
        self.clock = QLabel()
        self.statusBar().addPermanentWidget(self.clock)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

        self._build_actions()
        self.speech.set_listen_action(self.act_listen)
        self.tabifyDockWidget(self.speech_dock, self.doc_dock)
        self.speech_dock.raise_()
        self._apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._apply_theme())
        last = Path(self.settings.value("library/last", "") or "/nonexistent")
        if path:
            self.open_path(Path(path))
        elif last.is_file():
            self.open_path(last)
        else:
            self._set_note(Note.new())
        QTimer.singleShot(400, self.offer_recovery)

    # ── actions ────────────────────────────────────────────────────

    def _action(self, text, slot, shortcut=None, tip=None) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
            a.setStatusTip(tip)
        a.triggered.connect(slot)
        return a

    def _build_actions(self) -> None:
        A = self._action
        ed = self.editor
        self.act_new = A("&New note", self.new_note, QKeySequence.New)
        self.act_open = A("&Open…", self.open_dialog, QKeySequence.Open)
        self.act_save = A("&Save", self.save, QKeySequence.Save)
        self.act_save_as = A("Save &as…", self.save_as, QKeySequence.SaveAs)
        self.act_listen = A("Listen", self.toggle_listen, "Ctrl+L",
                            "Write what is said onto the page — offline Whisper, "
                            "the audio never leaves this computer (Ctrl+L)")
        self.act_listen.setCheckable(True)
        self.act_stop_on_key = A("Stop listening when I press Space or Return",
                                 lambda on: self.settings.setValue("speech/stop_on_key", on))
        self.act_stop_on_key.setCheckable(True)
        self.act_stop_on_key.setChecked(
            self.settings.value("speech/stop_on_key", False, type=bool))
        self.act_section = A("New section", lambda: ed.new_section(), "Ctrl+Return",
                             "Start a new section heading (Ctrl+Return) — or turn the "
                             "current line into one with Ctrl+1")
        self.act_undo = A("&Undo", self._undo, QKeySequence.Undo,
                          "Undo — also takes back what the AI or the microphone wrote")
        self.act_redo = A("&Redo", self._redo, QKeySequence.Redo)
        ed.undoAvailable.connect(self.act_undo.setEnabled)
        ed.redoAvailable.connect(self.act_redo.setEnabled)
        self.act_undo.setEnabled(False)
        self.act_redo.setEnabled(False)
        self.act_manual = A("&User manual", self.show_manual, QKeySequence.HelpContents,
                            "How to use KherveNote (F1)")
        self.act_bold = A("Bold", lambda: ed.set_mark("b"), QKeySequence.Bold)
        self.act_italic = A("Italic", lambda: ed.set_mark("i"), QKeySequence.Italic)
        self.act_underline = A("Underline", lambda: ed.set_mark("u"), QKeySequence.Underline)
        self.act_bullets = A("Bullets", lambda: ed.toggle_list(False), "Ctrl+Shift+8",
                             "Bullet list — or type “- ” (Ctrl+Shift+8)")
        self.act_numbers = A("Numbering", lambda: ed.toggle_list(True), "Ctrl+Shift+7",
                             "Numbered list — or type “1. ”; Tab makes 1.1 sub-items (Ctrl+Shift+7)")
        self.act_key = A("Key point", lambda: ed.set_style("important"), "Ctrl+Shift+K",
                         "Mark the paragraph as a key point (Ctrl+Shift+K)")
        self.act_question = A("Question", lambda: ed.set_style("question"), "Ctrl+Shift+Q",
                              "Mark the paragraph as a question (Ctrl+Shift+Q)")
        self.act_image = A("Image", self.insert_image, None,
                           "Insert a picture; paste (Ctrl+V) works for screenshots")
        self.act_attach = A("Insert PDF", self.attach_dialog, "Ctrl+Shift+A",
                            "Insert a PDF, Word, PowerPoint or text document into the note — "
                            "or drag the file onto the page (Ctrl+Shift+A)")
        self.act_camera = A("Take a picture", self.take_photo, "Ctrl+Shift+P",
                            "Take a picture with the camera — a whiteboard, a slide (Ctrl+Shift+P)")
        self.act_pdf = A("Export PDF", self.export_pdf, "Ctrl+E",
                         "Compile the note to PDF (Ctrl+E)")
        self.act_tex = A("Export LaTeX", self.export_tex)
        self.act_summary = A("Show &summary", self._toggle_summary)
        self.act_clock = A("Restart session &clock", self.restart_clock, None,
                           "Count times from now — use when the talk actually starts")

        self.style_box = QComboBox()
        self.style_box.setToolTip("Paragraph style — Section starts a new section")
        style_keys = {0: "Ctrl+0", 1: "Ctrl+1", 2: "Ctrl+2", 3: "Ctrl+3",
                      4: "Ctrl+Shift+K", 5: "Ctrl+Shift+Q"}
        for i, (label, _, _) in enumerate(STYLES):
            key = style_keys.get(i)
            native = QKeySequence(key).toString(QKeySequence.NativeText) if key else ""
            self.style_box.addItem(f"{label}   {native}" if native else label)
        self.style_box.activated.connect(self._pick_style)
        self._style_actions = []
        for key, idx in (("Ctrl+0", 0), ("Ctrl+1", 1), ("Ctrl+2", 2), ("Ctrl+3", 3)):
            a = A(STYLES[idx][0], lambda _=False, i=idx: self._pick_style(i), key)
            self.addAction(a)
            self._style_actions.append(a)

        layouts = QActionGroup(self)
        self.act_continuous = A("&Continuous page", lambda: self._set_layout("continuous"))
        self.act_paged = A("&A4 pages", lambda: self._set_layout("paged"))
        for a in (self.act_continuous, self.act_paged):
            a.setCheckable(True)
            layouts.addAction(a)
        self.act_transcript = A("Add what was &said (transcript) at the end",
                                lambda on: self.settings.setValue("export/transcript", on))
        self.act_transcript.setCheckable(True)
        self.act_transcript.setChecked(self.settings.value("export/transcript", False, type=bool))
        self.act_clock_times = A("Show times as the &time of day", self._toggle_clock_times, None,
                                 "Times beside your notes and the speech: the time of day "
                                 "(14:31:04), or the time since the note began (31:04)")
        self.act_clock_times.setCheckable(True)
        self.act_clock_times.setChecked(self.settings.value("view/clock_times", True, type=bool))
        self.act_into_page = A("Write the speech into the &page (instead of the side panel)",
                               lambda on: self.settings.setValue("speech/into_page", on))
        self.act_into_page.setCheckable(True)
        self.act_into_page.setChecked(self._into_page())
        self.act_times = A("Show &times in export", self._toggle_times)
        self.act_times.setCheckable(True)
        self.act_times.setChecked(self.settings.value("export/show_times", False, type=bool))

        themes = QActionGroup(self)
        self._theme_actions = {}
        for choice, label in (("system", "&System"), ("light", "&Light"), ("dark", "&Dark")):
            a = A(label, lambda _=False, c=choice: self._choose_theme(c))
            a.setCheckable(True)
            themes.addAction(a)
            self._theme_actions[choice] = a
        chosen = self.settings.value("view/theme", "system")
        self._theme_actions.get(chosen, self._theme_actions["system"]).setChecked(True)

        mb = self.menuBar()
        m = mb.addMenu("&File")
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.act_pdf)
        m.addAction(self.act_tex)
        m.addSeparator()
        m.addAction(A("Earlier &versions of this note…", self.show_versions, None,
                      "Every note keeps its earlier versions — open one as a copy"))
        m.addAction(A("Where is &KhervePDF…", self.locate_khervepdf, None,
                      "PDFs in notes open in KhervePDF; show KherveNote where it is"))
        m.addAction(A("Notes &folder…", self.choose_library, None,
                      "Where all notes are kept (the Notes panel shows this folder)"))
        m.addSeparator()
        m.addAction(A("&Quit", self.close, QKeySequence.Quit))
        m = mb.addMenu("&Edit")
        m.addAction(self.act_undo)
        m.addAction(self.act_redo)
        m.addSeparator()
        for label, slot, key in (("Cu&t", ed.cut, QKeySequence.Cut),
                                 ("&Copy", ed.copy, QKeySequence.Copy),
                                 ("&Paste", ed.paste, QKeySequence.Paste),
                                 ("Select &all", ed.selectAll, QKeySequence.SelectAll)):
            m.addAction(A(label, slot, key))
        m = mb.addMenu("F&ormat")
        for a in self._style_actions:
            m.addAction(a)
        for a in (None, self.act_key, self.act_question, None, self.act_bold, self.act_italic,
                  self.act_underline, None, self.act_bullets, self.act_numbers):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("&Note")
        for a in (self.act_listen, self.act_section, self.act_image, self.act_camera,
                  self.act_attach, None,
                  self.act_summary, self.act_clock):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("&Insert")
        m.addAction(A("&PDF, Word or PowerPoint document…", self.attach_dialog))
        m.addAction(A("&Image…", self.insert_image))
        m.addAction(A("Picture from the &camera…", self.take_photo))
        m.addSeparator()
        m.addAction(A("New &section", lambda: self.editor.new_section()))
        self._build_speech_menu(mb.addMenu("&Speech"))
        self._build_ai_menu(mb.addMenu("&AI"))
        m = mb.addMenu("&Export")
        m.addAction(self.act_continuous)
        m.addAction(self.act_paged)
        m.addAction(self.act_times)
        m.addAction(self.act_transcript)
        m = mb.addMenu("&View")
        m.addAction(self.act_clock_times)
        m.addAction(self.speech_dock.toggleViewAction())
        sub = m.addMenu("&Theme")
        for a in self._theme_actions.values():
            sub.addAction(a)
        m = mb.addMenu("&Help")
        m.addAction(self.act_manual)
        m.addAction(A("&Example notes — maths, physics, chemistry, materials",
                      self.install_examples, None,
                      "Copy eight worked lecture notes into an Examples folder and open one"))
        m.addSeparator()
        m.addAction(A("&About KherveNote", self.about))

        tb = QToolBar("Main")
        tb.setObjectName("main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        for a in (self.act_new, self.act_open, self.act_save, None, self.act_undo,
                  self.act_redo, None, self.act_listen, self.act_section, None):
            tb.addSeparator() if a is None else tb.addAction(a)
        tb.addWidget(self.style_box)
        for a in (self.act_bold, self.act_italic, self.act_underline, None, self.act_bullets,
                  self.act_numbers, None, self.act_key, self.act_question,
                  self.act_image, self.act_camera, self.act_attach, None, self.act_pdf,
                  self.act_tex, None,
                  self.act_manual):
            tb.addSeparator() if a is None else tb.addAction(a)
        ai_button = QToolButton()
        ai_button.setPopupMode(QToolButton.InstantPopup)
        ai_button.setToolTip("Local AI (Ollama): rephrase, summarise — also on right-click")
        ai_button.setText("AI")
        ai_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        ai_menu = QMenu(ai_button)
        for a in (self.act_rephrase, self.act_revise, self.act_summarise,
                  self.act_summarise_note):
            ai_menu.addAction(a)
        ai_button.setMenu(ai_menu)
        tb.insertWidget(self.act_pdf, ai_button)
        tb.insertSeparator(self.act_pdf)
        self._ai_button = ai_button
        # The things people look for first get their name next to the icon.
        for a in (self.act_listen, self.act_section, self.act_attach):
            tb.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self.toolbar = tb

    def _build_speech_menu(self, menu) -> None:
        menu.addAction(self.act_listen)
        menu.addAction(self.act_stop_on_key)
        menu.addAction(self.act_into_page)
        lead = menu.addMenu("The speech comes &before my notes by…")
        group = QActionGroup(self)
        for secs, label in ((0, "No time — I write as I hear"), (30, "30 seconds"),
                            (60, "1 minute"), (120, "2 minutes"), (300, "5 minutes")):
            a = lead.addAction(label)
            a.setCheckable(True)
            a.setChecked(secs == int(self._lead()))
            a.triggered.connect(lambda _=False, v=secs: self.settings.setValue("speech/lead", v))
            group.addAction(a)
        menu.addSeparator()
        models = menu.addMenu("&Model")
        group = QActionGroup(self)
        current = self.settings.value("speech/model", DEFAULT_MODEL)
        for name, label in MODELS:
            a = models.addAction(label)
            a.setCheckable(True)
            a.setChecked(name == current)
            a.triggered.connect(lambda _=False, n=name: self.settings.setValue("speech/model", n))
            group.addAction(a)
        langs = menu.addMenu("&Language")
        group = QActionGroup(self)
        current = self.settings.value("speech/language", "")
        for code, label in LANGUAGES:
            a = langs.addAction(label)
            a.setCheckable(True)
            a.setChecked(code == current)
            a.triggered.connect(lambda _=False, c=code: self.settings.setValue("speech/language", c))
            group.addAction(a)
        self._mic_menu = menu.addMenu("M&icrophone")
        self._mic_menu.aboutToShow.connect(self._fill_mic_menu)

    def _build_ai_menu(self, menu) -> None:
        self.act_rephrase = self._action("&Rephrase paragraph / selection",
                                         lambda: self.run_ai("rephrase"), "Ctrl+Shift+R",
                                         "Rewrite as clear sentences with the local AI (Ollama)")
        self.act_summarise = self._action("&Summarise section / selection",
                                          lambda: self.run_ai("summarise"), "Ctrl+Alt+S",
                                          "Key points of this section, by the local AI (Ollama)")
        self.act_revise = self._action("Re&vise with directions…", lambda: self.run_ai("revise"),
                                       "Ctrl+Shift+D",
                                       "Rewrite the selection (or this section) the way you say")
        self.act_summarise_note = self._action("Summarise the whole &note",
                                               lambda: self.run_ai("summarise_note"), None,
                                               "Write the summary at the top of the note")
        for a in (self.act_rephrase, self.act_revise, self.act_summarise,
                  self.act_summarise_note):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self._action("&Fill in this section from the speech", self._fill_section,
                                    None, "Add what was said during this section and your "
                                    "notes miss"))
        menu.addAction(self._action("Fill in &every section from the speech",
                                    self._fill_every_section))
        menu.addAction(self._action("Make &notes from the speech",
                                    lambda: self._notes_from_speech("")))
        menu.addSeparator()
        self._ai_model_menu = menu.addMenu("Local AI &model (Ollama)")
        menu.addAction(self._action("Set &up the local AI… (install Ollama, choose a model)",
                                    self.show_ai_setup))
        self._ai_model_menu.aboutToShow.connect(self._fill_ai_models)

    def _fill_ai_models(self) -> None:
        menu = self._ai_model_menu
        menu.clear()
        try:
            models = local_ai.list_models()
        except local_ai.OllamaError as exc:
            a = menu.addAction(str(exc))
            a.setEnabled(False)
            menu.addAction("Set up the local AI…", self.show_ai_setup)
            return
        if not models:
            menu.addAction("No models yet — install one…", self.show_ai_setup)
            return
        current = local_ai.pick_default(models, self.settings.value("ai/ollama_model", ""))
        group = QActionGroup(menu)
        for name in models:
            a = menu.addAction(name)
            a.setCheckable(True)
            a.setChecked(name == current)
            a.triggered.connect(lambda _=False, n=name: self.settings.setValue("ai/ollama_model", n))
            group.addAction(a)

    # ── local AI ───────────────────────────────────────────────────

    def run_ai(self, action: str) -> None:
        if self._ai_busy:
            self.statusBar().showMessage("The local AI is still writing…", 4000)
            return
        ed = self.editor
        if action == "rephrase":
            cur = ed.paragraph_range()
        elif action in ("summarise", "revise"):
            cur = ed.section_range()
        else:
            cur = None
        original = cur.selection().toPlainText() if cur is not None else ""
        if cur is not None and not original.strip():
            self.statusBar().showMessage("Nothing to work on here.", 4000)
            return
        text = original if cur is not None else self._sync_note().plain_text()
        if action == "summarise" and not ed.textCursor().hasSelection() and ed.section_title():
            text = f"Section: {ed.section_title()}\n\n{text}"
        if action == "revise":
            directions, ok = QInputDialog.getMultiLineText(
                self, "Revise with directions",
                "How should the AI revise it? For example: “Shorter, as bullet points”, "
                "“In French”, “Add a heading per topic”, “Explain the terms”.",
                self.settings.value("ai/revise_directions", "")
                or self.doc_panel.directions_text())
            if not ok or not directions.strip():
                return
            self.settings.setValue("ai/revise_directions", directions.strip())
            job = lambda model, txt: local_ai.revise(model, txt, directions)  # noqa: E731
        else:
            job = {"rephrase": local_ai.rephrase, "summarise": local_ai.summarise,
                   "summarise_note": local_ai.summarise_note}[action]
        title = {"rephrase": "Rephrasing", "summarise": "Summarising the section",
                 "summarise_note": "Summarising the whole note",
                 "revise": "Revising with your directions"}[action]
        self._run_ai(title, lambda model: job(model, text),
                     lambda res: self._ai_done(action, cur, original, res))

    def _run_ai(self, title: str, fn, on_result) -> None:
        """Run *fn(model)* with the local AI off the GUI thread, showing
        progress, the text as it is written and Cancel in the AI bar;
        then *on_result(("ok", text) | ("error", message))* — nothing at
        all if the user cancelled."""
        if self._ai_busy:
            self.statusBar().showMessage("The local AI is still writing…", 4000)
            return
        preferred = self.settings.value("ai/ollama_model", "")
        sig = _AISignals(self)
        job = local_ai.Job(on_text=sig.text.emit, on_step=sig.step.emit)
        sig.text.connect(self.ai_bar.add_text)
        sig.step.connect(self.ai_bar.set_step)
        self._ai_job = job
        self._ai_busy = True
        self.ai_bar.start(title)
        owner = self.note

        def done(result) -> None:
            self._ai_busy = False
            self._ai_job = None
            self.ai_bar.stop()
            if result[0] == "cancelled":
                self.statusBar().showMessage("Cancelled", 3000)
                return
            if self.note is not owner:
                # Its note was left meanwhile; never write into another one.
                self.statusBar().showMessage("The AI's answer was not written: another note "
                                             "is open now.", 6000)
                return
            on_result(result)
        sig.done.connect(done)

        def work():
            try:
                model = local_ai.pick_default(local_ai.list_models(), preferred)
                if not model:
                    raise local_ai.OllamaError("Ollama has no models yet.")
                sig.step.emit(f"{model} is reading…")
                sig.done.emit(("ok", job.run(fn, model)))
            except local_ai.Cancelled:
                sig.done.emit(("cancelled", ""))
            except local_ai.OllamaError as exc:
                sig.done.emit(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001 — surface anything to the user
                sig.done.emit(("error", f"The local AI failed: {exc}"))
        threading.Thread(target=work, daemon=True).start()

    def _cancel_ai(self) -> None:
        if self._ai_job is not None:
            self._ai_job.cancelled.set()
            self.ai_bar.set_step("cancelling…")

    def _ai_done(self, action: str, cur, original: str, result) -> None:
        self._ai_busy = False
        status, text = result
        if status != "ok" or not text.strip():
            self.statusBar().clearMessage()
            self._ai_problem(text or "The local AI returned nothing.")
            return
        if action == "summarise_note":
            # Through a cursor, not setPlainText, so Undo can take it back.
            summary = self.header.summary
            summary.setVisible(True)
            cur_s = QTextCursor(summary.document())
            cur_s.select(QTextCursor.Document)
            cur_s.insertText(text.strip())
            summary.setFocus()
        elif action == "revise":
            # Changed meanwhile (more speech, an edit): add, do not overwrite.
            self.editor.replace_with_blocks(cur, markdown_blocks(text, top_level=2),
                                            keep=cur.selection().toPlainText() != original)
        elif cur.selection().toPlainText() != original:
            # The text changed while the AI was writing (more speech, an
            # edit): put the result next to it rather than overwrite.
            self.editor.insert_summary_after(cur, text)
        elif action == "rephrase":
            self.editor.replace_range(cur, text)
        else:
            self.editor.insert_summary_after(cur, text)
        self.statusBar().showMessage("Done — Ctrl+Z undoes it", 5000)

    def _fill_mic_menu(self) -> None:
        self._mic_menu.clear()
        group = QActionGroup(self._mic_menu)
        current = self.settings.value("speech/device", "")
        for name in [""] + [n for _, n in input_devices()]:
            a = self._mic_menu.addAction(name or "System default")
            a.setCheckable(True)
            a.setChecked(name == current)
            a.triggered.connect(lambda _=False, n=name: self.settings.setValue("speech/device", n))
            group.addAction(a)

    def _set_icons(self) -> None:
        for a, icon in ((self.act_new, icons.new_note()), (self.act_open, icons.open_note()),
                        (self.act_save, icons.save_note()), (self.act_listen, icons.microphone()),
                        (self.act_section, icons.new_section()), (self.act_bold, icons.bold()),
                        (self.act_italic, icons.italic()), (self.act_underline, icons.underline()),
                        (self.act_bullets, icons.bullets()), (self.act_numbers, icons.numbering()),
                        (self.act_key, icons.star()), (self.act_question, icons.question()),
                        (self.act_image, icons.image()), (self.act_camera, icons.camera()),
                        (self.act_attach, icons.paperclip()),
                        (self.act_pdf, icons.export_pdf()),
                        (self.act_tex, icons.export_tex()), (self.act_undo, icons.undo()),
                        (self.act_redo, icons.redo()), (self.act_manual, icons.help_book())):
            a.setIcon(icon)
        self._ai_button.setIcon(icons.sparkle())

    # ── theme ──────────────────────────────────────────────────────

    def _choose_theme(self, choice: str) -> None:
        self.settings.setValue("view/theme", choice)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme.apply(QApplication.instance(), self.settings.value("view/theme", "system"))
        self._set_icons()
        self.header.apply_theme()
        self.ai_bar.apply_theme()
        modified = self.editor.document().isModified()
        self.editor.apply_theme()
        # Recolouring is not an edit.
        self.editor.document().setModified(modified)

    # ── state ──────────────────────────────────────────────────────

    def _set_note(self, note: Note, path: Optional[Path] = None) -> None:
        self.note, self.path = note, path
        self._disk_mtime = None
        (self.act_paged if note.meta.layout == "paged" else self.act_continuous).setChecked(True)
        self.editor.work_dir = self.work_dir
        self.header.load(note)
        self.player.release()
        self.speech.show_playing(False, "")
        self._docs.clear()
        self._doc_att = None
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())
        self._watched.clear()
        self.doc_dock.hide()
        load_note(self.editor, note)
        self.speech.set_segments(note.transcript, self._time_label)
        self.speech.set_vocabulary(note.meta.vocabulary)
        self._header_dirty = False
        self._update_title()
        self.library.set_pending(None if path is not None
                                 else (self._new_note_folder or self.library.root))
        self.library.set_current(path, self.editor.headings())
        if path is not None:
            self.settings.setValue("library/last", str(path))
        self.editor.setFocus()

    def _sync_note(self) -> Note:
        """The model, brought up to date with the page."""
        self.header.store(self.note)
        return document_to_note(self.editor.document(), self.note)

    @property
    def dirty(self) -> bool:
        return self._header_dirty or self.editor.document().isModified()

    def _mark_clean(self) -> None:
        self._header_dirty = False
        self.editor.document().setModified(False)
        self._update_title()

    def _header_changed(self) -> None:
        self._header_dirty = True
        self._update_title()
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if self.dirty:
            self._autosave_timer.start()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "Untitled"
        self.setWindowTitle(f"KherveNote v{self._version} — {name}{' •' if self.dirty else ''}")

    def _show_style(self, kind: str, level: int) -> None:
        for i, (_, k, lv) in enumerate(STYLES):
            if k == kind and (k != "heading" or lv == level):
                self.style_box.setCurrentIndex(i)
                return

    def _pick_style(self, index: int) -> None:
        _, kind, level = STYLES[index]
        self.editor.set_style(kind, level)
        self.editor.setFocus()

    def _tick(self) -> None:
        self.clock.setText("Session " + format_time(self.note.elapsed()))
        if self.session is not None and self.act_listen.isChecked():
            self.listen_label.setText(
                "\u25cf Listening " + format_time(self.session.duration))

    # ── listening ──────────────────────────────────────────────────

    def toggle_listen(self, on: bool) -> None:
        if on:
            self.act_listen.setChecked(False)
            self._start_listening()
        else:
            self._stop_listening()

    def _start_listening(self) -> None:
        if self.session is not None:
            return
        missing = missing_packages()
        if missing:
            QMessageBox.warning(self, "Listen", "Listening needs these Python packages:\n\n"
                                f"    pip install {' '.join(missing)}")
            return
        if not self.settings.value("speech/consent_shown", False, type=bool):
            QMessageBox.information(self, "Listen", (
                "KherveNote will record the microphone and write down what is said. "
                "Everything stays on this computer.\n\nMake sure the speaker and the "
                "audience are happy to be recorded."))
            self.settings.setValue("speech/consent_shown", True)
        with_permission("microphone", self, self._open_session)

    def _open_session(self) -> None:
        model = self.settings.value("speech/model", DEFAULT_MODEL)
        if self._engine is not None and self._engine[0] != model:
            self._engine = None
        device_name = self.settings.value("speech/device", "")
        device = next((i for i, n in input_devices() if n == device_name), None)
        t0 = self.note.elapsed() or 0.0
        # Recorded outside the note's temporary folder, so a crash cannot
        # lose it (see recovery.py).
        path = recovery.begin(self.note.meta.id, str(self.path or ""),
                              self.header.title.text().strip(), t0)
        self.session = ListenSession(str(path), t0, model,
                                     self.settings.value("speech/language", ""), device, self,
                                     engine=self._engine[1] if self._engine else None,
                                     preview=self._preview, vocabulary=self.note.meta.vocabulary)
        self.session.text.connect(self._on_speech)
        self.session.partial.connect(self._on_partial)
        self.session.status.connect(self._on_listen_status)
        self.session.level.connect(self._on_level)
        self._loudest = 0.0
        self.session.status.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.session.failed.connect(self._listen_failed)
        self.session.finished.connect(lambda s=self.session, m=model: self._session_done(s, m))
        self.act_listen.setChecked(True)
        self.act_listen.setIcon(icons.microphone(recording=True))
        for w in (self.listen_label, self.meter):
            w.setVisible(True)
        self.listen_label.setText("\u25cf Listening")
        self.listen_label.setStyleSheet(f"color:{theme.hex_('red')}; font-weight:bold;")
        self._listen_hint = "\u25cf getting the microphone ready…"
        self._show_live(self._listen_hint)
        self.speech.set_state("Listening — each line shows when it was said; the newest is at "
                              "the bottom. Click a time to see what you were writing then.")
        self.speech_dock.show()
        self.speech_dock.raise_()
        self.session.start()
        QTimer.singleShot(5000, lambda s=self.session: self._check_silence(s))

    def _into_page(self) -> bool:
        return self.settings.value("speech/into_page", False, type=bool)

    def _show_live(self, text: str) -> None:
        if self._into_page():
            self.editor.show_partial(text)
        else:
            self.speech.set_live(text)

    def _on_speech(self, text: str, t: float) -> None:
        if self._into_page():
            self.editor.append_transcript(text, t)
            return
        seg = Segment(t, text)
        self.note.transcript.append(seg)
        self.speech.add_segment(seg)
        self._header_changed()

    def _on_partial(self, text: str) -> None:
        # Between utterances keep a visible "listening" mark where the
        # words will appear, so it never looks as if nothing is happening.
        if self.session is not None:
            self._show_live(text or self._listen_hint)

    def _on_listen_status(self, message: str) -> None:
        if message.startswith("Downloading"):
            self._download_timer.start()
            self._listen_hint = "\u25cf " + message
        elif message.startswith("Loading"):
            self._listen_hint = "\u25cf loading the speech model…"
        elif message == "Listening":
            self._download_timer.stop()
            self._listen_hint = "\u25cf listening…"
        self._show_live(self._listen_hint)

    def _show_download(self) -> None:
        if self.session is None:
            self._download_timer.stop()
            return
        done, total = download_progress(self.session.model_name)
        of = f" of {total} MB" if total else " MB"
        self._listen_hint = (f"\u25cf downloading the speech model — {done}{of}, once only. "
                             "Keep talking: it is being recorded.")
        self._show_live(self._listen_hint)

    def _on_level(self, value: float) -> None:
        self._loudest = max(self._loudest, value)
        self.meter.setValue(min(100, int(value * 400)))

    def _check_silence(self, session) -> None:
        """macOS gives a blocked app a microphone that only sends zeros,
        with no error; say so instead of listening to nothing."""
        if session is not self.session or session.duration < 2 or self._loudest > 1e-6:
            return
        host = "the app you started KherveNote from (PyCharm, Terminal…)" \
            if not getattr(sys, "frozen", False) else "KherveNote"
        self.statusBar().showMessage("The microphone is sending silence", 15000)
        QMessageBox.warning(self, "Listen", (
            "The microphone is sending only silence — macOS is probably blocking "
            f"it.\n\nAllow {host} in System Settings ▸ Privacy & Security ▸ "
            "Microphone, then quit and restart it. Or pick another input under "
            "Speech ▸ Microphone."))

    def _stop_listening(self) -> None:
        self.act_listen.setChecked(False)
        self.act_listen.setIcon(icons.microphone())
        for w in (self.listen_label, self.meter):
            w.setVisible(False)
        if self.session is not None:
            self.statusBar().showMessage("Writing down the last words…", 8000)
            self._listen_hint = "\u25cf writing down the last words…"
            self.session.stop()

    def _listen_failed(self, message: str) -> None:
        self.statusBar().showMessage(message, 15000)
        if self.session is not None and self.session.duration == 0:
            self._stop_listening()
            QMessageBox.warning(self, "Listen", message)

    def offer_recovery(self) -> None:
        """Recordings a crash left behind: put each back into its note,
        keep it as a new note, or move it to the Trash."""
        busy = (Path(self.session.audio_path),) if self.session is not None else ()
        for p in recovery.pending(exclude=busy):
            when = p.when
            secs = int(recovery.duration(p.audio))
            title = p.note_title or (Path(p.note_path).stem if p.note_path else "")
            box = QMessageBox(QMessageBox.Warning, "Recovered recording", (
                "KherveNote stopped while it was recording"
                + (f" on {when:%d %B at %H:%M}" if when else "")
                + f" — {secs // 60} min {secs % 60:02d} s were kept.\n\n"
                "What was transcribed before it stopped is in the note already; this puts "
                "the recording back with it."), parent=self)
            into = None
            if p.note_path and Path(p.note_path).is_file():
                into = box.addButton(f"Add it to “{title or 'its note'}”",
                                     QMessageBox.AcceptRole)
            new = box.addButton("Keep it as a new note", QMessageBox.ActionRole)
            trash = box.addButton("Move it to the Trash", QMessageBox.DestructiveRole)
            later = box.addButton("Ask me later", QMessageBox.RejectRole)
            box.exec()
            chosen = box.clickedButton()
            if chosen is later:
                continue
            if chosen is trash:
                QFile.moveToTrash(str(p.folder))
                continue
            if not self._flush():
                return
            if chosen is into:
                self.open_path(Path(p.note_path))
            else:
                self._fresh_work_dir()
                note = Note.new(when)
                note.meta.title = f"Recovered recording — {title}" if title else \
                    "Recovered recording"
                self._new_note_folder = self.library.root
                self._set_note(note)
                self.header.load(note)
            rel = f"assets/rec-{uuid.uuid4().hex[:10]}{p.audio.suffix}"
            (self.work_dir / "assets").mkdir(exist_ok=True)
            shutil.copyfile(p.audio, self.work_dir / rel)
            t0 = p.t0 if chosen is into else 0.0
            self.note.recordings.append(Recording(rel, t0, float(secs)))
            self.speech.render()
            self._header_dirty = True
            if self.save():
                recovery.finish(p.audio)
                self.statusBar().showMessage("The recording is back in the note.", 8000)

    def _finish_listening(self) -> None:
        session = self.session
        if session is None:
            return
        self._stop_listening()
        if self.session is session:
            loop = QEventLoop()
            session.finished.connect(loop.quit)
            QTimer.singleShot(30000, loop.quit)
            loop.exec()

    def _session_done(self, session, model: str) -> None:
        if session.engine is not None:
            self._engine = (model, session.engine)
        if session.preview is not None:
            self._preview = session.preview
        self._download_timer.stop()
        self.editor.show_partial("")
        self.speech.set_live("")
        self.speech.set_state("Stopped. Press Listen to carry on — the new lines are added "
                              "below.")
        path = Path(session.audio_path)
        if path.exists() and session.duration > 0:
            rel = f"assets/rec-{uuid.uuid4().hex[:10]}{path.suffix}"
            (self.work_dir / "assets").mkdir(exist_ok=True)
            shutil.copyfile(path, self.work_dir / rel)
            self.note.recordings.append(Recording(rel, session.t0, session.duration))
            # The safe copy goes once the note holding it is saved.
            self._unsaved_recordings.append(path)
            self._header_changed()
            self.speech.render()               # its lines can now be played
        elif path.exists():
            recovery.finish(path)
        if self.session is session:
            self.session = None
        self.statusBar().showMessage("Stopped listening", 4000)

    def _toggle_summary(self) -> None:
        self.header.summary.setVisible(not self.header.summary.isVisible())
        if self.header.summary.isVisible():
            self.header.summary.setFocus()

    def restart_clock(self) -> None:
        self.note.meta.started = datetime.now().isoformat(timespec="seconds")
        self._header_changed()

    def _set_layout(self, layout: str) -> None:
        if self.note.meta.layout != layout:
            self.note.meta.layout = layout
            self._header_changed()

    def _toggle_times(self, on: bool) -> None:
        self.settings.setValue("export/show_times", on)

    # ── images ─────────────────────────────────────────────────────

    def _new_asset(self, suffix: str) -> tuple[str, Path]:
        rel = f"assets/{uuid.uuid4().hex[:10]}{suffix}"
        (self.work_dir / "assets").mkdir(exist_ok=True)
        return rel, self.work_dir / rel

    def _add_image(self, image: QImage, photo: bool = False) -> None:
        # Photos compress far better as JPEG; screenshots stay sharp as PNG.
        rel, dest = self._new_asset(".jpg" if photo else ".png")
        image.save(str(dest), "JPG" if photo else "PNG", 90 if photo else -1)
        self.editor.insert_image(rel, image)

    def take_photo(self) -> None:
        from .camera import CameraDialog, cameras, with_camera_permission
        if not cameras():
            QMessageBox.information(self, "Camera", "No camera was found on this computer.")
            return

        def shoot() -> None:
            dlg = CameraDialog(self)
            if dlg.exec() and dlg.image is not None and not dlg.image.isNull():
                self._add_image(dlg.image, photo=True)
        with_camera_permission(self, shoot)

    def insert_image(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Insert image", "",
                                            "Images (*.png *.jpg *.jpeg)")
        if not fn:
            return
        rel, dest = self._new_asset(Path(fn).suffix.lower())
        shutil.copyfile(fn, dest)
        self.editor.insert_image(rel, QImage(str(dest)))

    # ── files ──────────────────────────────────────────────────────

    # Notes save themselves: a couple of seconds after a change, and
    # before another note is opened or the window closes.  A new note
    # gets its file in the library once it has something in it.

    def _is_blank(self) -> bool:
        return (not self.header.title.text().strip() and not self.note.recordings
                and not self.note.transcript
                and not self.editor.document().toPlainText().strip()
                and not self.header.summary.toPlainText().strip())

    def autosave(self) -> bool:
        self._autosave_timer.stop()
        if not self.dirty:
            return True
        if self.path is None:
            if self._is_blank():
                return True
            folder = self._new_note_folder or self.library.root
            self.path = library.new_note_path(folder, self.header.title.text())
        return self.save()

    def _flush(self) -> bool:
        """Save the open note before leaving it; False to stay.  Listening
        is finished first, so its last words and its recording stay with
        this note, and an AI job writing into it is stopped."""
        self._finish_listening()
        if self._ai_job is not None:
            self._cancel_ai()
        if self.autosave():
            return True
        r = QMessageBox.question(self, "KherveNote",
                                 "This note could not be saved. Leave it anyway?",
                                 QMessageBox.Discard | QMessageBox.Cancel)
        return r == QMessageBox.Discard

    def _fresh_work_dir(self) -> None:
        self._tmp.cleanup()
        self._tmp = tempfile.TemporaryDirectory(prefix="khervenote-")
        self.work_dir = Path(self._tmp.name)

    def new_note(self, folder: Optional[Path] = None) -> None:
        if not self._flush():
            return
        self._fresh_work_dir()
        self._new_note_folder = Path(folder) if folder else self.library.selected_folder()
        self._set_note(Note.new())
        self.header.title.setFocus()

    def _last_dir(self) -> str:
        return self.settings.value("files/last_dir", str(Path.home() / "Documents"))

    def open_dialog(self) -> None:
        if not self._flush():
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Open note", self._last_dir(),
                                            f"KherveNote (*{EXTENSION})")
        if fn:
            self.open_path(Path(fn))

    def _open_from_library(self, path: Path) -> None:
        if path != self.path and self._flush():
            self.open_path(path)

    def open_path(self, path: Path) -> None:
        self._fresh_work_dir()
        try:
            note = load_knote(path, self.work_dir)
        except Exception as exc:  # noqa: BLE001 — any unreadable file
            QMessageBox.warning(self, "KherveNote", f"Could not open {path.name}:\n{exc}")
            self._set_note(Note.new())
            return
        self.settings.setValue("files/last_dir", str(path.parent))
        self._set_note(note, path)
        self._disk_mtime = path.stat().st_mtime

    def save(self) -> bool:
        if self.path is None:
            self.path = library.new_note_path(self._new_note_folder or self.library.root,
                                              self.header.title.text())
        note = self._sync_note()
        try:
            self._before_overwrite(note)
            save_knote(note, self.path, self.work_dir)
        except OSError as exc:
            QMessageBox.warning(self, "KherveNote", f"Could not save:\n{exc}")
            return False
        self._name_after_title()
        self._disk_mtime = self.path.stat().st_mtime
        for rec in self._unsaved_recordings:
            recovery.finish(rec)
        self._unsaved_recordings.clear()
        if self.session is not None:
            recovery.set_note(Path(self.session.audio_path), str(self.path),
                              self.header.title.text().strip())
        self.library.set_pending(None)
        self._mark_clean()
        self.settings.setValue("library/last", str(self.path))
        self.library.set_current(self.path, self.editor.headings())
        self.statusBar().showMessage(f"Saved {self.path.name}", 2000)
        return True

    def _before_overwrite(self, note: Note) -> None:
        """Never lose what is on disk: keep it as an earlier version and,
        if someone else changed the file since this window last read or
        wrote it (a second window, a sync program), save this window's
        note as a separate copy instead of overwriting theirs."""
        if not self.path.exists():
            return
        changed = (self._disk_mtime is not None
                   and abs(self.path.stat().st_mtime - self._disk_mtime) > 0.5)
        history.snapshot(self.library.root, note.meta.id, self.path, force=changed)
        if changed:
            theirs = self.path
            self.path = library.unique_path(
                theirs.parent, f"{theirs.stem} (this window {datetime.now():%H.%M})")
            note.meta.id = uuid.uuid4().hex
            QMessageBox.warning(self, "KherveNote", (
                f"“{theirs.name}” was changed outside this window (another KherveNote "
                "window or a sync program?).\n\nNothing is overwritten: this window's "
                f"note is saved as “{self.path.name}”, next to it."))

    def _name_after_title(self) -> None:
        """A note first saved before it had a title is called "Note <date>";
        once it has one, the file takes its name."""
        title = self.header.title.text().strip()
        if title and _AUTO_NAME.match(self.path.stem):
            try:
                self.path = library.rename(self.path, title)
            except OSError:
                pass

    def _moved(self, old: Path, new: Path) -> None:
        if self.path is None:
            return
        if self.path == old:
            self.path = new
        elif old in self.path.parents:
            self.path = new / self.path.relative_to(old)
        else:
            return
        self.settings.setValue("library/last", str(self.path))
        self.library.current = self.path
        self._update_title()

    def _trashed(self, path: Path) -> None:
        if self.path is not None and (self.path == path or path in self.path.parents):
            # Its file is gone: do not save it back.
            self.path = None
            self._mark_clean()
            self._fresh_work_dir()
            self._set_note(Note.new())

    def show_versions(self) -> None:
        from .versions_dialog import VersionsDialog
        self.autosave()
        dlg = VersionsDialog(history.versions(self.library.root, self.note.meta.id), self)
        if dlg.exec() and dlg.chosen is not None:
            stem = f"{(self.header.title.text().strip() or 'Note')} (from "\
                   f"{dlg.chosen.when:%d %b %H.%M})"
            folder = self.path.parent if self.path else self.library.root
            copy = history.restore_copy(dlg.chosen.path, folder, library.safe_name(stem))
            self.library.refresh()
            if self._flush():
                self.open_path(copy)
            self.statusBar().showMessage(f"Restored as {copy.name} — the note you had is "
                                         "unchanged", 8000)

    def choose_library(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder for all notes",
                                                  str(self.library.root))
        if folder and self._flush():
            self.settings.setValue("library/root", folder)
            self.library.set_root(Path(folder))

    def _suggested_name(self, suffix: str) -> str:
        base = self.path.stem if self.path else (self.header.title.text().strip() or "Notes")
        folder = self.path.parent if self.path else Path(self._last_dir())
        safe = "".join(c for c in base if c not in '\\/:*?"<>|')
        return str(folder / f"{safe}{suffix}")

    def save_as(self) -> bool:
        fn, _ = QFileDialog.getSaveFileName(self, "Save note", self._suggested_name(EXTENSION),
                                            f"KherveNote (*{EXTENSION})")
        if not fn:
            return False
        self.path = Path(fn).with_suffix(EXTENSION)
        self.settings.setValue("files/last_dir", str(self.path.parent))
        return self.save()

    # ── export ─────────────────────────────────────────────────────

    def _latex(self) -> str:
        return to_latex(self._sync_note(), show_times=self.act_times.isChecked(),
                        transcript=self.act_transcript.isChecked(),
                        asset_dir=self.work_dir)

    def export_tex(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Export LaTeX", self._suggested_name(".tex"),
                                            "LaTeX (*.tex)")
        if not fn:
            return
        dest = Path(fn)
        dest.write_text(self._latex(), encoding="utf-8")
        if self.note.asset_paths():
            shutil.copytree(self.work_dir / "assets", dest.parent / "assets",
                            dirs_exist_ok=True)
        self.statusBar().showMessage(f"Wrote {dest.name}", 4000)

    def export_pdf(self) -> None:
        if self._compiling:
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Export PDF", self._suggested_name(".pdf"),
                                            "PDF (*.pdf)")
        if not fn:
            return
        dest = Path(fn)
        tex = self._latex()
        build = self.work_dir / "build"
        signals = _Signals(self)
        signals.done.connect(lambda res: self._compiled(res, dest))
        self._compiling = True
        self.act_pdf.setEnabled(False)
        self.statusBar().showMessage("Compiling PDF… (the first compile may download "
                                     "LaTeX packages)")

        def work():
            signals.done.emit(compiler.compile_tex(tex, build, self.work_dir))
        threading.Thread(target=work, daemon=True).start()

    def _compiled(self, res: compiler.CompileResult, dest: Path) -> None:
        self._compiling = False
        self.act_pdf.setEnabled(True)
        if not res.ok:
            self.statusBar().clearMessage()
            box = QMessageBox(QMessageBox.Warning, "KherveNote", "The PDF could not be built.",
                              parent=self)
            box.setInformativeText(res.error or "")
            box.setDetailedText(res.log[-8000:])
            box.exec()
            return
        try:
            shutil.copyfile(res.pdf_path, dest)
        except OSError as exc:
            QMessageBox.warning(self, "KherveNote", f"Could not write {dest}:\n{exc}")
            return
        pages = compiler.pdf_page_heights_mm(dest)
        msg = f"Exported {dest.name}"
        if self.note.meta.layout == "continuous" and len(pages) > 1:
            msg += (f" — longer than {CONTINUOUS_LIMIT_MM / 1000:.2f} m, so split into "
                    f"{len(pages)} continuous pages between sections")
        self.statusBar().showMessage(msg, 8000)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(dest)))

    # ── attached documents ─────────────────────────────────────────

    def attach_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Attach documents", self._last_dir(),
                                                documents.FILTER)
        if files:
            self.add_files(files)

    def add_files(self, files: list) -> None:
        """Files dropped or chosen: pictures go on the page, documents
        are put in the note as an icon, where the cursor is."""
        attached, skipped = [], []
        for fn in files:
            path = Path(fn)
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                rel, dest = self._new_asset(path.suffix.lower())
                shutil.copyfile(path, dest)
                self.editor.insert_image(rel, QImage(str(dest)))
            elif documents.kind_of(path) and path.is_file():
                # Kept under its own name, so KhervePDF and other apps show
                # "Manual.pdf" rather than a made-up one.
                rel = f"assets/att-{uuid.uuid4().hex[:10]}/{library.safe_name(path.stem)}" \
                      f"{path.suffix.lower()}"
                (self.work_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, self.work_dir / rel)
                self.editor.insert_attachment(rel, path.name)
                attached.append(Attachment(rel, path.name))
            else:
                skipped.append(path.name)
        if attached:
            self.show_document(attached[-1])
        if skipped:
            QMessageBox.information(self, "Insert", "These cannot be inserted (use PDF, Word "
                                    ".docx, PowerPoint .pptx, text or pictures):\n\n"
                                    + "\n".join(skipped))

    def _update_drop_hint(self) -> None:
        self.header.drop_hint.setVisible(not self.editor.attachments())

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        files = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if files:
            event.acceptProposedAction()
            self.add_files(files)

    def _attachment_action(self, action: str, path: str, name: str) -> None:
        att = Attachment(path, name)
        if action == "open_file":
            self._open_attachment_file(att)
            return
        if action == "open":
            if name.lower().endswith(".pdf"):
                self.open_in_khervepdf(att)
            else:
                self._open_attachment_file(att, watch=True)
            return
        then = {
            "summarise": lambda doc: self._doc_summarise(),
            "summarise_sections": lambda doc: self._doc_summarise_sections(),
            "find": lambda doc: self.doc_panel.find.setFocus(),
            "ask": lambda doc: self.doc_panel.question.setFocus(),
        }.get(action)
        self.show_document(att, then)

    def _view_path(self, att: Attachment) -> Path:
        """The file another app opens: the note's own copy when it already
        has the document's name, else a copy under that name, watched so
        changes saved there come back into the note."""
        asset = self.work_dir / att.path
        if asset.name == att.name:
            view = asset
        else:
            view = self.work_dir / "open" / att.path.replace("/", "_") / att.name
            view.parent.mkdir(parents=True, exist_ok=True)
            if not view.exists():
                shutil.copyfile(asset, view)
        self._watched[str(view)] = att.path
        if str(view) not in self._watcher.files():
            self._watcher.addPath(str(view))
        return view

    def _attachment_changed(self, view: str) -> None:
        """A watched document was saved by another app (annotations in
        KhervePDF, say): take the new version into the note."""
        rel = self._watched.get(view)
        if rel is None:
            return
        src = Path(view)
        if not src.exists():          # saved by replacing the file: wait for it
            QTimer.singleShot(300, lambda: self._attachment_changed(view))
            return
        if str(src) not in self._watcher.files():
            self._watcher.addPath(str(src))
        asset = self.work_dir / rel
        if src != asset:
            shutil.copyfile(src, asset)
        self._docs.pop(rel, None)
        self._header_changed()
        self.statusBar().showMessage(f"{src.name} was changed in another app — kept in this "
                                     "note", 6000)

    def open_in_khervepdf(self, att: Attachment) -> None:
        view = self._view_path(att)
        how = khervepdf_link.open_pdf(str(view), self.settings.value("pdf/khervepdf", ""))
        if how == "running":
            self.statusBar().showMessage(f"{att.name} opened in KhervePDF", 5000)
        elif how == "started":
            self.statusBar().showMessage(f"Starting KhervePDF with {att.name}…", 8000)
        else:
            box = QMessageBox(QMessageBox.Information, "KhervePDF", (
                "KhervePDF, the KherveTools PDF viewer, was not found on this computer.\n\n"
                "Show KherveNote where it is (the KhervePDF app, or its folder), or open "
                "the PDF with the computer's default viewer."), parent=self)
            locate = box.addButton("Where is KhervePDF…", QMessageBox.ActionRole)
            default = box.addButton("Default viewer", QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is locate and self.locate_khervepdf():
                self.open_in_khervepdf(att)
            elif box.clickedButton() is default:
                self._open_attachment_file(att, watch=True)

    def locate_khervepdf(self) -> bool:
        path = QFileDialog.getExistingDirectory(
            self, "Where is KhervePDF? (the KhervePDF app, or its folder)", "/Applications")
        if not path:
            return False
        self.settings.setValue("pdf/khervepdf", path)
        return True

    def _open_attachment_file(self, att: Attachment, watch: bool = False) -> None:
        if watch:
            view = self._view_path(att)
        else:
            # A copy named as the user knows it, so the other app shows a
            # sensible title.
            view = self.work_dir / "open" / att.name
            view.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.work_dir / att.path, view)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(view)))

    def show_document(self, att: Attachment, then=None) -> None:
        """Open *att* in the Document panel, then call *then(doc)* once it
        has been read."""
        self._doc_att = att
        self.doc_dock.show()
        self.doc_dock.raise_()
        doc = self._docs.get(att.path)
        if doc is not None:
            if self.doc_panel.doc is not doc:
                self.doc_panel.set_document(doc)
            if then:
                then(doc)
            return
        self.doc_panel.set_loading(att.name)
        signals = _Signals(self)
        path = self.work_dir / att.path

        def done(result) -> None:
            status, value = result
            if status == "ok":
                self._docs[att.path] = value
                if self._doc_att is att:
                    self.doc_panel.set_document(value)
                    if then:
                        then(value)
            else:
                self.doc_panel.set_failed(att.name, value)
        signals.done.connect(done)

        def work():
            try:
                signals.done.emit(("ok", documents.read(path, att.name)))
            except Exception as exc:  # noqa: BLE001 — a damaged file must not crash
                signals.done.emit(("error", f"Could not read it: {exc}"))
        threading.Thread(target=work, daemon=True).start()

    def _doc(self):
        return self.doc_panel.doc

    def _ai_write(self, message: str, title: str, job, write=None) -> None:
        """Run *job(model, progress)* with the local AI and write its
        answer into the note — as a section called *title*, or through
        *write(text)*."""
        def finished(result) -> None:
            status, text = result
            if status != "ok" or not text.strip():
                self._ai_problem(text or "The local AI returned nothing.")
                return
            if write is not None:
                write(text)
            else:
                insert_section(self.editor, title, markdown_blocks(text))
            self.statusBar().showMessage("Written into the note — Ctrl+Z undoes it", 6000)
        self._run_ai(message, lambda model: job(model, self.ai_bar_step), finished)

    def ai_bar_step(self, text: str) -> None:
        """For jobs that report progress themselves (from any thread)."""
        job = local_ai.current_job()
        if job is not None:
            job.step(text)

    def _doc_summarise_sections(self) -> None:
        doc = self._doc()
        d = self.doc_panel.directions_text()
        if doc is not None:
            self._ai_write(f"Summarising every section of {doc.name}…",
                           f"Summary by section — {doc.name}",
                           lambda m, _p: local_ai.summarise_each_section(m, doc, directions=d))

    def _doc_summarise(self) -> None:
        doc = self._doc()
        d = self.doc_panel.directions_text()
        if doc is not None:
            self._ai_write(f"Summarising {doc.name}… (a long document takes a while)",
                           f"Summary — {doc.name}",
                           lambda m, _p: local_ai.summarise_document(m, doc, directions=d))

    def _doc_summarise_section(self, i: int) -> None:
        doc = self._doc()
        d = self.doc_panel.directions_text()
        if doc is None:
            return
        sec = doc.sections[i]
        name = sec.title or doc.name
        self._ai_write(f"Summarising “{name}”…", f"{name} — summary",
                       lambda m, _p: local_ai.summarise_section(m, doc.name, name, sec.text,
                                                                directions=d))

    def _doc_ask(self, question: str) -> None:
        doc = self._doc()
        d = self.doc_panel.directions_text()
        if doc is not None:
            title = question if len(question) <= 90 else question[:87] + "…"
            self._ai_write(f"Reading {doc.name} to answer…", title,
                           lambda m, _p: local_ai.answer(m, doc, question, directions=d))
            self.doc_panel.question.clear()

    def _doc_insert_section(self, i: int) -> None:
        doc = self._doc()
        if doc is None:
            return
        sec = doc.sections[i]
        where = f", p. {sec.page}" if sec.page else ""
        insert_section(self.editor, f"{sec.title or 'Extract'} ({doc.name}{where})",
                       markdown_blocks(sec.text))

    def _doc_quote(self, hit) -> None:
        doc = self._doc()
        if doc is None:
            return
        quote = f"“{hit.snippet.strip('… ')}”"
        source = f" ({doc.name}, {hit.where})"
        self.editor.insert_paragraph(quote + source, [[0, len(quote), "i"]])
        self.editor.setFocus()

    # ── times and the speech beside the notes ──────────────────────

    def _time_label(self, t: float) -> str:
        return self.note.time_label(t, clock=self.act_clock_times.isChecked()
                                    if hasattr(self, "act_clock_times") else True)

    def _toggle_clock_times(self, on: bool) -> None:
        self.settings.setValue("view/clock_times", on)
        self.editor.gutter.update()
        self.speech.render()

    def _lead(self) -> float:
        """How long before writing something the speech about it usually
        came (Speech ▸ The speech comes before my notes by…)."""
        return float(self.settings.value("speech/lead", 120, type=int))

    def _speech_window(self, start: Optional[float], end: Optional[float]):
        """A section's speech: from *lead* before its heading was written to
        *lead* before the next one (or to the end)."""
        lead = self._lead()
        return (None if start is None else start - lead,
                None if end is None else end - lead)

    def _correlate(self) -> None:
        """Highlight what was said before the paragraph at the cursor was
        written — as far back as the lead time, a minute at least."""
        t = self.editor.current_time()
        if t is not None and self.note.transcript:
            self.speech.highlight(t - max(60.0, self._lead()), t + 5)

    def _speech_text(self, segments) -> str:
        lines = "\n".join(f"[{self._time_label(g.t)}] {g.text}" for g in segments)
        words = self.note.meta.vocabulary.strip()
        # The AI spells the talk's terms right as well.
        return f"(Terms used in this talk: {words})\n{lines}" if words else lines

    def _audio_at(self, t: float):
        """(file, session time it starts) of the recording holding time
        *t*, or None."""
        for rec in self.note.recordings:
            path = self.work_dir / rec.path
            if rec.t0 - 1 <= t <= rec.t0 + rec.duration + 1 and path.exists():
                return path, rec.t0
        s = self.session
        if s is not None and t >= s.t0 and Path(s.audio_path).exists():
            return Path(s.audio_path), s.t0          # the one being recorded now
        return None

    def play_speech(self, index: int, on: bool) -> None:
        """Hear line *index* of the speech — or, with *on*, carry on from it."""
        segs = self.note.transcript
        if not 0 <= index < len(segs):
            return
        seg = segs[index]
        found = self._audio_at(seg.t)
        if found is None:
            self.statusBar().showMessage("The recording of this line is not in the note.", 5000)
            return
        path, t0 = found
        start = max(0.0, seg.t - t0 - 0.4)
        end = None
        if not on:
            nxt = segs[index + 1].t if index + 1 < len(segs) else None
            end = (nxt - t0 + 0.2) if nxt is not None and nxt - seg.t < 30 else start + 15
        self.player.play(str(path), start, end, f"{self._time_label(seg.t)}  {seg.text[:60]}")

    def _set_vocabulary(self, words: str) -> None:
        self.note.meta.vocabulary = words
        if self.session is not None:
            self.session.vocabulary = words
        self._header_changed()

    def suggest_vocabulary(self) -> None:
        texts = [self.header.title.text(), self.header.summary.toPlainText(),
                 self.editor.document().toPlainText()]
        for path, name in self.editor.attachments():
            doc = self._docs.get(path)
            if doc is None:
                try:
                    doc = documents.read(self.work_dir / path, name)
                    self._docs[path] = doc
                except Exception:  # noqa: BLE001 — an unreadable file adds nothing
                    continue
            texts.append(doc.text)
        found = vocabulary.suggest(texts, known=self.note.meta.vocabulary)
        if not found:
            self.statusBar().showMessage("No new names or terms found in the note or its "
                                         "documents.", 5000)
            return
        words = vocabulary.merge(self.note.meta.vocabulary, found)
        self.speech.set_vocabulary(words)
        self._set_vocabulary(words)
        self.statusBar().showMessage(f"Added {len(found)} words — remove any you don't need.",
                                     6000)

    def _fill_section(self) -> None:
        """Ask which speech goes with the section at the cursor — starting
        a little before its heading was written — then let the AI add
        what the notes miss."""
        if not self.note.transcript:
            self.statusBar().showMessage("Nothing has been said yet.", 5000)
            return
        first, start, end = self.editor.section_window()
        a, b = self._speech_window(start, end)
        speech = self.note.transcript
        a = speech[0].t if a is None else max(a, 0.0)
        b = speech[-1].t if b is None else b
        title = first.text().strip() if block_kind(first) == ("heading", 1) else ""
        dlg = SpeechRangeDialog(self.note, title, a, b, self.speech.selected_range(), self)
        dlg.range_changed.connect(self.speech.highlight)
        dlg.range_changed.emit(*dlg.span)
        if dlg.exec():
            self._fill_with(first, dlg.segments())

    def _fill_with(self, first, segments) -> None:
        if not segments:
            return
        notes = self._section_text(first)
        span = f"{self._time_label(segments[0].t)}–{self._time_label(segments[-1].t)}"

        def write(text: str) -> None:
            if text.strip().lower().startswith("nothing to add"):
                self.statusBar().showMessage("Your notes already cover what was said.", 6000)
                return
            insert_section(self.editor, f"From the speech ({span})", markdown_blocks(text),
                           level=2, within=first)
        self._ai_write("Filling in the section from the speech", "",
                       lambda m, _p: local_ai.fill_from_speech(m, notes, self._speech_text(segments)),
                       write)

    def _section_text(self, first) -> str:
        lines, b = [], first
        while b.isValid():
            if b != first and block_kind(b) == ("heading", 1):
                break
            if b.text().strip():
                lines.append(b.text().replace("\u2028", " "))
            b = b.next()
        return "\n".join(lines)

    def _fill_every_section(self) -> None:
        windows = [(w[0], *self._speech_window(w[1], w[2]))
                   for w in self.editor.section_windows()]
        windows = [w for w in windows if self.note.speech_between(w[1], w[2])]
        if not windows:
            self.statusBar().showMessage("There is no speech to compare with yet.", 5000)
            return
        jobs = [(w[0].blockNumber(), self._section_text(w[0]),
                 self.note.speech_between(w[1], w[2])) for w in windows]

        def run(model, _p):
            out = []
            for i, (number, notes, segs) in enumerate(jobs, 1):
                local_ai.current_job().step(f"Section {i} of {len(jobs)}")
                out.append((number, segs, local_ai.fill_from_speech(
                    model, notes, self._speech_text(segs))))
            return out

        def write(results) -> None:
            # Last section first, so earlier block numbers stay valid.
            for number, segs, text in sorted(results, key=lambda r: r[0], reverse=True):
                if text.strip().lower().startswith("nothing to add"):
                    continue
                span = f"{self._time_label(segs[0].t)}–{self._time_label(segs[-1].t)}"
                insert_section(self.editor, f"From the speech ({span})",
                               markdown_blocks(text), level=2,
                               within=self.editor.document().findBlockByNumber(number))
        self._run_ai("Filling in every section from the speech", lambda m: run(m, None),
                     lambda res: write(res[1]) if res[0] == "ok"
                     else self._ai_problem(res[1]))

    def _notes_from_speech(self, selected: str) -> None:
        text = selected or self._speech_text(self.note.transcript)
        if not text.strip():
            self.statusBar().showMessage("Nothing has been said yet.", 5000)
            return

        def write(notes: str) -> None:
            insert_section(self.editor, "Notes from the speech", markdown_blocks(notes),
                           at_end=True)
        self._ai_write("Making notes from the speech", "",
                       lambda m, _p: local_ai.notes_from_speech(m, text), write)

    # ── undo / help ────────────────────────────────────────────────

    def _undo_target(self):
        # Only a text box of this window — the focus may be elsewhere.
        w = QApplication.focusWidget()
        if isinstance(w, (QTextEdit, QLineEdit)) and self.isAncestorOf(w):
            return w
        return self.editor

    def _undo(self) -> None:
        self._undo_target().undo()

    def _redo(self) -> None:
        self._undo_target().redo()

    def _ai_problem(self, message: str) -> None:
        box = QMessageBox(QMessageBox.Warning, "Local AI", message, parent=self)
        setup = box.addButton("Set up the local AI…", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is setup:
            self.show_ai_setup()

    def install_examples(self) -> None:
        from . import examples
        if not self._flush():
            return
        paths = examples.install(self.library.root)
        self.library._expanded.add(str(self.library.root / examples.FOLDER))
        self.library.refresh()
        self.open_path(paths[0])
        self.speech_dock.show()
        self.statusBar().showMessage(
            f"{len(paths)} example notes are in the “{examples.FOLDER}” folder of the Notes "
            "panel — each has the speech that was heard beside it.", 10000)

    def show_ai_setup(self) -> None:
        from .ai_setup import AISetupDialog
        AISetupDialog(self.settings, self).exec()

    def show_manual(self) -> None:
        from .manual import ManualDialog
        if getattr(self, "_manual", None) is None:
            self._manual = ManualDialog(self)
        self._manual.show()
        self._manual.raise_()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (obj is self.editor and event.type() == QEvent.KeyPress
                and self.session is not None and self.act_listen.isChecked()
                and self.act_stop_on_key.isChecked()
                and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter)
                and not event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            # Like dictation on a phone: starting to type yourself ends it.
            self._stop_listening()
        return super().eventFilter(obj, event)

    # ── misc ───────────────────────────────────────────────────────

    def about(self) -> None:
        QMessageBox.about(self, "About KherveNote", (
            f"<h3>KherveNote v{self._version}</h3>"
            "<p>Live notes for lectures, trainings and talks, exported to LaTeX "
            "and PDF.</p><p>Part of the <b>KherveTools</b> family — "
            "<a href='https://khervetools.com'>khervetools.com</a></p>"
            "<p>© 2026 Gwilherm Kerherve · GPL v3</p>"))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.session is not None:
            self._stop_listening()
        if self._flush():
            self._tmp.cleanup()
            event.accept()
        else:
            event.ignore()
