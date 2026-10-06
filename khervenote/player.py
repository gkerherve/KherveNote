# KherveNote — hearing what was said
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Plays a stretch of a recording — one line of speech, or on from a
point — so a doubtful word or number can be checked by ear."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class LinePlayer(QObject):
    #: Playing (True) or not, and what is playing.
    state = Signal(bool, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(self._position)
        self.player.mediaStatusChanged.connect(self._status)
        self.player.playbackStateChanged.connect(self._playback)
        self._source = ""
        self._start_ms = 0
        self._end_ms: Optional[int] = None
        self._pending = False
        self.label = ""

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
