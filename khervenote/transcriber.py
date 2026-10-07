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

import os
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


#: The live preview needs speed more than accuracy: below this size it
#: uses the chosen model, above it this one (when it is downloaded).
PREVIEW_MODEL = "base"
_SMALLER = ("tiny", "base")


_MODEL_MB = {"tiny": 75, "base": 145, "small": 484, "medium": 1530, "large-v3-turbo": 1620}


def download_progress(name: str) -> tuple[int, int]:
    """(MB on disk so far, MB expected) of a model being downloaded."""
    try:
        from faster_whisper.utils import _MODELS
    except ImportError:
        return 0, 0
    repo = _MODELS.get(name, "")
    root = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")), "hub")
    folder = os.path.join(root, "models--" + repo.replace("/", "--"), "blobs")
    done = 0
    if os.path.isdir(folder):
        for entry in os.scandir(folder):
            if entry.is_file():
                done += entry.stat().st_size
    return done // 1_000_000, _MODEL_MB.get(name, 0)


class WhisperEngine:
    def __init__(self, name: str = DEFAULT_MODEL) -> None:
        from faster_whisper import WhisperModel
        # Once downloaded, never touch the network: the Hub check costs
        # seconds at every start and fails offline.
        local = model_is_cached(name)
        # int8 on the CPU is fast enough for live speech on any recent
        # laptop, and needs no GPU stack.
        self.model = WhisperModel(name, device="cpu", compute_type="int8",
                                  cpu_threads=min(8, os.cpu_count() or 4),
                                  local_files_only=local)

    def transcribe(self, audio: np.ndarray, language: str = "", prompt: str = "",
                   fast: bool = False, vocabulary: str = "") -> tuple[str, Optional[str]]:
        # Greedy decoding: beam search costs ~30 % more time for little
        # gain on clear lecture speech.  The preview also skips the VAD.
        # The talk's own words, as hotwords and as a glossary before the
        # last words heard: "ToF-SIMS" instead of "two F-SIMs".
        vocab = " ".join(vocabulary.split())[:400]
        if vocab:
            prompt = f"Glossary: {vocab}. {prompt}".strip()
        segments, info = self.model.transcribe(
            audio, language=language or None, beam_size=1, vad_filter=not fast,
            without_timestamps=True, condition_on_previous_text=False,
            initial_prompt=prompt or None, hotwords=vocab or None)
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
    """One run of the microphone, from Listen to Stop.

    One worker thread does all the transcribing.  Finished utterances
    (cut at pauses) come first; whenever there are none waiting, it
    transcribes the utterance still in progress with a fast model and
    emits it as ``partial`` — the words appear while they are spoken and
    are replaced by the final ``text`` once the speaker pauses.
    """

    text = Signal(str, float)        # final text, session time it started
    partial = Signal(str)            # the words being spoken now ("" clears)
    level = Signal(float)            # microphone level, 0..1-ish
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    #: Seconds of new audio before the preview is refreshed.
    PREVIEW_STEP = 0.4
    #: The preview looks at most this far back.
    PREVIEW_WINDOW = 10.0

    def __init__(self, audio_path: str, t0: float, model: str = DEFAULT_MODEL,
                 language: str = "", device: Optional[int] = None, parent=None,
                 engine: Optional[WhisperEngine] = None,
                 preview: Optional[WhisperEngine] = None, vocabulary: str = "") -> None:
        super().__init__(parent)
        self.audio_path = audio_path
        self.t0 = t0
        self.model_name = model
        self.language = language
        self.device = device
        self.engine = engine
        self.preview = preview
        self.chunker = Chunker()
        self._lock = threading.Lock()
        self._chunks: "queue.Queue[Optional[Chunk]]" = queue.Queue()
        self._recorder: Optional[Recorder] = None
        self._worker: Optional[threading.Thread] = None
        self._context = ""
        #: Names and terms of this talk; may change while listening.
        self.vocabulary = vocabulary
        self._heard = 0              # samples fed so far
        self._previewed = 0          # _heard at the last preview
        self._stopping = False

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

    def switch_device(self, device: Optional[int], name: str) -> None:
        """Carry on from another microphone; the recording and its times
        go on unbroken."""
        self.device = device
        rec = self._recorder
        if rec is None:
            return

        def run() -> None:
            try:
                rec.switch(device)
                self.status.emit(f"Listening with {name}")
            except Exception as exc:  # noqa: BLE001 — unplugged, busy, PortAudio
                self.failed.emit(f"Could not switch to {name}: {exc}")
        threading.Thread(target=run, daemon=True).start()

    def feed(self, frames: np.ndarray) -> None:
        with self._lock:
            chunks = self.chunker.feed(frames)
            self._heard += len(frames)
        for chunk in chunks:
            self._chunks.put(chunk)

    def stop(self) -> None:
        self._stopping = True
        if self._recorder is not None:
            self._recorder.stop()
            self.audio_path = self._recorder.path
        with self._lock:
            chunks = self.chunker.flush()
        for chunk in chunks:
            self._chunks.put(chunk)
        self._chunks.put(None)

    @property
    def duration(self) -> float:
        return self._recorder.duration if self._recorder else 0.0

    # transcription side

    def _load(self) -> bool:
        if self.engine is None:
            cached = model_is_cached(self.model_name)
            self.status.emit(f"Loading the speech model ({self.model_name})…" if cached else
                             f"Downloading the speech model ({self.model_name}) — once only. "
                             "Keep talking: it is being recorded.")
            try:
                self.engine = WhisperEngine(self.model_name)
            except Exception as exc:  # noqa: BLE001 — download / load failures
                self.failed.emit(f"Could not load the speech model: {exc}")
                return False
        if self.preview is None:
            if self.model_name in _SMALLER or not model_is_cached(PREVIEW_MODEL):
                self.preview = self.engine
            else:
                try:
                    self.preview = WhisperEngine(PREVIEW_MODEL)
                except Exception:  # noqa: BLE001 — fall back to the main model
                    self.preview = self.engine
        return True

    def _transcribe_loop(self) -> None:
        if not self._load():
            self._drain_until_end()
            return
        self.status.emit("Listening")
        while True:
            try:
                chunk = self._chunks.get(timeout=0.05)
            except queue.Empty:
                self._maybe_preview()
                continue
            if chunk is None:
                break
            try:
                text, lang = self.engine.transcribe(chunk.audio, self.language, self._context,
                                                    vocabulary=self.vocabulary)
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(f"Transcription failed: {exc}")
                continue
            if lang and not self.language:
                self.language = lang          # stop re-detecting every chunk
            self.partial.emit("")
            if text:
                self._context = (self._context + " " + text)[-220:]
                self.text.emit(text, self.t0 + chunk.start_s)
        self.partial.emit("")
        self.finished.emit()

    def _maybe_preview(self) -> None:
        if self._stopping or not self._chunks.empty():
            return
        with self._lock:
            if self._heard - self._previewed < self.PREVIEW_STEP * RATE:
                return
            self._previewed = self._heard
            pending = self.chunker.pending()
        if pending is None:
            return
        audio = pending.audio[-int(self.PREVIEW_WINDOW * RATE):]
        try:
            text, _ = self.preview.transcribe(audio, self.language, self._context, fast=True,
                                              vocabulary=self.vocabulary)
        except Exception:  # noqa: BLE001 — a failed preview is not worth reporting
            return
        if text and self._chunks.empty():
            self.partial.emit(text)

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
