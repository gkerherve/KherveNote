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


def chat(model: str, system: str, text: str, timeout: float = 600.0,
         context: int = 8192) -> str:
    # Ollama's default window (often 4096 tokens) would silently cut off
    # a document extract; ask for room for it.
    payload = {"model": model, "stream": False,
               "options": {"temperature": 0.3, "num_ctx": context},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": text}]}
    try:
        # Reasoning models would otherwise spend minutes "thinking" about
        # a paragraph; servers that predate the flag reject it.
        reply = _request("/api/chat", dict(payload, think=False), timeout)
    except OllamaError as exc:
        if "think" not in str(exc).lower():
            raise
        reply = _request("/api/chat", payload, timeout)
    content = reply.get("message", {}).get("content", "")
    return _THINK_RE.sub("", content).strip()


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
#: prompt, e.g. an XPS assistant built for KherveFitting) is used only
#: when nothing general is installed.
_GENERAL = ("qwen", "llama", "gemma", "mistral", "phi", "granite", "deepseek")


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


def summarise_document(model: str, doc, budget: int = 9000) -> str:
    """Summary of a whole document; a long one is summarised in parts
    first, then the parts are combined."""
    from .documents import batches
    parts = batches(doc, budget)
    head = f"Document: {doc.name}\n\n"
    if len(parts) == 1:
        return chat(model, DOC_SUMMARY, head + parts[0], context=16384)
    notes = [chat(model, DOC_PART_SUMMARY, head + part, context=16384) for part in parts]
    return chat(model, DOC_SUMMARY, head + "\n".join(notes), context=16384)


def summarise_section(model: str, doc_name: str, title: str, text: str) -> str:
    return chat(model, DOC_SUMMARY,
                f"Document: {doc_name}\nSection: {title}\n\n{text[:30000]}", context=16384)


def answer(model: str, doc, question: str) -> str:
    from .documents import best_passages
    extracts = "\n\n".join(f"[{p.where}]\n{p.text}" for p in best_passages(doc, question))
    return chat(model, DOC_ANSWER,
                f"Document: {doc.name}\n\nExtracts:\n{extracts}\n\nQuestion: {question}",
                context=16384)


def summarise_each_section(model: str, doc, progress=None, max_parts: int = 24) -> str:
    """A "## title" heading and key points for every top-level section,
    one model call each.  A document cut into many small sections (one
    per page, say) is grouped into at most *max_parts* parts first."""
    groups = _section_groups(doc, max_parts)
    out = []
    for i, (title, text) in enumerate(groups, 1):
        if progress:
            progress(f"Summarising section {i} of {len(groups)}: {title}…")
        if len(text.strip()) < 80:
            continue
        points = chat(model, DOC_PART_SUMMARY,
                      f"Document: {doc.name}\nSection: {title}\n\n{text[:30000]}",
                      context=16384)
        out.append(f"## {title}\n{points.strip()}")
    return "\n\n".join(out)


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
