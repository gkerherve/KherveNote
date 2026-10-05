# KherveNote — .knote file format
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read and write ``.knote`` files.

A ``.knote`` is a zip: ``note.json`` (the model) plus ``assets/`` (images
now; the recording and imported documents later).  While a note is open
its assets live in a working directory, so the page and the compiler
can use them as plain files; saving zips that directory back up.
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

from .model import Note

NOTE_JSON = "note.json"
EXTENSION = ".knote"


def save_knote(note: Note, path: str | os.PathLike, work_dir: str | os.PathLike) -> None:
    """Write *note* and the assets it references to *path*.

    Written to a temporary file in the same folder and swapped in, so a
    failure half-way (full disk, OneDrive lock) never leaves the user
    with a truncated note.
    """
    path = Path(path)
    work_dir = Path(work_dir)
    fd, tmp = tempfile.mkstemp(prefix=".knote-", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(NOTE_JSON, json.dumps(note.to_dict(), indent=1,
                                              ensure_ascii=False))
            for rel in sorted(set(note.asset_paths())):
                src = work_dir / rel
                if src.is_file():
                    # Images are already compressed; deflating them again
                    # only costs time.
                    zf.write(src, rel, compress_type=zipfile.ZIP_STORED)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_knote(path: str | os.PathLike, work_dir: str | os.PathLike) -> Note:
    """Read *path*, unpacking its assets into *work_dir*."""
    work_dir = Path(work_dir).resolve()
    with zipfile.ZipFile(path) as zf:
        note = Note.from_dict(json.loads(zf.read(NOTE_JSON).decode("utf-8")))
        for name in zf.namelist():
            if name == NOTE_JSON or name.endswith("/"):
                continue
            dest = (work_dir / name).resolve()
            # A crafted zip could name ../../something; refuse to write
            # outside the working directory.
            if work_dir not in dest.parents:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
    return note
