# KherveNote — entry point
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""``python -m khervenote [note.knote]`` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from . import theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("KherveNote")
    app.setOrganizationName("KherveTools")
    # Before any window exists, so nothing is ever drawn in the
    # platform palette (see theme.py).
    theme.apply(app, QSettings("KherveTools", "KherveNote").value("view/theme", "system"))
    from .mainwindow import MainWindow
    path = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
