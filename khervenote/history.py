# KherveNote — earlier versions of notes
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Before a note's file is overwritten, the version on disk is kept in
``<library>/.history/<note id>/`` — at most one every few minutes, the
newest few dozen — so nothing a bug, a second window or a mistaken edit
does can lose a note for good.  Restoring always makes a new file; a
version is never written back over a note.  Qt-free.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .knote_file import EXTENSION, NOTE_JSON

HISTORY = ".history"
#: Seconds between two kept versions of the same note.
MIN_INTERVAL = 300
#: Versions kept per note.
KEEP = 40


@dataclass
class Version:
    path: Path
    when: datetime
    title: str
    first_line: str
    size: int


def folder(root: Path, note_id: str) -> Path:
    return Path(root) / HISTORY / note_id


def snapshot(root: Path, note_id: str, path: Path, force: bool = False) -> Optional[Path]:
    """Keep a copy of the note at *path* as it is on disk now, unless the
    newest kept version was saved less than MIN_INTERVAL before it.
    Copies keep the note's own modification time, so that is what is
    compared.  Returns the copy, or None if none was needed."""
    path = Path(path)
    if not note_id or not path.is_file():
        return None
    dest_dir = folder(root, note_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(dest_dir.glob("*" + EXTENSION), key=lambda p: p.stat().st_mtime)
    if existing and not force:
        if path.stat().st_mtime - existing[-1].stat().st_mtime < MIN_INTERVAL:
            return None
    stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H.%M.%S")
    dest = dest_dir / f"{stamp}{EXTENSION}"
    n = 2
    while dest.exists():
        dest = dest_dir / f"{stamp} ({n}){EXTENSION}"
        n += 1
    shutil.copy2(path, dest)
    for old in sorted(dest_dir.glob("*" + EXTENSION),
                      key=lambda p: p.stat().st_mtime)[:-KEEP]:
        old.unlink()
    return dest


def versions(root: Path, note_id: str) -> list[Version]:
    """Kept versions of a note, newest first."""
    out = []
    for p in sorted(folder(root, note_id).glob("*" + EXTENSION),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        title, first = "", ""
        try:
            with zipfile.ZipFile(p) as zf:
                d = json.loads(zf.read(NOTE_JSON).decode("utf-8"))
            title = d.get("meta", {}).get("title", "")
            for sec in d.get("sections", []):
                first = sec.get("title", "") or next(
                    (b.get("text", "") for b in sec.get("blocks", []) if b.get("text")), "")
                if first:
                    break
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            pass
        out.append(Version(p, datetime.fromtimestamp(p.stat().st_mtime), title,
                           first[:80], p.stat().st_size))
    return out


def restore_copy(version: Path, dest_folder: Path, stem: str) -> Path:
    """Copy a kept version into *dest_folder* as a new note."""
    from .library import unique_path
    dest = unique_path(Path(dest_folder), stem)
    shutil.copy2(version, dest)
    return dest
