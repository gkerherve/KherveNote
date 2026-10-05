# KherveNote — the notes library
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""All notes live in one folder (``~/Documents/KherveNote`` by default)
whose sub-folders are the folders of the Notes panel — plain files and
folders, so they can be synced, backed up or tidied in Finder too.

Reading a note's title, date and text only opens ``note.json`` inside the
zip, never the pictures or recordings, so scanning stays fast.  Qt-free.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .knote_file import EXTENSION, NOTE_JSON
from .model import Note


def default_root() -> Path:
    return Path.home() / "Documents" / "KherveNote"


@dataclass
class NoteInfo:
    path: Path
    title: str
    date: str
    started: str
    text: str           # everything searchable, lower-cased
    first_line: str = ""

    @property
    def label(self) -> str:
        """Its title; a note without one shows its first words, which say
        more than "Note 2026-10-05 14.16"."""
        if self.title.strip():
            return self.title.strip()
        if self.first_line:
            words = self.first_line.split()
            short = " ".join(words[:8])
            return short + ("…" if len(words) > 8 else "")
        return self.path.stem


@dataclass
class Folder:
    path: Path
    folders: list["Folder"] = field(default_factory=list)
    notes: list[NoteInfo] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name


_CACHE: dict[Path, tuple[float, NoteInfo]] = {}


def read_info(path: Path) -> NoteInfo:
    """Title, date and searchable text of the note at *path* (cached
    until the file changes)."""
    path = Path(path)
    mtime = path.stat().st_mtime
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        with zipfile.ZipFile(path) as zf:
            note = Note.from_dict(json.loads(zf.read(NOTE_JSON).decode("utf-8")))
        m = note.meta
        text = " ".join([m.title, m.speaker, m.date, m.place, note.summary,
                         note.plain_text()]).lower()
        first = next((t for sec in note.sections
                      for t in [sec.title] + [b.text for b in sec.blocks if b.text]
                      if t.strip()), "")
        info = NoteInfo(path, m.title, m.date, m.started, text, first.strip())
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        info = NoteInfo(path, "", "", "", path.stem.lower())
    _CACHE[path] = (mtime, info)
    return info


def _sort_key(info: NoteInfo) -> str:
    # Newest first: the session start, falling back to the file time.
    if info.started:
        return info.started
    return datetime.fromtimestamp(info.path.stat().st_mtime).isoformat()


def scan(root: Path) -> Folder:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return _scan(root)


def _scan(folder: Path) -> Folder:
    out = Folder(folder)
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
    except OSError:
        return out
    for e in entries:
        if e.name.startswith("."):
            continue
        if e.is_dir():
            out.folders.append(_scan(Path(e.path)))
        elif e.name.endswith(EXTENSION):
            out.notes.append(read_info(Path(e.path)))
    out.notes.sort(key=_sort_key, reverse=True)
    return out


def matches(info: NoteInfo, query: str) -> bool:
    """Every word of *query* appears in the note (title, date, people,
    text) or in its file name."""
    words = query.lower().split()
    hay = info.text + " " + info.path.stem.lower()
    return all(w in hay for w in words)


def filter_tree(folder: Folder, query: str) -> Optional[Folder]:
    """The part of the tree that matches *query*: matching notes, plus
    folders whose name matches (with everything in them)."""
    if not query.strip():
        return folder
    words = query.lower().split()
    if all(w in folder.name.lower() for w in words):
        return folder
    kept = Folder(folder.path)
    kept.folders = [f for f in (filter_tree(sub, query) for sub in folder.folders) if f]
    kept.notes = [n for n in folder.notes if matches(n, query)]
    return kept if kept.folders or kept.notes else None


_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(name: str, fallback: str = "Untitled") -> str:
    name = _UNSAFE.sub(" ", name).strip().strip(".")
    return re.sub(r"\s+", " ", name)[:80] or fallback


def unique_path(folder: Path, stem: str, suffix: str = EXTENSION) -> Path:
    path = folder / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}){suffix}"
        n += 1
    return path


def new_note_path(folder: Path, title: str, now: Optional[datetime] = None) -> Path:
    now = now or datetime.now()
    stem = safe_name(title) if title.strip() else f"Note {now:%Y-%m-%d %H.%M}"
    folder.mkdir(parents=True, exist_ok=True)
    return unique_path(folder, stem)


def make_folder(parent: Path, name: str = "New folder") -> Path:
    path = unique_path(parent, safe_name(name, "New folder"), "")
    path.mkdir(parents=True)
    return path


def move(src: Path, dest_folder: Path) -> Path:
    """Move a note or folder into *dest_folder*; returns its new path.
    A name already taken there gets " (2)"."""
    src, dest_folder = Path(src), Path(dest_folder)
    if src.parent == dest_folder:
        return src
    if src.is_dir() and (dest_folder == src or src in dest_folder.parents):
        raise ValueError("A folder cannot go inside itself.")
    suffix = "" if src.is_dir() else src.suffix
    stem = src.name if src.is_dir() else src.stem
    dest = unique_path(dest_folder, stem, suffix)
    shutil.move(str(src), str(dest))
    _CACHE.pop(src, None)
    return dest


def rename(src: Path, new_name: str) -> Path:
    src = Path(src)
    suffix = "" if src.is_dir() else src.suffix
    stem = safe_name(new_name, src.stem)
    if stem == (src.name if src.is_dir() else src.stem):
        return src
    dest = unique_path(src.parent, stem, suffix)
    src.rename(dest)
    _CACHE.pop(src, None)
    return dest
