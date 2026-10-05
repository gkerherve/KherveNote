# KherveNote — main window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: toolbar, outline, the note header and the endless page."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QToolBar, QVBoxLayout, QWidget,
)

from . import __version__, compiler, icons, theme
from .editor import STYLES, NoteEditor, document_to_note, load_note
from .knote_file import EXTENSION, load_knote, save_knote
from .model import Note
from .audio import input_devices
from .model import Recording
from .permissions import with_permission
from .serializer import CONTINUOUS_LIMIT_MM, format_time, to_latex
from .transcriber import DEFAULT_MODEL, LANGUAGES, MODELS, ListenSession, missing_packages


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
        self.summary = QPlainTextEdit()
        self.summary.setPlaceholderText("Summary")
        self.summary.setFixedHeight(90)
        self.summary.setVisible(False)
        for w in (self.title, self.speaker, self.date, self.place):
            w.setFrame(False)
            w.textEdited.connect(self.changed)
        self.summary.textChanged.connect(self.changed)
        self._col = col
        col.addWidget(self.title)
        col.addLayout(row)
        col.addWidget(self.summary)

    def set_column(self, left: int, right: int) -> None:
        self._col.setContentsMargins(left, 14, right, 4)

    def apply_theme(self) -> None:
        page, muted, text = theme.hex_("page"), theme.hex_("muted"), theme.hex_("text")
        self.setStyleSheet(
            f"#noteheader{{background:{page};}}"
            f"QLineEdit{{background:{page}; color:{text}; border:none;}}"
            f"QPlainTextEdit{{background:{theme.hex_('button')}; color:{text};"
            f" border:none; border-left:3px solid {theme.hex_('accent')};}}")
        for w in (self.speaker, self.date, self.place):
            w.setStyleSheet(f"color:{muted};")

    def load(self, note: Note) -> None:
        m = note.meta
        for w, v in ((self.title, m.title), (self.speaker, m.speaker),
                     (self.date, m.date), (self.place, m.place)):
            w.setText(v)
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
    """Header over editor, sharing one column so their text lines up."""

    def __init__(self, header: NoteHeader, editor: NoteEditor) -> None:
        super().__init__()
        self.header, self.editor = header, editor
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(header)
        col.addWidget(editor, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._align)

    def _align(self) -> None:
        m = self.editor.viewportMargins()
        margin = int(self.editor.document().documentMargin())
        self.header.set_column(m.left() + margin, m.right() + margin)


