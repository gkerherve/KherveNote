# KherveNote — microphone capture and chunking
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Microphone → 16 kHz mono float frames → speech chunks.

Whisper works on whole utterances, so the stream is cut where the
speaker pauses (``Chunker``): at least ``min_s`` of audio, ended by
``pause_s`` of quiet, and never longer than ``max_s`` (then cut at the
quietest moment near the end).  Chunks that are quiet throughout are
dropped — given silence, Whisper tends to invent "Thank you."

Nothing here imports Qt; ``sounddevice`` and ``soundfile`` are imported
only when a recording starts, so the app runs without them.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

RATE = 16000
_FRAME = 480            # 30 ms analysis frames


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


@dataclass
class Chunk:
    start: int            # first sample, counted from the recording start
    audio: np.ndarray

    @property
    def start_s(self) -> float:
        return self.start / RATE


class Chunker:
    def __init__(self, min_s: float = 1.5, max_s: float = 10.0, pause_s: float = 0.5,
                 floor: float = 0.006) -> None:
        self.min_n = int(min_s * RATE)
        self.max_n = int(max_s * RATE)
        self.pause_frames = max(1, int(pause_s * RATE / _FRAME))
        self.floor = floor
        self._buf = np.zeros(0, dtype=np.float32)
        self._start = 0                       # sample index of _buf[0]

    def _levels(self, x: np.ndarray) -> np.ndarray:
        n = len(x) // _FRAME
        if n == 0:
            return np.zeros(0)
        return np.sqrt(np.mean(np.square(x[:n * _FRAME].reshape(n, _FRAME)), axis=1))

    def _quiet(self, levels: np.ndarray) -> np.ndarray:
        # Quiet relative to this chunk's loud parts as well as absolutely,
        # so a noisy room still yields pauses.
        loud = np.percentile(levels, 90) if levels.size else 0.0
        return levels < max(self.floor, 0.2 * loud)

    def _emit(self, n: int) -> Optional[Chunk]:
        audio, self._buf = self._buf[:n], self._buf[n:]
        start, self._start = self._start, self._start + n
        levels = self._levels(audio)
        if not levels.size or not (~self._quiet(levels)).any() or levels.max() < self.floor * 2:
            return None
        # Start the chunk shortly before the first sound, so its time is
        # when the speaker started rather than when the pause before began.
        first = int(np.argmax(~self._quiet(levels)))
        skip = max(0, first - 7) * _FRAME
        return Chunk(start + skip, audio[skip:])

    def feed(self, frames: np.ndarray) -> list[Chunk]:
        self._buf = np.concatenate([self._buf, frames.astype(np.float32).ravel()])
        out = []
        while len(self._buf) >= self.min_n:
            levels = self._levels(self._buf)
            quiet = self._quiet(levels)
            tail = quiet[-self.pause_frames:]
            if not (~quiet).any():
                # Nothing said yet: keep only the latest moment of quiet.
                keep = self.pause_frames * _FRAME
                self._start += len(self._buf) - keep
                self._buf = self._buf[-keep:]
                break
            if len(tail) == self.pause_frames and tail.all():
                chunk = self._emit(len(levels) * _FRAME)
            elif len(self._buf) >= self.max_n:
                # No pause: cut at the quietest frame in the last 3 s.
                window = max(1, int(3 * RATE / _FRAME))
                lo = max(0, len(levels) - window)
                cut = (lo + int(np.argmin(levels[lo:]))) * _FRAME + _FRAME
                chunk = self._emit(max(cut, _FRAME))
            else:
                break
            if chunk is not None:
                out.append(chunk)
        return out

    def pending(self) -> Optional[Chunk]:
        """The speech heard since the last chunk, for a live preview, or
        None while it is still only quiet."""
        if len(self._buf) < _FRAME * 10:
            return None
        levels = self._levels(self._buf)
        loud = ~self._quiet(levels)
        if not loud.any() or levels.max() < self.floor * 2:
            return None
        skip = max(0, int(np.argmax(loud)) - 7) * _FRAME
        return Chunk(self._start + skip, self._buf[skip:].copy())

    def flush(self) -> list[Chunk]:
        if not len(self._buf):
            return []
        chunk = self._emit(len(self._buf))
        return [chunk] if chunk is not None else []


