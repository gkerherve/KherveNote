# KherveNote — themes
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Light and dark colour sets for the window, the page and the icons.

The palette is always set explicitly (Fusion): left to the platform, the
Windows dark theme paints the drawn icons and the page unreadable.
"System" follows the OS light/dark setting at start-up and when it
changes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#f3f3f3", "page": "#ffffff", "text": "#1c1c1c",
        "muted": "#8a8a8a", "heading": "#1a3f75", "accent": "#1a6dd8",
        "accent2": "#d96b00", "key_bg": "#fbeee2", "key_fg": "#a84f00",
        "question": "#1a4f9c", "button": "#ececec", "border": "#d6d6d6",
        "highlight": "#1a6dd8", "highlight_text": "#ffffff", "red": "#d0302b",
    },
    "dark": {
        "window": "#1f1f1f", "page": "#0f0f0f", "text": "#e4e4e4",
        "muted": "#8c8c8c", "heading": "#9cc2ff", "accent": "#6cb4ff",
        "accent2": "#f0a050", "key_bg": "#3a2914", "key_fg": "#f3b06a",
        "question": "#9cc2ff", "button": "#2b2b2b", "border": "#3a3a3a",
        "highlight": "#2f6fc0", "highlight_text": "#ffffff", "red": "#ff5a52",
    },
}
CHOICES = ("system", "light", "dark")

_current = "light"


def resolve(choice: str) -> str:
    if choice in THEMES:
        return choice
    hints = QGuiApplication.styleHints()
    dark = hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark
    return "dark" if dark else "light"


def current() -> str:
    return _current


def color(key: str) -> QColor:
    return QColor(THEMES[_current][key])


def hex_(key: str) -> str:
    return THEMES[_current][key]


def apply(app, choice: str) -> str:
    """Set the application palette for *choice*; returns light/dark."""
    global _current
    _current = resolve(choice)
    t = THEMES[_current]
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in (
            (QPalette.Window, "window"), (QPalette.WindowText, "text"),
            (QPalette.Base, "page"), (QPalette.AlternateBase, "button"),
            (QPalette.Text, "text"), (QPalette.Button, "button"),
            (QPalette.ButtonText, "text"), (QPalette.Highlight, "highlight"),
            (QPalette.HighlightedText, "highlight_text"),
            (QPalette.ToolTipBase, "window"), (QPalette.ToolTipText, "text"),
            (QPalette.PlaceholderText, "muted"), (QPalette.Link, "accent"),
            (QPalette.Mid, "border"), (QPalette.Midlight, "border")):
        pal.setColor(role, QColor(t[key]))
    for role in (QPalette.ButtonText, QPalette.WindowText, QPalette.Text):
        pal.setColor(QPalette.Disabled, role, QColor(t["muted"]))
    app.setPalette(pal)
    return _current
