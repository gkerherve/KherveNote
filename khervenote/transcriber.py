# KherveNote — offline speech-to-text
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Whisper, run locally with faster-whisper: audio never leaves the
machine.  The model is fetched once (Hugging Face) and cached; after
that, listening works offline.

``ListenSession`` ties the pieces together on worker threads:
microphone → ``Recorder`` (writes the audio file) → ``Chunker`` →
transcription → ``text`` signal on the GUI thread.
"""
from __future__ import annotations

import queue
import threading
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from .audio import RATE, Chunk, Chunker, Recorder

#: (name, label) — sizes as faster-whisper names them.
MODELS = (
    ("tiny", "Tiny — fastest, ~75 MB"),
    ("base", "Base — fast, ~145 MB"),
    ("small", "Small — good, ~480 MB"),
    ("medium", "Medium — better, ~1.5 GB"),
    ("large-v3-turbo", "Large v3 turbo — best, ~1.6 GB"),
)
DEFAULT_MODEL = "small"

#: (code, label); "" lets Whisper detect the language.
LANGUAGES = (("", "Detect automatically"), ("en", "English"), ("fr", "French"),
             ("de", "German"), ("es", "Spanish"), ("it", "Italian"), ("pt", "Portuguese"),
             ("nl", "Dutch"), ("zh", "Chinese"), ("ja", "Japanese"))

#: Phrases Whisper produces from noise; dropped when they are all a chunk said.
_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching!", "thanks for watching.",
    "you", "bye.", "bye", ".", "...", "merci.", "sous-titrage st' 501",
}


def missing_packages() -> list[str]:
    missing = []
    for mod, pkg in (("sounddevice", "sounddevice"), ("soundfile", "soundfile"),
                     ("faster_whisper", "faster-whisper")):
        try:
            __import__(mod)
        except (ImportError, OSError):
            missing.append(pkg)
    return missing


def model_is_cached(name: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
        from faster_whisper.utils import _MODELS
    except ImportError:
        return False
    repo = _MODELS.get(name)
    return bool(repo) and isinstance(try_to_load_from_cache(repo, "model.bin"), str)


class WhisperEngine:
    def __init__(self, name: str = DEFAULT_MODEL) -> None:
        from faster_whisper import WhisperModel
        # int8 on the CPU is fast enough for live speech on any recent
        # laptop, and needs no GPU stack.
        self.model = WhisperModel(name, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray, language: str = "",
                   prompt: str = "") -> tuple[str, Optional[str]]:
        segments, info = self.model.transcribe(
            audio, language=language or None, beam_size=3, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=prompt or None)
        parts = []
        for seg in segments:
            if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
                continue
            parts.append(seg.text.strip())
        text = " ".join(p for p in parts if p).strip()
        if text.lower() in _HALLUCINATIONS:
            text = ""
        return text, getattr(info, "language", None)


class ListenSession(QObject):
    """One run of the microphone, from Listen to Stop."""

    text = Signal(str, float)        # recognised text, session time it started
    level = Signal(float)            # microphone level, 0..1-ish
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, audio_path: str, t0: float, model: str = DEFAULT_MODEL,
                 language: str = "", device: Optional[int] = None, parent=None,
                 engine: Optional[WhisperEngine] = None) -> None:
        super().__init__(parent)
        self.audio_path = audio_path
        self.t0 = t0
        self.model_name = model
        self.language = language
        self.device = device
        self.engine = engine
        self.chunker = Chunker()
        self._chunks: "queue.Queue[Optional[Chunk]]" = queue.Queue()
        self._recorder: Optional[Recorder] = None
        self._worker: Optional[threading.Thread] = None
        self._context = ""

    # capture side

    def start(self) -> None:
        self._worker = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._worker.start()
        self._recorder = Recorder(self.audio_path, self.feed, self.level.emit, self.device)
        # Opening the device can block (an OS permission prompt pending),
        # so it never happens on the GUI thread.
        threading.Thread(target=self._open, daemon=True).start()

    def _open(self) -> None:
        try:
            self._recorder.start()
        except Exception as exc:  # noqa: BLE001 — no device, permission, PortAudio
            self._recorder = None
            self._chunks.put(None)
            self.failed.emit(f"Could not open the microphone: {exc}")

    def feed(self, frames: np.ndarray) -> None:
        for chunk in self.chunker.feed(frames):
            self._chunks.put(chunk)

    def stop(self) -> None:
        if self._recorder is not None:
            self._recorder.stop()
            self.audio_path = self._recorder.path
        for chunk in self.chunker.flush():
            self._chunks.put(chunk)
        self._chunks.put(None)

    @property
    def duration(self) -> float:
        return self._recorder.duration if self._recorder else 0.0

    # transcription side

    def _transcribe_loop(self) -> None:
        if self.engine is None:
            cached = model_is_cached(self.model_name)
            self.status.emit(f"Loading the speech model ({self.model_name})…" if cached else
                             f"Downloading the speech model ({self.model_name}) — once only…")
            try:
                self.engine = WhisperEngine(self.model_name)
            except Exception as exc:  # noqa: BLE001 — download / load failures
                self.failed.emit(f"Could not load the speech model: {exc}")
                self._drain_until_end()
                return
        self.status.emit("Listening")
        while True:
            chunk = self._chunks.get()
            if chunk is None:
                break
            try:
                text, lang = self.engine.transcribe(chunk.audio, self.language, self._context)
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(f"Transcription failed: {exc}")
                continue
            if lang and not self.language:
                self.language = lang          # stop re-detecting every chunk
            if text:
                self._context = (self._context + " " + text)[-220:]
                self.text.emit(text, self.t0 + chunk.start_s)
        self.finished.emit()

    def _drain_until_end(self) -> None:
        while self._chunks.get() is not None:
            pass
        self.finished.emit()


def transcribe_file(engine: WhisperEngine, audio: np.ndarray, language: str = "") -> list[tuple[float, str]]:
    """Chunk and transcribe a whole recording (also what the tests use)."""
    chunker = Chunker()
    out = []
    step = RATE // 10
    chunks = []
    for i in range(0, len(audio), step):
        chunks += chunker.feed(audio[i:i + step])
    chunks += chunker.flush()
    for c in chunks:
        text, _ = engine.transcribe(c.audio, language)
        if text:
            out.append((c.start_s, text))
    return out
