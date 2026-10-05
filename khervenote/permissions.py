# KherveNote — OS permissions
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ask the OS for the camera or the microphone before using them.

Qt's permission API only works from an app bundle whose Info.plist
explains the use (``NSMicrophoneUsageDescription``,
``NSCameraUsageDescription``); asked from a plain Python process it
refuses at once.  Run from source, macOS asks on behalf of the terminal
or IDE when the device is opened, so Qt is skipped there.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

_NAMES = {"camera": ("QCameraPermission", "Camera"),
          "microphone": ("QMicrophonePermission", "Microphone")}


def _denied(kind: str, parent) -> None:
    label = _NAMES[kind][1]
    QMessageBox.warning(parent, label, (
        f"KherveNote is not allowed to use the {kind}.\n\nAllow it in System "
        f"Settings ▸ Privacy & Security ▸ {label}, then try again."))


def with_permission(kind: str, parent, then) -> None:
    """Run *then()* once the OS allows *kind* ("camera" / "microphone"),
    asking the user at most once."""
    if not getattr(sys, "frozen", False):
        then()
        return
    try:
        import PySide6.QtCore as core
        perm = getattr(core, _NAMES[kind][0])()
    except (ImportError, AttributeError):     # Qt < 6.5: no permission API
        then()
        return
    app = QApplication.instance()
    status = app.checkPermission(perm)
    if status == Qt.PermissionStatus.Granted:
        then()
    elif status == Qt.PermissionStatus.Denied:
        _denied(kind, parent)
    else:
        def answered(p) -> None:
            # Never ask again from here: a refusal must end the attempt.
            if p.status() == Qt.PermissionStatus.Granted:
                then()
            else:
                _denied(kind, parent)
        app.requestPermission(perm, parent, answered)
