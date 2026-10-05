# KherveNote — the Notes panel
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""The left panel: every note in the library as a tree of folders, a
search box, and the sections of the open note under it.  Folders and
notes are real folders and files (see ``library.py``); moving or
renaming here moves or renames them on disk."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QFile, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QMenu, QMessageBox, QStyle,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import library, theme

PATH = Qt.UserRole
KIND = Qt.UserRole + 1          # "folder" / "note" / "section"
BLOCK = Qt.UserRole + 2         # section: block number in the editor


class _Tree(QTreeWidget):
    dropped = Signal(list, Path)          # paths moved into a folder

    def __init__(self, panel: "LibraryPanel") -> None:
        super().__init__()
        self.panel = panel
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.setIndentation(14)

    def dropEvent(self, event) -> None:  # noqa: N802
        target = self.itemAt(event.position().toPoint())
        dest = self.panel.folder_of(target)
        paths = [Path(i.data(0, PATH)) for i in self.selectedItems()
                 if i.data(0, KIND) in ("folder", "note")]
        # We move the files ourselves and rebuild; Qt must not move items.
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if paths:
            self.dropped.emit(paths, dest)


class LibraryPanel(QWidget):
    open_note = Signal(Path)
    new_note = Signal(Path)               # folder to create it in
    go_to_section = Signal(int)
    moved = Signal(Path, Path)            # old, new — notes or folders
    trashed = Signal(Path)

    def __init__(self, root: Path, parent=None) -> None:
        super().__init__(parent)
        self.root = Path(root)
        self.current: Optional[Path] = None
        #: Folder of the open note while it has no file yet (just made).
        self.pending: Optional[Path] = None
        self._sections: list[tuple[int, str, int]] = []
        self._expanded: set[str] = set()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        new_note = QToolButton()
        new_note.setText("+ Note")
        new_note.setToolTip("New note in the selected folder")
        new_note.clicked.connect(lambda: self.new_note.emit(self.selected_folder()))
        new_folder = QToolButton()
        new_folder.setText("+ Folder")
        new_folder.setToolTip("New folder inside the selected folder")
        new_folder.clicked.connect(lambda: self._make_folder(self.selected_folder()))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.search, 1)
        row.addWidget(new_note)
        row.addWidget(new_folder)

        self.tree = _Tree(self)
        self.tree.itemActivated.connect(self._activated)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemChanged.connect(self._edited)
        self.tree.itemExpanded.connect(lambda i: self._expanded.add(i.data(0, PATH)))
        self.tree.itemCollapsed.connect(lambda i: self._expanded.discard(i.data(0, PATH)))
        self.tree.dropped.connect(self._drop)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)

        col = QVBoxLayout(self)
        col.setContentsMargins(6, 6, 6, 6)
        col.setSpacing(6)
        col.addLayout(row)
        col.addWidget(self.tree, 1)

    # ── building ───────────────────────────────────────────────────

    def set_root(self, root: Path) -> None:
        self.root = Path(root)
        self.refresh()

    def set_current(self, path: Optional[Path], sections=None) -> None:
        self.current = Path(path) if path else None
        if sections is not None:
            self._sections = sections
        self.refresh()

    def set_sections(self, sections) -> None:
        self._sections = sections
        item = self._find(self.current) if self.current is not None else next(
            (i for i in self._all_items() if i.data(0, KIND) == "pending"), None)
        if item is not None:
            self._fill_sections(item)

    def refresh(self) -> None:
        query = self.search.text()
        tree = library.filter_tree(library.scan(self.root), query)
        selected = {i.data(0, PATH) for i in self.tree.selectedItems()}
        self.tree.blockSignals(True)
        self.tree.clear()
        if tree is not None:
            self._add(self.tree.invisibleRootItem(), tree, bool(query.strip()))
        self.tree.blockSignals(False)
        for item in self._all_items():
            if item.data(0, PATH) in selected:
                item.setSelected(True)

    def _add(self, parent: QTreeWidgetItem, folder: library.Folder, open_all: bool) -> None:
        style = self.style()
        if self.pending is not None and Path(self.pending) == Path(folder.path):
            it = QTreeWidgetItem(parent, ["New note — start writing to keep it", ""])
            it.setData(0, KIND, "pending")
            it.setData(0, PATH, "")
            f = QFont(it.font(0))
            f.setBold(True)
            f.setItalic(True)
            it.setFont(0, f)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._fill_sections(it)
        for sub in folder.folders:
            it = QTreeWidgetItem(parent, [sub.name, ""])
            it.setData(0, PATH, str(sub.path))
            it.setData(0, KIND, "folder")
            it.setIcon(0, style.standardIcon(QStyle.SP_DirIcon))
            it.setFlags(it.flags() | Qt.ItemIsEditable | Qt.ItemIsDropEnabled)
            self._add(it, sub, open_all)
            it.setExpanded(open_all or str(sub.path) in self._expanded
                           or self._contains_current(sub))
        for info in folder.notes:
            it = QTreeWidgetItem(parent, [info.label, _short_date(info.date)])
            it.setData(0, PATH, str(info.path))
            it.setData(0, KIND, "note")
            it.setToolTip(0, f"{info.label}\n{info.date}\n{info.path}")
            it.setForeground(1, theme.color("muted"))
            it.setFlags((it.flags() | Qt.ItemIsEditable) & ~Qt.ItemIsDropEnabled)
            if self.current is not None and Path(info.path) == self.current:
                f = QFont(it.font(0))
                f.setBold(True)
                it.setFont(0, f)
                self._fill_sections(it)
                it.setExpanded(True)

    def set_pending(self, folder: Optional[Path]) -> None:
        self.pending = Path(folder) if folder is not None else None
        if self.pending is not None:
            self._expanded.add(str(self.pending))

    def _fill_sections(self, note_item: QTreeWidgetItem) -> None:
        # Restore, not unblock: this also runs inside refresh().
        was = self.tree.blockSignals(True)
        note_item.takeChildren()
        for level, title, number in self._sections:
            sec = QTreeWidgetItem(note_item, [("  " * (level - 1)) + (title or "Untitled section"), ""])
            sec.setData(0, KIND, "section")
            sec.setData(0, BLOCK, number)
            sec.setForeground(0, theme.color("heading"))
            sec.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        note_item.setExpanded(True)
        self.tree.blockSignals(was)

    def _contains_current(self, folder: library.Folder) -> bool:
        here = self.current or (self.pending / "x" if self.pending is not None else None)
        return here is not None and folder.path in here.parents

    def _all_items(self):
        stack = [self.tree.invisibleRootItem()]
        while stack:
            item = stack.pop()
            for i in range(item.childCount()):
                child = item.child(i)
                yield child
                stack.append(child)

    def _find(self, path: Optional[Path]) -> Optional[QTreeWidgetItem]:
        if path is None:
            return None
        for item in self._all_items():
            if item.data(0, KIND) == "note" and Path(item.data(0, PATH)) == path:
                return item
        return None

    # ── selection ──────────────────────────────────────────────────

    def folder_of(self, item: Optional[QTreeWidgetItem]) -> Path:
        while item is not None and item.data(0, KIND) == "section":
            item = item.parent()
        if item is None:
            return self.root
        path = Path(item.data(0, PATH))
        return path if item.data(0, KIND) == "folder" else path.parent

    def selected_folder(self) -> Path:
        items = self.tree.selectedItems()
        return self.folder_of(items[0] if items else None)

    def _clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        kind = item.data(0, KIND)
        if kind == "note" and Path(item.data(0, PATH)) != self.current:
            self.open_note.emit(Path(item.data(0, PATH)))
        elif kind == "section":
            self.go_to_section.emit(item.data(0, BLOCK))

    def _activated(self, item: QTreeWidgetItem, col: int) -> None:
        self._clicked(item, col)

    # ── file operations ────────────────────────────────────────────

    def _edited(self, item: QTreeWidgetItem, col: int) -> None:
        if col != 0 or item.data(0, KIND) not in ("folder", "note"):
            return
        old = Path(item.data(0, PATH))
        try:
            new = library.rename(old, item.text(0))
        except OSError as exc:
            QMessageBox.warning(self, "Rename", f"Could not rename:\n{exc}")
            new = old
        if new != old:
            self.moved.emit(old, new)
        self.refresh()

    def _drop(self, paths: list, dest: Path) -> None:
        for src in paths:
            try:
                new = library.move(src, dest)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Move", f"Could not move {src.name}:\n{exc}")
                continue
            if new != src:
                self.moved.emit(src, new)
        self.refresh()

    def _make_folder(self, parent: Path) -> None:
        path = library.make_folder(parent)
        self._expanded.add(str(parent))
        self.refresh()
        for item in self._all_items():
            if item.data(0, PATH) == str(path):
                self.tree.setCurrentItem(item)
                self.tree.editItem(item, 0)

    def _trash(self, items: list[QTreeWidgetItem]) -> None:
        paths = [Path(i.data(0, PATH)) for i in items if i.data(0, KIND) in ("folder", "note")]
        if not paths:
            return
        names = "\n".join(p.name for p in paths[:8])
        if QMessageBox.question(self, "Move to Trash",
                                f"Move to the Trash?\n\n{names}") != QMessageBox.Yes:
            return
        for p in paths:
            if QFile.moveToTrash(str(p)):
                self.trashed.emit(p)
            else:
                QMessageBox.warning(self, "Move to Trash", f"Could not move {p.name} to the Trash.")
        self.refresh()

    def _menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is not None and not item.isSelected():
            self.tree.setCurrentItem(item)
        folder = self.folder_of(item)
        menu = QMenu(self)
        menu.addAction("New note here", lambda: self.new_note.emit(folder))
        menu.addAction("New folder here", lambda: self._make_folder(folder))
        if item is not None and item.data(0, KIND) in ("folder", "note"):
            menu.addSeparator()
            menu.addAction("Rename", lambda: self.tree.editItem(item, 0))
            path = Path(item.data(0, PATH))
            menu.addAction("Show in Finder" if _is_mac() else "Show in folder",
                           lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(
                               str(path if path.is_dir() else path.parent))))
            menu.addSeparator()
            menu.addAction("Move to Trash", lambda: self._trash(self.tree.selectedItems()))
        menu.exec(self.tree.viewport().mapToGlobal(pos))


def _short_date(date: str) -> str:
    from datetime import datetime
    for fmt in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date.strip(), fmt).strftime("%d %b %y")
        except ValueError:
            continue
    return date[:12]


def _is_mac() -> bool:
    import sys
    return sys.platform == "darwin"
