# KherveNote — typed lists
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""The plain-text list syntax notes are typed in.

``- item`` / ``* item`` / ``• item`` is a bullet, ``1. item`` / ``1) item``
a numbered item; indenting a line under an item makes it a sub-item.
Indents are compared with the lines above rather than counted in fixed
units, so two spaces, four spaces and tabs all work.  Used by the
serializer for text that carries the markers literally.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_ITEM_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*•]|\d{1,3}[.)])[ \t]+(?P<text>.*)$")

#: LaTeX nests itemize/enumerate four deep.
MAX_DEPTH = 4


@dataclass
class Item:
    indent: int
    numbered: bool
    marker: str
    text: str


def _width(indent: str) -> int:
    return len(indent.expandtabs(4))


def parse_item(line: str) -> Optional[Item]:
    m = _ITEM_RE.match(line)
    if not m:
        return None
    marker = m.group("marker")
    return Item(_width(m.group("indent")), marker[0].isdigit(), marker,
                m.group("text").rstrip())


def indent_of(line: str) -> int:
    return _width(line[:len(line) - len(line.lstrip(" \t"))])


@dataclass
class ListLine:
    """One rendered line of a list: an item at *level*, or a continuation
    of the previous item's text (*item* False)."""
    level: int
    numbered: bool
    text: str
    item: bool = True


def nest(lines: list[str]) -> list[ListLine]:
    """Assign nesting levels to a run of list lines.  A non-item line
    indented deeper than the last item continues that item."""
    out: list[ListLine] = []
    widths: list[int] = []
    for ln in lines:
        item = parse_item(ln)
        if item is None:
            if out:
                out.append(ListLine(out[-1].level, out[-1].numbered, ln.strip(), item=False))
            continue
        while widths and widths[-1] > item.indent:
            widths.pop()
        if not widths or widths[-1] < item.indent:
            widths.append(item.indent)
        level = min(len(widths) - 1, MAX_DEPTH - 1)
        out.append(ListLine(level, item.numbered, item.text))
    return out


def is_list_line(line: str, in_list: bool) -> bool:
    """Is *line* part of a list?  Items always are; an indented plain
    line is when it follows an item."""
    return parse_item(line) is not None or (in_list and indent_of(line) > 0
                                            and bool(line.strip()))
