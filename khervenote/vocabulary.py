# KherveNote — the words of a talk
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Suggest the names, acronyms and technical terms of a talk from what
is already written (the notes, attached documents), for speech
recognition to listen for.  Qt-free."""
from __future__ import annotations

import re
from collections import Counter

# Acronyms and formulas (XPS, ToF-SIMS, LLZO, Li7La3Zr2O12), words with a
# capital inside or a hyphen (KherveFitting, Hall-Petch), and capitalised
# names that are not at the start of a sentence (Tougaard, Shirley).
_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*\b")
_COMMON = set("""The This That These Those There Then When Where What Which While With
Without From For And But Not Note Notes Page Section Figure Table Summary Key Question
Introduction Conclusion Methods Results Discussion Abstract References Today Next First
Second Third Finally However Also Here Each Every All Some Most Our Their They We You
It Its In On At By Of To As An If Or So No Yes Dr Prof Mr Mrs Ms""".split())


def _interesting(word: str) -> bool:
    if word in _COMMON or len(word) < 2:
        return False
    upper = sum(c.isupper() for c in word)
    return (upper >= 2 or "-" in word and upper >= 1
            or any(c.isdigit() for c in word) and upper >= 1)


def suggest(texts: list[str], limit: int = 30, known: str = "") -> list[str]:
    """Terms worth listening for, most frequent first, without the ones in
    *known* (the current list)."""
    have = {w.strip().lower() for w in known.split(",") if w.strip()}
    counts: Counter = Counter()
    names: Counter = Counter()
    for text in texts:
        for sentence in re.split(r"(?<=[.!?:;])\s+|\n", text):
            words = _TOKEN.findall(sentence)
            for i, w in enumerate(words):
                if _interesting(w):
                    counts[w] += 1
                elif i > 0 and w[0].isupper() and w[1:].islower() and w not in _COMMON \
                        and len(w) > 3:
                    names[w] += 1
    for w, n in names.items():
        if n >= 2:                      # a name used twice is worth having
            counts[w] += n
    out = []
    for w, _n in counts.most_common():
        if w.lower() not in have and w.lower() not in {o.lower() for o in out}:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def merge(known: str, extra: list[str]) -> str:
    words = [w.strip() for w in known.split(",") if w.strip()]
    for w in extra:
        if w.lower() not in {x.lower() for x in words}:
            words.append(w)
    return ", ".join(words)
