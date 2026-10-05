# KherveNote — main window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: toolbar, outline, the live page and the note composer."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QToolBar, QVBoxLayout, QWidget,
)

from . import __version__, compiler, icons, lists
from .knote_file import EXTENSION, load_knote, save_knote
from .live_page import LivePage
from .model import Note
from .serializer import CONTINUOUS_LIMIT_MM, format_time, to_latex

_KINDS = (("Note", "typed"), ("Key point", "important"), ("Question", "question"))


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


class Composer(QPlainTextEdit):
    """Where notes are typed during the talk: Enter adds the note to the
    page, Shift+Enter starts a new line (continuing a list), Tab and
    Shift+Tab indent and outdent a list item."""

    submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Type a note and press Enter  ·  Shift+Enter for a new line  ·  "
                                "- bullets, 1. numbers, Tab for sub-items")
        self.setFixedHeight(84)

    def _line(self) -> tuple[QTextCursor, str]:
        cur = self.textCursor()
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        return cur, cur.selectedText()

    def _replace_line(self, text: str) -> None:
        cur, _ = self._line()
        cur.insertText(text)
        self.setTextCursor(cur)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key, mods = event.key(), event.modifiers()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                _, line = self._line()
                item = lists.parse_item(line)
                if item is not None and not item.text:
                    self._replace_line("")      # an empty item ends the list
                else:
                    self.textCursor().insertText("\n" + (lists.continuation(line) or ""))
                return
            if not mods & (Qt.ControlModifier | Qt.MetaModifier):
                text = self.toPlainText().strip("\n")
                if text.strip():
                    self.submitted.emit(text)
                    self.clear()
                return
        if key == Qt.Key_Tab and not mods:
            self.indent(1)
            return
        if key == Qt.Key_Backtab:
            self.indent(-1)
            return
        super().keyPressEvent(event)

    def indent(self, step: int) -> None:
        _, line = self._line()
        item = lists.parse_item(line)
        body = line.lstrip(" \t")
        width = lists.indent_of(line)
        width = width + 2 if step > 0 else max(0, width - 2)
        if item is not None and item.numbered:
            # A new sub-list counts from 1 again.
            body = f"1{item.marker[-1]} {item.text}"
        self._replace_line(" " * width + body)

    def toggle_marker(self, numbered: bool) -> None:
        """Make the current line a bullet / numbered item, or plain again."""
        _, line = self._line()
        item = lists.parse_item(line)
        lead = line[:len(line) - len(line.lstrip(" \t"))]
        if item is not None and item.numbered == numbered:
            self._replace_line(lead + item.text)
        else:
            text = item.text if item is not None else line.strip()
            self._replace_line(lead + ("1. " if numbered else "- ") + text)
        self.setFocus()


