# KherveNote — local AI (Ollama)
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Summarise and rephrase with a model running in Ollama on this
computer, for people who would rather not send their notes to a cloud
AI.  Plain HTTP to Ollama's API; no Qt, no extra packages."""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Optional

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "").strip() or "http://localhost:11434"
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/")


class OllamaError(RuntimeError):
    pass


def _request(path: str, payload: Optional[dict] = None, timeout: float = 5.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url() + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise OllamaError(f"Ollama answered {exc.code}: {detail[:300]}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise OllamaError("Ollama is not running on this computer "
                          f"({base_url()}). Start it with `ollama serve`.") from exc


def is_running() -> bool:
    try:
        _request("/api/version", timeout=2)
        return True
    except OllamaError:
        return False


def pull(model: str, progress=None) -> None:
    """Download *model* into Ollama, reporting ``progress(fraction, text)``
    as it goes (fraction is None while there is no size yet)."""
    req = urllib.request.Request(base_url() + "/api/pull",
                                 data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            for line in resp:
                if not line.strip():
                    continue
                msg = json.loads(line)
                if "error" in msg:
                    raise OllamaError(msg["error"])
                total, done = msg.get("total"), msg.get("completed")
                if progress:
                    frac = done / total if total and done is not None else None
                    progress(frac, msg.get("status", ""))
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"Ollama answered {exc.code}: {exc.read()[:300]!r}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise OllamaError("Ollama is not running on this computer "
                          f"({base_url()}). Start it, then try again.") from exc


def list_models() -> list[str]:
    return sorted(m["name"] for m in _request("/api/tags", timeout=3).get("models", []))


class Cancelled(Exception):
    """The user pressed Cancel while the model was writing."""


class Job:
    """What a running AI task tells the window: each piece of text as it
    is written (*on_text*), which step it is on (*on_step*), and whether
    the user cancelled.  Set for the calling thread with ``Job.run``."""

    def __init__(self, on_text=None, on_step=None) -> None:
        self.on_text = on_text
        self.on_step = on_step
        self.cancelled = threading.Event()
        #: Parallel parts would interleave their words; they stay quiet.
        self.quiet = False

    def step(self, text: str) -> None:
        if self.on_step:
            self.on_step(text)

    def run(self, fn, *args):
        _current.job = self
        try:
            return fn(*args)
        finally:
            _current.job = None


_current = threading.local()


def current_job() -> Optional[Job]:
    return getattr(_current, "job", None)


def chat(model: str, system: str, text: str, timeout: float = 600.0,
         context: int = 8192, limit: Optional[int] = None) -> str:
    # Ollama's default window (often 4096 tokens) would silently cut off
    # a document extract; ask for room for it.  *limit* caps the reply.
    options = {"temperature": 0.3, "num_ctx": context}
    if limit:
        options["num_predict"] = limit
    payload = {"model": model, "stream": False, "options": options,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": text}]}
    job = current_job()
    send = (lambda body: _stream(body, job, timeout)) if job else \
        (lambda body: _request("/api/chat", body, timeout).get("message", {}).get("content", ""))
    try:
        # Reasoning models would otherwise spend minutes "thinking" about
        # a paragraph; servers that predate the flag reject it.
        content = send(dict(payload, think=False))
    except OllamaError as exc:
        if "think" not in str(exc).lower():
            raise
        content = send(payload)
    return _THINK_RE.sub("", content).strip()


def _stream(payload: dict, job: Job, timeout: float) -> str:
    """The reply, read word by word so the window can show it being
    written and Cancel can stop it at once."""
    req = urllib.request.Request(base_url() + "/api/chat",
                                 data=json.dumps(dict(payload, stream=True)).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    parts = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for line in resp:
                if job.cancelled.is_set():
                    raise Cancelled()
                if not line.strip():
                    continue
                msg = json.loads(line)
                if "error" in msg:
                    raise OllamaError(f"Ollama answered: {msg['error']}")
                piece = msg.get("message", {}).get("content", "")
                if piece:
                    parts.append(piece)
                    if job.on_text and not job.quiet:
                        job.on_text(piece)
                if msg.get("done"):
                    break
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise OllamaError(f"Ollama answered {exc.code}: {detail[:300]}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise OllamaError("Ollama is not running on this computer "
                          f"({base_url()}). Start it with `ollama serve`.") from exc
    return "".join(parts)


def _parallel(fn, items: list, workers: int = 2) -> list:
    """*fn* over *items*, a few at a time — Ollama can work on more than
    one request when memory allows — keeping the order and the job."""
    from concurrent.futures import ThreadPoolExecutor
    job = current_job()
    if job is not None:
        job.quiet = True

    def call(item):
        return job.run(fn, item) if job is not None else fn(item)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(call, items))
    finally:
        if job is not None:
            job.quiet = False


SUMMARISE = (
    "You turn notes taken during a lecture or training into a summary. "
    "Write in the same language as the notes. Give the key points as short "
    "bullet points, each line starting with '- '. Keep facts, numbers and "
    "names exactly; do not add anything that is not in the notes. Reply with "
    "the bullet points only, no introduction.")

SUMMARISE_NOTE = (
    "You write the summary at the top of a set of lecture notes. Write in "
    "the same language as the notes: 3 to 6 sentences giving what the talk "
    "covered and its main conclusions. Do not add anything that is not in "
    "the notes. Reply with the summary only.")

REPHRASE = (
    "Rewrite the text as clear, well-written prose, as it would appear in "
    "good lecture notes. Keep the meaning, every fact and number, and the "
    "language of the text. It may be a speech transcript: remove "
    "hesitations and repetitions and fix words that were obviously "
    "misheard. Keep paragraph breaks. Reply with the rewritten text only.")


def summarise(model: str, text: str) -> str:
    return chat(model, SUMMARISE, text)


def summarise_note(model: str, text: str) -> str:
    return chat(model, SUMMARISE_NOTE, text)


def rephrase(model: str, text: str) -> str:
    return chat(model, REPHRASE, text)


#: General-purpose families, best first, for when the user has not
#: picked a model.  Anything else (custom models with their own system
#: prompt, made for another app) is used only when nothing general is
#: installed.
_GENERAL = ("qwen", "gemma", "ministral", "mistral", "llama", "aya", "phi", "granite",
            "gpt-oss", "deepseek")


def pick_default(models: list[str], preferred: str = "") -> str:
    if preferred in models:
        return preferred
    for family in _GENERAL:
        for name in models:
            if name.lower().startswith(family):
                return name
    return models[0] if models else ""


# ── attached documents ──────────────────────────────────────────────

DOC_SUMMARY = (
    "You summarise a document for someone's lecture notes. Write in the "
    "language of the document. Start with two or three sentences on what it "
    "is about, then the key points as bullet lines starting with '- '. Keep "
    "facts, numbers and names exactly; add page references like (p. 4) when "
    "the text shows them in brackets. Reply with the summary only.")

DOC_PART_SUMMARY = (
    "Summarise this part of a longer document as bullet lines starting with "
    "'- ', keeping facts, numbers, names and the page references in "
    "brackets. Reply with the bullets only.")

DOC_ANSWER = (
    "You answer a question about a document, using ONLY the extracts given. "
    "Write the answer as a short section of lecture notes in the language of "
    "the question: clear paragraphs and, where it helps, bullet lines "
    "starting with '- '. After each fact give where it comes from, like "
    "(p. 4) or (Slide 3), from the [brackets] before each extract. If the "
    "extracts do not contain the answer, say so plainly and do not guess. "
    "Reply with the section text only, without a title.")


def with_directions(system: str, directions: str) -> str:
    """*system* plus the user's own directions, which win over its
    format but never over the facts."""
    directions = (directions or "").strip()
    if not directions:
        return system
    return (system + "\n\nThe user gives these directions; follow them, even where they "
            "change the format or language asked for above — but never invent facts "
            "that are not in the text:\n" + directions)


def _ask(model: str, system: str, text: str, directions: str = "", **kw) -> str:
    """chat() with the user's directions in the instructions and again
    after the text — small models follow what they read last."""
    d = (directions or "").strip()
    if d:
        text = f"{text}\n\n---\nDirections from the user (follow them exactly): {d}"
    return chat(model, with_directions(system, d), text, **kw)


REVISE = (
    "Revise the text below following the user's directions. Keep every fact, "
    "number and name that the directions do not ask you to drop, and do not add "
    "facts that are not in the text. Use '## ' for headings and '- ' or '1. ' for "
    "lists when they help. Reply with the revised text only.")


def revise(model: str, text: str, directions: str) -> str:
    _step("Revising")
    return _ask(model, REVISE, text[:40000], directions, context=16384, limit=2000)


def _step(text: str) -> None:
    job = current_job()
    if job is not None:
        job.step(text)


def summarise_document(model: str, doc, budget: int = 20000, directions: str = "") -> str:
    """Summary of a whole document; a long one is summarised in parts
    (two at a time) first, then the parts are combined.  *directions*
    guide both steps (what to keep from each part, how to write it)."""
    from .documents import batches
    parts = batches(doc, budget)
    head = f"Document: {doc.name}\n\n"
    if len(parts) == 1:
        _step("Writing the summary")
        return _ask(model, DOC_SUMMARY, head + parts[0], directions, context=16384,
                    limit=1500 if directions else 900)
    _step(f"Reading the document in {len(parts)} parts")
    done = [0]

    def part(text: str) -> str:
        out = _ask(model, DOC_PART_SUMMARY, head + text, directions, context=16384,
                   limit=600)
        done[0] += 1
        _step(f"Read {done[0]} of {len(parts)} parts")
        return out
    notes = _parallel(part, parts)
    _step("Writing the summary")
    return _ask(model, DOC_SUMMARY, head + "\n".join(notes), directions, context=16384,
                limit=1500 if directions else 900)


def summarise_section(model: str, doc_name: str, title: str, text: str,
                      directions: str = "") -> str:
    _step(f"Summarising “{title}”")
    return _ask(model, DOC_SUMMARY,
                f"Document: {doc_name}\nSection: {title}\n\n{text[:30000]}", directions,
                context=16384, limit=900)


def answer(model: str, doc, question: str, directions: str = "") -> str:
    _step("Reading the passages that match the question")
    from .documents import best_passages
    extracts = "\n\n".join(f"[{p.where}]\n{p.text}" for p in best_passages(doc, question))
    return _ask(model, DOC_ANSWER,
                f"Document: {doc.name}\n\nExtracts:\n{extracts}\n\nQuestion: {question}",
                directions, context=16384)


def summarise_each_section(model: str, doc, progress=None, max_parts: int = 24,
                           directions: str = "") -> str:
    """A "## title" heading and key points for every top-level section,
    two at a time.  A document cut into many small sections (one per
    page, say) is grouped into at most *max_parts* parts first."""
    groups = [g for g in _section_groups(doc, max_parts) if len(g[1].strip()) >= 80]
    done = [0]

    def one(group) -> str:
        title, text = group
        points = _ask(model, DOC_PART_SUMMARY,
                      f"Document: {doc.name}\nSection: {title}\n\n{text[:30000]}", directions,
                      context=16384, limit=800 if directions else 500)
        done[0] += 1
        msg = f"Summarised {done[0]} of {len(groups)} sections"
        _step(msg)
        if progress:
            progress(msg)
        return f"## {title}\n{points.strip()}"
    _step(f"Summarising {len(groups)} sections")
    return "\n\n".join(_parallel(one, groups))


def _section_groups(doc, max_parts: int) -> list[tuple[str, str]]:
    # Sub-sections are folded into the top-level section they belong to.
    top = min((s.level for s in doc.sections), default=1)
    groups: list[list] = []
    for s in doc.sections:
        if s.level == top or not groups:
            groups.append([s.title or doc.name, s.text])
        else:
            groups[-1][1] += f"\n\n{s.title}\n{s.text}"
    if len(groups) > max_parts:
        size = -(-len(groups) // max_parts)
        merged = []
        for i in range(0, len(groups), size):
            chunk = groups[i:i + size]
            title = chunk[0][0] if len(chunk) == 1 else f"{chunk[0][0]} – {chunk[-1][0]}"
            merged.append([title, "\n\n".join(t for _, t in chunk)])
        groups = merged
    return [(t, x) for t, x in groups]


# ── the speech transcript and the user's notes ──────────────────────

FILL_FROM_SPEECH = (
    "You are given someone's own notes for one part of a talk, and the "
    "transcript of what the speaker said during that part. Write, as short "
    "bullet lines starting with '- ', the important points the speaker made "
    "that the notes do not already contain. Keep facts, numbers and names "
    "exactly, in the language of the talk. Do not repeat what the notes "
    "already say. If the notes already cover everything, reply exactly: "
    "Nothing to add.")

NOTES_FROM_SPEECH = (
    "Turn this transcript of a talk into clear lecture notes in the language "
    "of the talk: '## ' headings for the topics in the order they came, and "
    "under each, short paragraphs or bullet lines starting with '- '. Keep "
    "facts, numbers and names exactly; drop hesitations, repetitions and "
    "small talk. Reply with the notes only.")

SPEECH_PART = (
    "Summarise this part of a talk's transcript as bullet lines starting "
    "with '- ', keeping facts, numbers and names. Reply with the bullets only.")


def fill_from_speech(model: str, notes: str, speech: str) -> str:
    _step("Comparing your notes with what was said")
    return chat(model, FILL_FROM_SPEECH,
                f"My notes:\n{notes or '(nothing written)'}\n\nTranscript:\n{speech[:40000]}",
                context=16384, limit=700)


def notes_from_speech(model: str, transcript: str, budget: int = 18000) -> str:
    """Notes from a transcript; a long one is condensed part by part
    (two at a time) first."""
    if len(transcript) <= budget:
        _step("Writing notes from the speech")
        return chat(model, NOTES_FROM_SPEECH, transcript, context=16384, limit=1500)
    lines, parts, buf = transcript.splitlines(), [], ""
    for line in lines:
        if buf and len(buf) + len(line) > budget:
            parts.append(buf)
            buf = ""
        buf += line + "\n"
    if buf:
        parts.append(buf)
    _step(f"Reading the speech in {len(parts)} parts")
    condensed = _parallel(lambda part: chat(model, SPEECH_PART, part, context=16384,
                                            limit=700), parts)
    _step("Writing notes from the speech")
    return chat(model, NOTES_FROM_SPEECH, "\n".join(condensed), context=16384, limit=1500)
