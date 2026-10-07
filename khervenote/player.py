# KherveNote — hearing what was said
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Plays a stretch of a recording — one line of speech, or on from a
point — so a doubtful word or number can be checked by ear."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaDevices, QMediaPlayer


def device_id(dev: QAudioDevice) -> str:
    return bytes(dev.id()).decode("utf-8", "replace")


def output_devices() -> list[QAudioDevice]:
    return list(QMediaDevices.audioOutputs())


class LinePlayer(QObject):
    #: Playing (True) or not, and what is playing.
    state = Signal(bool, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        #: The chosen speakers' id; "" follows the system default.
        self.device = ""
        self._devices = QMediaDevices(self)
        self._devices.audioOutputsChanged.connect(self._apply_device)
        self.player.positionChanged.connect(self._position)
        self.player.mediaStatusChanged.connect(self._status)
        self.player.playbackStateChanged.connect(self._playback)
        self._source = ""
        self._start_ms = 0
        self._end_ms: Optional[int] = None
        self._pending = False
        self.label = ""

    def set_device(self, dev_id: str) -> None:
        """Play through the speakers / headphones *dev_id* ("" = the
        system default, followed when it changes)."""
        self.device = dev_id
        self._apply_device()

    def _apply_device(self) -> None:
        # A chosen device that is unplugged falls back to the default,
        # and comes back by itself when plugged in again.
        chosen = next((d for d in output_devices() if device_id(d) == self.device), None)
        dev = chosen or QMediaDevices.defaultAudioOutput()
        if dev.id() != self.output.device().id():
            self.output.setDevice(dev)

    def device_name(self) -> str:
        return self.output.device().description()

    def play(self, path: str, start_s: float, end_s: Optional[float] = None,
             label: str = "") -> None:
        """Play *path* from *start_s* seconds, stopping at *end_s* (or at
        the end of the recording)."""
        self._start_ms = max(0, int(start_s * 1000))
        self._end_ms = None if end_s is None else int(end_s * 1000)
        self.label = label
        if path != self._source:
            self._source = path
            self._pending = True
            self.player.setSource(QUrl.fromLocalFile(path))
        else:
            self._begin()

    def _status(self, status) -> None:
        if self._pending and status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self._pending = False
            self._begin()
        elif status == QMediaPlayer.InvalidMedia:
            self._pending = False
            self.state.emit(False, "This recording cannot be played.")

    def _begin(self) -> None:
        self.player.setPosition(self._start_ms)
        self.player.play()

    def _position(self, ms: int) -> None:
        if self._end_ms is not None and ms >= self._end_ms:
            self.player.pause()

    def _playback(self, st) -> None:
        self.state.emit(st == QMediaPlayer.PlayingState, self.label)

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self._source:
            # Carry on past the line that was asked for.
            self._end_ms = None
            self.player.play()

    def stop(self) -> None:
        self.player.stop()
        self._end_ms = None

    def release(self) -> None:
        """Let go of the file (its note is being closed)."""
        self.stop()
        self.player.setSource(QUrl())
        self._source = ""

    @property
    def playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlayingState

    def position_s(self) -> float:
        return self.player.position() / 1000.0
