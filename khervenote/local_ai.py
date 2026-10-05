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


def list_models() -> list[str]:
    return sorted(m["name"] for m in _request("/api/tags", timeout=3).get("models", []))


def chat(model: str, system: str, text: str, timeout: float = 600.0) -> str:
    payload = {"model": model, "stream": False, "options": {"temperature": 0.3},
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
