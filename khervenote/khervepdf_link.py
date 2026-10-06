# KherveNote — opening PDFs in KhervePDF
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""PDFs attached to a note open in KhervePDF, the KherveTools PDF viewer
and annotator (sibling repo ``../KhervePDF``).

The contract is KhervePDF's own single-instance channel: a JSON line
``{"cmd": "open", "paths": [...]}`` on the local socket
``khervepdf-<user>`` makes a running KhervePDF open the files as tabs.
When none is running, KherveNote starts one — the installed app, or a
source checkout next to this one — with the file as its argument.
Nothing here imports KhervePDF.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


def server_name() -> str:
    """KhervePDF's single-instance socket (same rule as its own
    ``single_instance.server_name``)."""
    if os.environ.get("KHERVEPDF_IPC_NAME"):
        return os.environ["KHERVEPDF_IPC_NAME"]
    user = re.sub(r"[^A-Za-z0-9_]", "_", getpass.getuser() or "user")
    return f"khervepdf-{user}"


def send_to_running(paths: list[str], timeout_ms: int = 800) -> bool:
    """True when a running KhervePDF took the files."""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write((json.dumps({"cmd": "open", "paths": paths}) + "\n").encode())
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    # Hang up only once KhervePDF has answered: closing at once can lose
    # the request (Windows named pipes).  Same as KhervePDF's own client.
    sock.waitForReadyRead(5000)
    sock.disconnectFromServer()
    return True


def _sibling_checkout() -> Optional[Path]:
    here = Path(__file__).resolve().parent.parent
    repo = here.parent / "KhervePDF"
    return repo if (repo / "KhervePDF.py").is_file() else None


def bundled_khervepdf() -> Optional[Path]:
    """The KhervePDF a release build carries: ``KhervePDF/KhervePDF.exe``
    beside ``KherveNote.exe``, or ``Contents/Helpers/KhervePDF.app``
    inside ``KherveNote.app``.  None when run from source."""
    if not getattr(sys, "frozen", False):
        return None
    here = Path(sys.executable).resolve().parent
    if sys.platform == "darwin":
        p = here.parent / "Helpers" / "KhervePDF.app"      # Contents/MacOS -> Contents
        return p if p.is_dir() else None
    p = here / "KhervePDF" / ("KhervePDF.exe" if sys.platform == "win32" else "KhervePDF")
    return p if p.is_file() else None


def bundled_executable() -> Optional[Path]:
    """The bundled KhervePDF's own executable (inside the .app on a Mac)."""
    p = bundled_khervepdf()
    if p is not None and p.suffix == ".app":
        p = p / "Contents" / "MacOS" / "KhervePDF"
    return p if p is not None and p.is_file() else None


def launch_command(paths: list[str], configured: str = "") -> Optional[list[str]]:
    """How to start KhervePDF with *paths*, or None if it is not here.

    Looked for in order: a path the user set (an app, an .exe or a
    checkout), the installed app, the copy the KherveNote installer
    ships, a source checkout beside KherveNote.
    """
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if sys.platform == "darwin":
        candidates += [Path("/Applications/KhervePDF.app"),
                       Path.home() / "Applications" / "KhervePDF.app"]
    elif sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidates.append(Path(base) / "KhervePDF" / "KhervePDF.exe")
                candidates.append(Path(base) / "Programs" / "KhervePDF" / "KhervePDF.exe")
    bundled = bundled_khervepdf()
    if bundled is not None:
        candidates.append(bundled)
    checkout = _sibling_checkout()
    if checkout is not None:
        candidates.append(checkout)
    for c in candidates:
        if c.suffix == ".app" and c.is_dir():
            return ["open", "-a", str(c), *paths]
        if c.is_file() and c.suffix.lower() == ".exe":
            return [str(c), *paths]
        if c.is_dir() and (c / "KhervePDF.py").is_file():
            py = _venv_python(c) or sys.executable
            return [py, str(c / "KhervePDF.py"), *paths]
    return None


def _venv_python(repo: Path) -> Optional[str]:
    for rel in (".venv/bin/python", "venv/bin/python",
                ".venv/Scripts/python.exe", "venv/Scripts/python.exe"):
        p = repo / rel
        if p.is_file():
            return str(p)
    return None


def open_pdf(path: str, configured: str = "") -> str:
    """Open *path* in KhervePDF.  Returns "running" (a tab in the open
    window), "started", or "missing" (KhervePDF was not found)."""
    path = str(Path(path).resolve())
    if send_to_running([path]):
        return "running"
    cmd = launch_command([path], configured)
    if cmd is None:
        return "missing"
    kw: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, cwd=str(Path(path).parent))
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True      # KhervePDF outlives KherveNote
    subprocess.Popen(cmd, **kw)
    return "started"
