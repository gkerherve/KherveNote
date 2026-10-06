# KherveNote — recordings that survive a crash
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""While listening, the recording is written to a recovery folder of
its own — not the note's temporary folder, which a crash would leave
behind unreferenced — together with a label saying which note it belongs
to.  When listening stops and the note has been saved, the folder is
removed; if KherveNote stopped before that, the next start finds it and
offers to put the recording back.  Qt-free.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

LABEL = "recording.json"


def recovery_dir() -> Path:
    if os.environ.get("KHERVENOTE_RECOVERY_DIR"):          # tests
        return Path(os.environ["KHERVENOTE_RECOVERY_DIR"])
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "KherveNote" / "recovery"


@dataclass
class Pending:
    folder: Path
    audio: Path
    note_path: str
    note_id: str
    note_title: str
    t0: float
    started: str            # when the recording began (ISO)

    @property
    def when(self) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(self.started)
        except ValueError:
            return None


def begin(note_id: str, note_path: str, note_title: str, t0: float) -> Path:
    """A fresh recovery folder for one recording; returns the audio path
    to record into."""
    folder = recovery_dir() / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True)
    _write(folder, {"note_id": note_id, "note_path": note_path, "note_title": note_title,
                    "t0": t0, "started": datetime.now().isoformat(timespec="seconds")})
    return folder / "recording.ogg"


def _write(folder: Path, label: dict) -> None:
    tmp = folder / (LABEL + ".tmp")
    tmp.write_text(json.dumps(label, indent=1), encoding="utf-8")
    os.replace(tmp, folder / LABEL)


def set_note(audio: Path, note_path: str, note_title: str) -> None:
    """The note got a file (or a new title) while recording."""
    folder = Path(audio).parent
    try:
        label = json.loads((folder / LABEL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    label.update(note_path=note_path, note_title=note_title)
    _write(folder, label)


def finish(audio: Path) -> None:
    """The recording is safely in a saved note: forget it here."""
    folder = Path(audio).parent
    if folder.parent == recovery_dir() and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def pending(exclude: tuple = ()) -> list[Pending]:
    """Recordings left behind by a run that did not finish them, oldest
    first.  Empty ones (stopped before any sound) are cleaned away."""
    root = recovery_dir()
    out = []
    if not root.is_dir():
        return out
    for folder in sorted(root.iterdir()):
        audio = next(iter(sorted(folder.glob("*.ogg")) + sorted(folder.glob("*.flac"))), None)
        if folder in exclude or (audio is not None and audio in exclude):
            continue
        if audio is None or audio.stat().st_size < 1024:
            shutil.rmtree(folder, ignore_errors=True)
            continue
        try:
            label = json.loads((folder / LABEL).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            label = {}
        out.append(Pending(folder, audio, label.get("note_path", ""), label.get("note_id", ""),
                           label.get("note_title", ""), float(label.get("t0", 0.0)),
                           label.get("started", "")))
    return out


def duration(audio: Path) -> float:
    """Length of a recording, even one cut short by a crash."""
    try:
        import soundfile as sf
        return float(sf.info(str(audio)).duration)
    except Exception:  # noqa: BLE001 — a damaged file: estimate from Opus at ~24 kbit/s
        return Path(audio).stat().st_size / 3000.0
