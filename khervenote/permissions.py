# KherveNote — OS permissions
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ask the OS for the camera or the microphone before using them."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

_NAMES = {"camera": ("QCameraPermission", "Camera"),
          "microphone": ("QMicrophonePermission", "Microphone")}


def with_permission(kind: str, parent, then) -> None:
    """Run *then()* once the OS allows *kind* ("camera" / "microphone"),
    asking the user if it has not been decided yet."""
    cls_name, label = _NAMES[kind]
    try:
        import PySide6.QtCore as core
        perm = getattr(core, cls_name)()
    except (ImportError, AttributeError):     # Qt < 6.5: no permission API
        then()
        return
    app = QApplication.instance()
    status = app.checkPermission(perm)
    if status == Qt.PermissionStatus.Granted:
        then()
    elif status == Qt.PermissionStatus.Denied and not getattr(sys, "frozen", False):
        # Run from source, the OS asks on behalf of the terminal or IDE,
        # which Qt cannot see — try, and let the OS decide.
        then()
    elif status == Qt.PermissionStatus.Denied:
        QMessageBox.warning(parent, label, f"KherveNote is not allowed to use the {kind}. "
                            f"Allow it in the system privacy settings ({label}) and try again.")
    else:
        app.requestPermission(perm, parent, lambda _p: with_permission(kind, parent, then))
