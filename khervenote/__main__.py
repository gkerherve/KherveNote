# KherveNote — entry point
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""``python -m khervenote [note.knote]`` opens the main window."""
from __future__ import annotations

import os
import sys
import tempfile
from typing import Optional

from PySide6.QtCore import QLockFile, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from . import theme


def _user() -> str:
    """Who runs this, for the lock name (Windows has no ``os.getuid``)."""
    if hasattr(os, "getuid"):
        return str(os.getuid())
    return os.environ.get("USERNAME", "user")


def _single_instance() -> Optional[QLockFile]:
    """The lock that makes this the only KherveNote running.  Two windows
    reopen the same note and each save over the other's, so a second
    one must not start.  A lock left by a crashed run is taken over."""
    lock = QLockFile(os.path.join(tempfile.gettempdir(), f"khervenote-{_user()}.lock"))
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(200) else None


def main() -> None:
    if "--self-test" in sys.argv:
        from .selftest import run
        sys.exit(run(sys.argv[sys.argv.index("--self-test") + 1:]))
    if getattr(sys, "frozen", False):
        # Release builds carry tectonic and a warmed TeX cache: put the
        # cache where tectonic looks, so PDF export works offline at once.
        from .compiler import seed_tectonic_cache
        try:
            seed_tectonic_cache()
        except OSError:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("KherveNote")
    app.setOrganizationName("KherveTools")
    # Before any window exists, so nothing is ever drawn in the
    # platform palette (see theme.py).
    theme.apply(app, QSettings("KherveTools", "KherveNote").value("view/theme", "system"))
    lock = _single_instance()
    if lock is None:
        QMessageBox.information(None, "KherveNote", (
            "KherveNote is already open.\n\nUse the window that is open — two at once "
            "would save over each other's notes."))
        sys.exit(0)
    from .mainwindow import MainWindow
    path = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
