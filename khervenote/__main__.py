# KherveNote — entry point
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""``python -m khervenote [note.knote]`` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _light_palette(app: QApplication) -> None:
    """A fixed light Fusion palette: the Windows dark theme makes the
    painted toolbar icons and the white page unreadable."""
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in (
            (QPalette.Window, "#f7f7f7"), (QPalette.WindowText, "#1c1c1c"),
            (QPalette.Base, "#ffffff"), (QPalette.AlternateBase, "#eef1f5"),
            (QPalette.Text, "#1c1c1c"), (QPalette.Button, "#f0f0f0"),
            (QPalette.ButtonText, "#1c1c1c"), (QPalette.Highlight, "#1a6dd8"),
            (QPalette.HighlightedText, "#ffffff"), (QPalette.ToolTipBase, "#ffffdc"),
            (QPalette.ToolTipText, "#1c1c1c"), (QPalette.PlaceholderText, "#9a9a9a"),
            (QPalette.Link, "#1a6dd8")):
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9a9a9a"))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9a9a9a"))
    app.setPalette(pal)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("KherveNote")
    app.setOrganizationName("KherveTools")
    _light_palette(app)
    from .mainwindow import MainWindow
    path = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