class _Signals(QObject):
    done = Signal(object)


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
        self.editor.outline_changed.connect(self._refresh_outline)
        self.editor.style_at_cursor.connect(self._show_style)
        self.editor.image_pasted.connect(self._add_image)
        self.header = NoteHeader()
        self.header.changed.connect(self._header_changed)
        self.setCentralWidget(Page(self.header, self.editor))

        self.outline = QListWidget()
        self.outline.itemClicked.connect(
            lambda item: self.editor.go_to_block(item.data(Qt.UserRole)))
        dock = QDockWidget("Sections", self)
        dock.setObjectName("outline")
        dock.setWidget(self.outline)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

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
        self._listen_start = 0.0
        self.clock = QLabel()
        self.statusBar().addPermanentWidget(self.clock)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

        self._build_actions()
        self._apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._apply_theme())
        if path:
            self.open_path(Path(path))
        else:
            self._set_note(Note.new())

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
        self.act_section = A("Section", lambda: ed.new_section(), "Ctrl+Return",
                             "Start a new section (Ctrl+Return)")
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
        self.act_camera = A("Take a picture", self.take_photo, "Ctrl+Shift+P",
                            "Take a picture with the camera — a whiteboard, a slide (Ctrl+Shift+P)")
        self.act_pdf = A("Export PDF", self.export_pdf, "Ctrl+E",
                         "Compile the note to PDF (Ctrl+E)")
        self.act_tex = A("Export LaTeX", self.export_tex)
        self.act_summary = A("Show &summary", self._toggle_summary)
        self.act_clock = A("Restart session &clock", self.restart_clock, None,
                           "Count times from now — use when the talk actually starts")

        self.style_box = QComboBox()
        self.style_box.setToolTip("Paragraph style (Ctrl+0 text, Ctrl+1/2/3 headings)")
        for label, _, _ in STYLES:
            self.style_box.addItem(label)
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
        m.addAction(A("&Quit", self.close, QKeySequence.Quit))
        m = mb.addMenu("F&ormat")
        for a in self._style_actions:
            m.addAction(a)
        for a in (None, self.act_key, self.act_question, None, self.act_bold, self.act_italic,
                  self.act_underline, None, self.act_bullets, self.act_numbers):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("&Note")
        for a in (self.act_listen, self.act_section, self.act_image, self.act_camera, None,
                  self.act_summary, self.act_clock):
            m.addSeparator() if a is None else m.addAction(a)
        self._build_speech_menu(mb.addMenu("&Speech"))
        m = mb.addMenu("&Export")
        m.addAction(self.act_continuous)
        m.addAction(self.act_paged)
        m.addAction(self.act_times)
        m = mb.addMenu("&View")
        sub = m.addMenu("&Theme")
        for a in self._theme_actions.values():
            sub.addAction(a)
        m = mb.addMenu("&Help")
        m.addAction(A("&About KherveNote", self.about))

        tb = QToolBar("Main")
        tb.setObjectName("main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        for a in (self.act_new, self.act_open, self.act_save, None, self.act_listen, None):
            tb.addSeparator() if a is None else tb.addAction(a)
        tb.addWidget(self.style_box)
        for a in (self.act_bold, self.act_italic, self.act_underline, None, self.act_bullets,
                  self.act_numbers, None, self.act_section, self.act_key, self.act_question,
                  self.act_image, self.act_camera, None, self.act_pdf, self.act_tex):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)
        self.toolbar = tb

    def _build_speech_menu(self, menu) -> None:
        menu.addAction(self.act_listen)
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
                        (self.act_pdf, icons.export_pdf()),
                        (self.act_tex, icons.export_tex())):
            a.setIcon(icon)

    # ── theme ──────────────────────────────────────────────────────

    def _choose_theme(self, choice: str) -> None:
        self.settings.setValue("view/theme", choice)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme.apply(QApplication.instance(), self.settings.value("view/theme", "system"))
        self._set_icons()
        self.header.apply_theme()
        modified = self.editor.document().isModified()
        self.editor.apply_theme()
        # Recolouring is not an edit.
        self.editor.document().setModified(modified)

    # ── state ──────────────────────────────────────────────────────

    def _set_note(self, note: Note, path: Optional[Path] = None) -> None:
        self.note, self.path = note, path
        (self.act_paged if note.meta.layout == "paged" else self.act_continuous).setChecked(True)
        self.editor.work_dir = self.work_dir
        self.header.load(note)
        load_note(self.editor, note)
        self._header_dirty = False
        self._update_title()
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

    def _update_title(self) -> None:
        name = self.path.name if self.path else "Untitled"
        self.setWindowTitle(f"KherveNote v{self._version} — {name}{' •' if self.dirty else ''}")

    def _refresh_outline(self) -> None:
        self.outline.clear()
        for level, title, number in self.editor.headings():
            item = QListWidgetItem("    " * (level - 1) + (title or "Untitled section"))
            item.setData(Qt.UserRole, number)
            if level == 1:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self.outline.addItem(item)

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
        (self.work_dir / "assets").mkdir(exist_ok=True)
        path = self.work_dir / f"assets/rec-{uuid.uuid4().hex[:10]}.ogg"
        device_name = self.settings.value("speech/device", "")
        device = next((i for i, n in input_devices() if n == device_name), None)
        t0 = self.note.elapsed() or 0.0
        self.session = ListenSession(str(path), t0, model,
                                     self.settings.value("speech/language", ""), device, self,
                                     engine=self._engine[1] if self._engine else None)
        self.session.text.connect(self.editor.append_transcript)
        self.session.level.connect(lambda v: self.meter.setValue(min(100, int(v * 400))))
        self.session.status.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.session.failed.connect(self._listen_failed)
        self.session.finished.connect(lambda s=self.session, m=model: self._session_done(s, m))
        self.act_listen.setChecked(True)
        self.act_listen.setIcon(icons.microphone(recording=True))
        for w in (self.listen_label, self.meter):
            w.setVisible(True)
        self.listen_label.setText("\u25cf Listening")
        self.listen_label.setStyleSheet(f"color:{theme.hex_('red')}; font-weight:bold;")
        self.session.start()

    def _stop_listening(self) -> None:
        self.act_listen.setChecked(False)
        self.act_listen.setIcon(icons.microphone())
        for w in (self.listen_label, self.meter):
            w.setVisible(False)
        if self.session is not None:
            self.statusBar().showMessage("Writing down the last words…", 8000)
            self.session.stop()

    def _listen_failed(self, message: str) -> None:
        self.statusBar().showMessage(message, 15000)
        if self.session is not None and self.session.duration == 0:
            self._stop_listening()
            QMessageBox.warning(self, "Listen", message)

    def _session_done(self, session, model: str) -> None:
        if session.engine is not None:
            self._engine = (model, session.engine)
        path = Path(session.audio_path)
        if path.exists() and session.duration > 0:
            rel = path.relative_to(self.work_dir).as_posix()
            self.note.recordings.append(Recording(rel, session.t0, session.duration))
            self._header_changed()
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

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = QMessageBox.question(self, "KherveNote", "Save changes to this note?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def _fresh_work_dir(self) -> None:
        self._tmp.cleanup()
        self._tmp = tempfile.TemporaryDirectory(prefix="khervenote-")
        self.work_dir = Path(self._tmp.name)

    def new_note(self) -> None:
        if self._confirm_discard():
            self._fresh_work_dir()
            self._set_note(Note.new())

    def _last_dir(self) -> str:
        return self.settings.value("files/last_dir", str(Path.home() / "Documents"))

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Open note", self._last_dir(),
                                            f"KherveNote (*{EXTENSION})")
        if fn:
            self.open_path(Path(fn))

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

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        try:
            save_knote(self._sync_note(), self.path, self.work_dir)
        except OSError as exc:
            QMessageBox.warning(self, "KherveNote", f"Could not save:\n{exc}")
            return False
        self._mark_clean()
        self.statusBar().showMessage(f"Saved {self.path.name}", 3000)
        return True

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
        if self._confirm_discard():
            self._tmp.cleanup()
            event.accept()
        else:
            event.ignore()