def input_devices(refresh: bool = False) -> list[tuple[int, str]]:
    """(index, name) of every input device, or [] without sounddevice.

    Only the default host API is listed — Windows offers each microphone
    again through MME, DirectSound, WASAPI and WDM-KS.  Two devices with
    the same name get " (2)", " (3)"… so a name picks one device.
    *refresh* re-scans, so a microphone plugged in since the start shows;
    never while a stream is open (PortAudio would close it)."""
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        return []
    try:
        if refresh:
            sd._terminate()
            sd._initialize()
        devices = sd.query_devices()
        try:
            host = sd.query_devices(kind="input")["hostapi"]
        except Exception:  # noqa: BLE001 — no default input
            host = None
        out, seen = [], {}
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) <= 0:
                continue
            if host is not None and d.get("hostapi") != host:
                continue
            name = d["name"]
            seen[name] = seen.get(name, 0) + 1
            out.append((i, name if seen[name] == 1 else f"{name} ({seen[name]})"))
        return out
    except Exception:  # noqa: BLE001 — PortAudio errors vary by platform
        return []


def default_input_name() -> str:
    try:
        import sounddevice as sd
        return sd.query_devices(kind="input")["name"]
    except Exception:  # noqa: BLE001 — no sounddevice, or no input at all
        return ""


def find_input(name: str, devices: Optional[list[tuple[int, str]]] = None) -> Optional[int]:
    """The device index called *name*, or None for the system default
    (an empty name, or a device that is no longer connected)."""
    if not name:
        return None
    return next((i for i, n in (input_devices() if devices is None else devices)
                 if n == name), None)


class Recorder:
    """Records the microphone to *path* (Ogg/Opus, small enough to keep a
    whole lecture in the note) and hands frames to *on_frames* on a
    worker thread — never in PortAudio's real-time callback."""

    def __init__(self, path: str, on_frames: Callable[[np.ndarray], None],
                 on_level: Callable[[float], None], device: Optional[int] = None) -> None:
        self.path = path
        self.on_frames = on_frames
        self.on_level = on_level
        self.device = device
        self.frames_written = 0
        self._q: "queue.Queue[Optional[np.ndarray]]" = queue.Queue()
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._stopped = False
        self._lock = threading.Lock()
        self.error: Optional[str] = None

    def start(self) -> None:
        import soundfile as sf
        try:
            self._file = sf.SoundFile(self.path, "w", RATE, 1, format="OGG", subtype="OPUS")
        except (RuntimeError, sf.LibsndfileError):
            self.path = self.path.rsplit(".", 1)[0] + ".flac"
            self._file = sf.SoundFile(self.path, "w", RATE, 1, format="FLAC")
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()
        device = self.device
        stream = self._open_stream(device)
        with self._lock:
            if self._stopped:
                # Stop was pressed while the device was still opening.
                stream.close()
                return
            if self.device != device:
                # Another microphone was picked meanwhile.
                stream.close()
                stream = self._open_stream(self.device)
            self._stream = stream
            stream.start()

    def _open_stream(self, device: Optional[int]):
        import sounddevice as sd
        return sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                              blocksize=RATE // 10, device=device,
                              callback=self._callback)

    def switch(self, device: Optional[int]) -> None:
        """Carry on recording from another microphone, into the same
        file.  If it cannot be opened the old one is kept and the error
        raised."""
        with self._lock:
            if self._stream is None:
                self.device = device             # still opening: start() takes it
                return
        new = self._open_stream(device)
        with self._lock:
            if self._stopped or self._stream is None:
                new.close()
                return
            old, self._stream = self._stream, new
            if old is not None:
                old.stop()
                old.close()
            try:
                new.start()
            except Exception:
                new.close()
                self._stream = None
                if old is not None:
                    self._stream = self._open_stream(self.device)
                    self._stream.start()
                raise
            self.device = device

    def _callback(self, indata, frames, time_info, status) -> None:  # PortAudio thread
        self._q.put(indata[:, 0].copy())

    def _drain(self) -> None:
        while True:
            frames = self._q.get()
            if frames is None:
                break
            try:
                self._file.write(frames)
                self.frames_written += len(frames)
                if self.frames_written % RATE < len(frames):
                    # About once a second: a crash then loses at most that.
                    self._file.flush()
                self.on_level(rms(frames))
                self.on_frames(frames)
            except Exception as exc:  # noqa: BLE001 — keep recording what we can
                self.error = str(exc)
        self._file.close()

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
        self._q.put(None)
        if self._thread is not None:
            self._thread.join(timeout=10)

    @property
    def duration(self) -> float:
        return self.frames_written / RATE
