# KherveNote — camera capture
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Take a picture with the computer's camera — a whiteboard, a slide,
a handout — and drop it into the note."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)


def cameras() -> list:
    return list(QMediaDevices.videoInputs())


def with_camera_permission(parent, then) -> None:
    """Run *then()* once the OS allows camera use, asking if needed."""
    try:
        from PySide6.QtCore import QCameraPermission
    except ImportError:          # Qt < 6.5: no permission API, just try
        then()
        return
    app = QApplication.instance()
    perm = QCameraPermission()
    status = app.checkPermission(perm)
    if status == Qt.PermissionStatus.Granted:
        then()
    elif status == Qt.PermissionStatus.Denied:
        QMessageBox.warning(parent, "Camera", "KherveNote is not allowed to use the camera. "
                            "Allow it in the system privacy settings (Camera) and try again.")
    else:
        app.requestPermission(perm, parent, lambda p: with_camera_permission(parent, then))


class CameraDialog(QDialog):
    """Live preview; Take picture (or Space) closes with the photo."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Take a picture")
        self.resize(760, 560)
        self.image: Optional[QImage] = None
        self.session = QMediaCaptureSession(self)
        self.capture = QImageCapture(self)
        self.session.setImageCapture(self.capture)
        self.preview = QVideoWidget()
        self.session.setVideoOutput(self.preview)
        self.capture.imageCaptured.connect(self._captured)
        self.capture.errorOccurred.connect(
            lambda _id, _err, msg: self.status.setText(f"Could not take the picture: {msg}"))
        self.camera: Optional[QCamera] = None

        self.devices = QComboBox()
        self._inputs = cameras()
        for dev in self._inputs:
            self.devices.addItem(dev.description())
        default = QMediaDevices.defaultVideoInput()
        for i, dev in enumerate(self._inputs):
            if dev.id() == default.id():
                self.devices.setCurrentIndex(i)
        self.devices.currentIndexChanged.connect(self._start)
        self.shoot = QPushButton("Take picture")
        self.shoot.setDefault(True)
        self.shoot.clicked.connect(self.take)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.take)
        self.status = QLabel("")

        row = QHBoxLayout()
        row.addWidget(QLabel("Camera:"))
        row.addWidget(self.devices, 1)
        row.addWidget(cancel)
        row.addWidget(self.shoot)
        col = QVBoxLayout(self)
        col.addWidget(self.preview, 1)
        col.addWidget(self.status)
        col.addLayout(row)
        self._start()

    def _start(self, *_) -> None:
        if self.camera is not None:
            self.camera.stop()
            self.camera.deleteLater()
        if not self._inputs:
            self.status.setText("No camera found.")
            self.shoot.setEnabled(False)
            return
        self.camera = QCamera(self._inputs[self.devices.currentIndex()], self)
        self.camera.errorOccurred.connect(lambda _e, msg: self.status.setText(msg))
        self.session.setCamera(self.camera)
        self.camera.start()

    def take(self) -> None:
        if self.capture.isReadyForCapture():
            self.shoot.setEnabled(False)
            self.capture.capture()
        else:
            self.status.setText("The camera is not ready yet…")

    def _captured(self, _id: int, image: QImage) -> None:
        self.image = image
        self.accept()

    def done(self, result: int) -> None:  # noqa: D401 — QDialog override
        if self.camera is not None:
            self.camera.stop()
        super().done(result)