class _CompileSignals(QObject):
    done = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self, path: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowIcon(icons.app_icon())
        self.resize(1200, 860)
        self.settings = QSettings("KherveTools", "KherveNote")
        self._version = version_string()
        self.path: Optional[Path] = None
        self.dirty = False
        self._tmp = tempfile.TemporaryDirectory(prefix="khervenote-")
        self.work_dir = Path(self._tmp.name)
        self._compiling = False

        self.page = LivePage()
        self.page.changed.connect(self._mark_dirty)
        self.page.titles_changed.connect(self._refresh_outline)
        self.page.split_requested.connect(self._split_at)
        self.page.delete_requested.connect(self._delete_block)
        self.page.remove_section_requested.connect(self._remove_section)

        self.composer = Composer()
        self.composer.submitted.connect(self._add_typed)
        self.kind = QComboBox()
        for label, _ in _KINDS:
            self.kind.addItem(label)
        add = QPushButton("Add")
        add.clicked.connect(lambda: self._add_typed(self.composer.toPlainText().strip()))
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 8)
        bar.addWidget(self.kind)
        bar.addWidget(self.composer, 1)
        bar.addWidget(add)
        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.page, 1)
        col.addLayout(bar)
        self.setCentralWidget(central)

        self.outline = QListWidget()
        self.outline.currentRowChanged.connect(self.page.scroll_to_section)
        dock = QDockWidget("Sections", self)
        dock.setObjectName("outline")
        dock.setWidget(self.outline)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self.clock = QLabel()
        self.statusBar().addPermanentWidget(self.clock)
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)

        self._build_actions()
        if path:
            self.open_path(Path(path))
        else:
            self._set_note(Note.new())

    # ── actions ────────────────────────────────────────────────────

    def _action(self, text, slot, shortcut=None, icon=None, tip=None) -> QAction:
        a = QAction(text, self)
        if icon is not None:
            a.setIcon(icon)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
            a.setStatusTip(tip)
        a.triggered.connect(slot)
        return a

    def _build_actions(self) -> None:
        A = self._action
        self.act_new = A("&New note", self.new_note, QKeySequence.New, icons.new_note())
        self.act_open = A("&Open…", self.open_dialog, QKeySequence.Open, icons.open_note())
        self.act_save = A("&Save", self.save, QKeySequence.Save, icons.save_note())
        self.act_save_as = A("Save &as…", self.save_as, QKeySequence.SaveAs)
        self.act_listen = A("Listen", lambda: None, None, icons.microphone(),
                            "Live speech-to-text with offline Whisper — arrives in v0.2")
        self.act_listen.setEnabled(False)
        self.act_section = A("New &section", self.new_section, "Ctrl+Return",
                             icons.new_section(), "Start a new section now (Ctrl+Return)")
        self.act_key = A("&Key point", lambda: self._compose_as("important"),
                         "Ctrl+Shift+K", icons.star(), "Type a key point (Ctrl+Shift+K)")
        self.act_question = A("&Question", lambda: self._compose_as("question"),
                              "Ctrl+Shift+Q", icons.question(), "Type a question (Ctrl+Shift+Q)")
        self.act_bullets = A("&Bullets", lambda: self.composer.toggle_marker(False),
                             "Ctrl+Shift+8", icons.bullets(), "Bullet list (Ctrl+Shift+8)")
        self.act_numbers = A("N&umbering", lambda: self.composer.toggle_marker(True),
                             "Ctrl+Shift+7", icons.numbering(),
                             "Numbered list — Tab makes sub-items 1.1, 1.2 (Ctrl+Shift+7)")
        self.act_image = A("Insert &image…", self.insert_image, None, icons.image(),
                           "Insert a picture or slide screenshot")
        self.act_paste_image = A("&Paste image", self.paste_image, "Ctrl+Shift+V", None,
                                 "Insert the image on the clipboard, e.g. a screenshot of a slide")
        self.act_pdf = A("Export &PDF…", self.export_pdf, "Ctrl+E", icons.export_pdf(),
                         "Compile the note to PDF (Ctrl+E)")
        self.act_tex = A("Export &LaTeX…", self.export_tex, None, icons.export_tex())
        self.act_clock = A("Restart session &clock", self.restart_clock, None, None,
                           "Count times from now — use when the talk actually starts")

        layouts = QActionGroup(self)
        self.act_continuous = A("&Continuous page", lambda: self._set_layout("continuous"))
        self.act_paged = A("&A4 pages", lambda: self._set_layout("paged"))
        for a in (self.act_continuous, self.act_paged):
            a.setCheckable(True)
            layouts.addAction(a)
        self.act_times = A("Show &times in export", self._toggle_times)
        self.act_times.setCheckable(True)
        self.act_times.setChecked(self.settings.value("export/show_times", False, type=bool))

        mb = self.menuBar()
        m = mb.addMenu("&File")
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.act_pdf)
        m.addAction(self.act_tex)
        m.addSeparator()
        m.addAction(A("&Quit", self.close, QKeySequence.Quit))
        m = mb.addMenu("&Note")
        for a in (self.act_listen, self.act_section, self.act_key, self.act_question,
                  self.act_bullets, self.act_numbers, self.act_image, self.act_paste_image):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.act_clock)
        m = mb.addMenu("&Export")
        m.addAction(self.act_continuous)
        m.addAction(self.act_paged)
        m.addAction(self.act_times)
        m = mb.addMenu("&Help")
        m.addAction(A("&About KherveNote", self.about))

        tb = QToolBar("Main")
        tb.setObjectName("main")
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for a in (self.act_new, self.act_open, self.act_save, None, self.act_listen,
                  self.act_section, self.act_key, self.act_question, self.act_bullets,
                  self.act_numbers, self.act_image,
                  None, self.act_pdf, self.act_tex):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)

    # ── state ──────────────────────────────────────────────────────

    def _set_note(self, note: Note, path: Optional[Path] = None) -> None:
        self.note, self.path = note, path
        (self.act_paged if note.meta.layout == "paged" else self.act_continuous).setChecked(True)
        self.page.rebuild(note, self.work_dir)
        self._refresh_outline()
        self.dirty = False
        self._update_title()
        self.composer.setFocus()

    def _mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "Untitled"
        self.setWindowTitle(f"KherveNote v{self._version} — {name}{' •' if self.dirty else ''}")

    def _refresh_outline(self) -> None:
        self.outline.blockSignals(True)
        row = self.outline.currentRow()
        self.outline.clear()
        for i, sec in enumerate(self.note.sections):
            label = sec.title.strip() or ("(start)" if i == 0 else "Untitled section")
            stamp = format_time(sec.t)
            self.outline.addItem(f"{stamp}  {label}" if stamp else label)
        self.outline.setCurrentRow(min(row, self.outline.count() - 1))
        self.outline.blockSignals(False)

    def _tick(self) -> None:
        self.clock.setText("Session " + format_time(self.note.elapsed()))

    # ── capturing ──────────────────────────────────────────────────

    def _compose_as(self, kind: str) -> None:
        self.kind.setCurrentIndex([k for _, k in _KINDS].index(kind))
        self.composer.setFocus()

    def _add_typed(self, text: str) -> None:
        if not text:
            return
        kind = _KINDS[self.kind.currentIndex()][1]
        self.page.append_block(self.note.add_block(kind, text, t=self.note.elapsed()))
        self.composer.clear()
        self.kind.setCurrentIndex(0)
        self._mark_dirty()

    def new_section(self) -> None:
        self.page.append_section(self.note.add_section(t=self.note.elapsed()))
        self._refresh_outline()
        self.outline.setCurrentRow(self.outline.count() - 1)
        self._mark_dirty()

    def _add_image_file(self, src_suffix: str, writer) -> None:
        rel = f"assets/{uuid.uuid4().hex[:10]}{src_suffix}"
        (self.work_dir / "assets").mkdir(exist_ok=True)
        writer(self.work_dir / rel)
        self.page.append_block(self.note.add_block("image", t=self.note.elapsed(), path=rel))
        self._mark_dirty()

    def insert_image(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Insert image", "",
                                            "Images (*.png *.jpg *.jpeg)")
        if fn:
            self._add_image_file(Path(fn).suffix.lower(),
                                 lambda dest: shutil.copyfile(fn, dest))

    def paste_image(self) -> None:
        img = QApplication.clipboard().image()
        if img.isNull():
            self.statusBar().showMessage("There is no image on the clipboard.", 4000)
            return
        self._add_image_file(".png", lambda dest: img.save(str(dest), "PNG"))

    def restart_clock(self) -> None:
        from datetime import datetime
        self.note.meta.started = datetime.now().isoformat(timespec="seconds")
        self._mark_dirty()

    # ── structure edits ────────────────────────────────────────────

    def _rebuild(self) -> None:
        bar = self.page.verticalScrollBar()
        pos = bar.value()
        self.page.rebuild(self.note, self.work_dir)
        QTimer.singleShot(0, lambda: bar.setValue(pos))
        self._refresh_outline()
        self._mark_dirty()

    def _split_at(self, block_id: str) -> None:
        self.note.split_at(block_id)
        self._rebuild()

    def _delete_block(self, block_id: str) -> None:
        self.note.remove_block(block_id)
        self._rebuild()

    def _remove_section(self, section_id: str) -> None:
        self.note.remove_section(section_id)
        self._rebuild()

    def _set_layout(self, layout: str) -> None:
        if self.note.meta.layout != layout:
            self.note.meta.layout = layout
            self._mark_dirty()

    def _toggle_times(self, on: bool) -> None:
        self.settings.setValue("export/show_times", on)

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
            save_knote(self.note, self.path, self.work_dir)
        except OSError as exc:
            QMessageBox.warning(self, "KherveNote", f"Could not save:\n{exc}")
            return False
        self.dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {self.path.name}", 3000)
        return True

    def _suggested_name(self, suffix: str) -> str:
        base = self.path.stem if self.path else (self.note.meta.title.strip() or "Notes")
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

    def _latex(self, asset_dir: Optional[Path]) -> str:
        return to_latex(self.note, show_times=self.act_times.isChecked(),
                        asset_dir=asset_dir)

    def export_tex(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Export LaTeX", self._suggested_name(".tex"),
                                            "LaTeX (*.tex)")
        if not fn:
            return
        dest = Path(fn)
        dest.write_text(self._latex(self.work_dir), encoding="utf-8")
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
        tex = self._latex(self.work_dir)
        build = self.work_dir / "build"
        signals = _CompileSignals(self)
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
        if self._confirm_discard():
            self._tmp.cleanup()
            event.accept()
        else:
            event.ignore()
