# KherveNote — document model
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""The note model: the single source of truth.

A ``Note`` is one listening session (a lecture, a training, a talk).
It is a flat run of ``Section``s, each holding ``Block``s in the order
they were captured.  The live page, the ``.knote`` file, the LaTeX
serializer and (later) the MCP tools all read and write through it.

Times (``t``) are seconds since the session started, so a block can be
matched back to the recording once there is one.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

#: Bumped when the JSON layout changes incompatibly.
FORMAT_VERSION = 1

#: typed      — what the note-taker wrote
#: transcript — speech-to-text (v0.2)
#: important  — flagged by the note-taker as a key point
#: question   — something to ask or look up
#: image      — a picture or slide screenshot stored in the note's assets
#: heading    — a subsection heading inside a section (``level`` 2 or 3)
#: item       — a list item (``level`` 0-3 nesting, ``numbered``)
#: attachment — the icon of an attached document (``path``; ``text`` is
#:              its name), where it sits in the note
BLOCK_KINDS = ("typed", "transcript", "important", "question", "image",
               "heading", "item", "attachment")

#: Inline styles a span of block text can carry.
MARK_STYLES = ("b", "i", "u")

LAYOUTS = ("continuous", "paged")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


@dataclass
class Block:
    kind: str = "typed"
    text: str = ""
    t: Optional[float] = None
    #: Asset path relative to the note (``assets/<name>``), images only.
    path: str = ""
    id: str = field(default_factory=_new_id)
    #: Heading level (2-3) or list nesting depth (0-3).
    level: int = 0
    numbered: bool = False
    #: Inline styles as ``[start, length, style]`` over ``text``.
    marks: list[list] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in BLOCK_KINDS:
            raise ValueError(f"unknown block kind {self.kind!r}")

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "text": self.text}
        if self.t is not None:
            d["t"] = round(self.t, 2)
        if self.path:
            d["path"] = self.path
        if self.level:
            d["level"] = self.level
        if self.numbered:
            d["numbered"] = True
        if self.marks:
            d["marks"] = [list(m) for m in self.marks]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(kind=d.get("kind", "typed"), text=d.get("text", ""),
                   t=d.get("t"), path=d.get("path", ""),
                   id=d.get("id") or _new_id(), level=int(d.get("level", 0)),
                   numbered=bool(d.get("numbered", False)),
                   marks=[list(m) for m in d.get("marks", [])
                          if len(m) == 3 and m[2] in MARK_STYLES])


@dataclass
class Section:
    #: An empty title on the first section means "before any section was
    #: started" — it is exported without a heading.
    title: str = ""
    t: Optional[float] = None
    blocks: list[Block] = field(default_factory=list)
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        d = {"id": self.id, "title": self.title,
             "blocks": [b.to_dict() for b in self.blocks]}
        if self.t is not None:
            d["t"] = round(self.t, 2)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Section":
        return cls(title=d.get("title", ""), t=d.get("t"),
                   blocks=[Block.from_dict(b) for b in d.get("blocks", [])],
                   id=d.get("id") or _new_id())


@dataclass
class Segment:
    """One stretch of recognised speech in the transcript, which runs
    beside the user's own notes; *t* is when it was said (session time)."""
    t: float
    text: str

    def to_dict(self) -> dict:
        return {"t": round(self.t, 2), "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(t=float(d.get("t", 0.0)), text=d.get("text", ""))


@dataclass
class Recording:
    """One Listen-to-Stop run of the microphone, kept in the note."""
    path: str
    t0: float = 0.0          # session time the recording started
    duration: float = 0.0

    def to_dict(self) -> dict:
        return {"path": self.path, "t0": round(self.t0, 2),
                "duration": round(self.duration, 2)}

    @classmethod
    def from_dict(cls, d: dict) -> "Recording":
        return cls(path=d["path"], t0=d.get("t0", 0.0), duration=d.get("duration", 0.0))


@dataclass
class Attachment:
    """A document attached to the note (PDF, Word, slides…), kept in its
    assets under a unique name; *name* is what the user called it."""
    path: str
    name: str

    def to_dict(self) -> dict:
        return {"path": self.path, "name": self.name}

    @classmethod
    def from_dict(cls, d: dict) -> "Attachment":
        return cls(path=d["path"], name=d.get("name") or d["path"].rsplit("/", 1)[-1])


@dataclass
class Meta:
    title: str = ""
    speaker: str = ""
    date: str = ""
    place: str = ""
    #: ISO timestamp of when the session started; block times count from it.
    started: str = ""
    layout: str = "continuous"

    def __post_init__(self) -> None:
        if self.layout not in LAYOUTS:
            self.layout = "continuous"

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "Meta":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Note:
    meta: Meta = field(default_factory=Meta)
    summary: str = ""
    sections: list[Section] = field(default_factory=lambda: [Section()])
    recordings: list[Recording] = field(default_factory=list)
    transcript: list[Segment] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)

    @classmethod
    def new(cls, now: Optional[datetime] = None) -> "Note":
        now = now or datetime.now()
        return cls(meta=Meta(date=now.strftime("%d %B %Y"),
                             started=now.isoformat(timespec="seconds")))

    def __post_init__(self) -> None:
        if not self.sections:
            self.sections.append(Section())

    # ── editing ────────────────────────────────────────────────────

    @property
    def current(self) -> Section:
        """New material goes into the last section."""
        return self.sections[-1]

    def clock(self, t: Optional[float]) -> Optional[datetime]:
        """The time of day session time *t* corresponds to."""
        if t is None or not self.meta.started:
            return None
        try:
            return datetime.fromisoformat(self.meta.started) + timedelta(seconds=t)
        except ValueError:
            return None

    def time_label(self, t: Optional[float], clock: bool = True, seconds: bool = True) -> str:
        """How a time is shown: the time of day ("10:42:15") or, with
        *clock* False or no start time, the time since the start."""
        when = self.clock(t) if clock else None
        if when is not None:
            return when.strftime("%H:%M:%S" if seconds else "%H:%M")
        if t is None:
            return ""
        s = int(t)
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def speech_between(self, start: Optional[float], end: Optional[float]) -> list[Segment]:
        """Transcript segments said from *start* up to (not including)
        *end*; None leaves that side open."""
        return [g for g in self.transcript
                if (start is None or g.t >= start) and (end is None or g.t < end)]

    def elapsed(self, now: Optional[datetime] = None) -> Optional[float]:
        if not self.meta.started:
            return None
        try:
            start = datetime.fromisoformat(self.meta.started)
        except ValueError:
            return None
        return max(0.0, ((now or datetime.now()) - start).total_seconds())

    def add_section(self, title: str = "", t: Optional[float] = None) -> Section:
        sec = Section(title=title, t=t)
        self.sections.append(sec)
        return sec

    def add_block(self, kind: str, text: str = "", t: Optional[float] = None,
                  path: str = "", **kw) -> Block:
        blk = Block(kind=kind, text=text, t=t, path=path, **kw)
        self.current.blocks.append(blk)
        return blk

    def find_block(self, block_id: str) -> tuple[Section, int]:
        for sec in self.sections:
            for i, b in enumerate(sec.blocks):
                if b.id == block_id:
                    return sec, i
        raise KeyError(block_id)

    def remove_block(self, block_id: str) -> Block:
        sec, i = self.find_block(block_id)
        return sec.blocks.pop(i)

    def split_at(self, block_id: str, title: str = "") -> Section:
        """Start a new section at *block_id*, moving it and everything
        after it in its section into the new one — for "a section began
        here" decided after the fact."""
        sec, i = self.find_block(block_id)
        moved = sec.blocks[i:]
        del sec.blocks[i:]
        new = Section(title=title, t=moved[0].t, blocks=moved)
        self.sections.insert(self.sections.index(sec) + 1, new)
        return new

    def remove_section(self, section_id: str) -> None:
        """Drop a section heading; its blocks join the previous section.
        The first section cannot be removed, only emptied of its title."""
        idx = next(i for i, s in enumerate(self.sections) if s.id == section_id)
        if idx == 0:
            self.sections[0].title = ""
            return
        sec = self.sections.pop(idx)
        self.sections[idx - 1].blocks.extend(sec.blocks)

    def attachment_blocks(self) -> list[Attachment]:
        return [Attachment(b.path, b.text) for s in self.sections for b in s.blocks
                if b.kind == "attachment"]

    def asset_paths(self) -> list[str]:
        return ([b.path for s in self.sections for b in s.blocks if b.path]
                + [r.path for r in self.recordings]
                + [a.path for a in self.attachments])

    def plain_text(self) -> str:
        """The note as lightly marked-up text, for an AI to read."""
        m = self.meta
        lines = [f"# {m.title}" if m.title else "# Notes"]
        lines += [x for x in (m.speaker, m.date, m.place) if x]
        if self.attachments:
            lines.append("Attached: " + ", ".join(a.name for a in self.attachments))
        for sec in self.sections:
            if sec.title:
                lines += ["", f"## {sec.title}"]
            for b in sec.blocks:
                if b.kind == "heading":
                    lines += ["", "#" * (b.level + 1) + " " + b.text]
                elif b.kind == "item":
                    marker = "1." if b.numbered else "-"
                    lines.append("  " * b.level + f"{marker} {b.text}")
                elif b.kind == "image":
                    lines.append(f"[image{': ' + b.text if b.text else ''}]")
                elif b.kind == "attachment":
                    lines.append(f"[attached document: {b.text}]")
                else:
                    prefix = {"important": "Key point: ", "question": "Question: ",
                              "transcript": "(said) "}.get(b.kind, "")
                    lines.append(prefix + b.text)
        if self.transcript:
            lines += ["", "## What was said (transcript)"]
            lines += [f"[{self.time_label(g.t)}] {g.text}" for g in self.transcript]
        return "\n".join(lines).strip() + "\n"

    # ── persistence ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"format": FORMAT_VERSION, "meta": self.meta.to_dict(),
                "summary": self.summary,
                "sections": [s.to_dict() for s in self.sections],
                "recordings": [r.to_dict() for r in self.recordings],
                "transcript": [g.to_dict() for g in self.transcript],
                "attachments": [a.to_dict() for a in self.attachments]}

    @classmethod
    def from_dict(cls, d: dict) -> "Note":
        fmt = d.get("format", 1)
        if fmt > FORMAT_VERSION:
            raise ValueError(
                f"this note was written by a newer KherveNote (format {fmt})")
        return cls(meta=Meta.from_dict(d.get("meta", {})),
                   summary=d.get("summary", ""),
                   sections=[Section.from_dict(s)
                             for s in d.get("sections", [])],
                   recordings=[Recording.from_dict(r) for r in d.get("recordings", [])],
                   transcript=[Segment.from_dict(g) for g in d.get("transcript", [])],
                   attachments=[Attachment.from_dict(a) for a in d.get("attachments", [])])


_MD_ITEM = re.compile(r"^(\s*)([-*•]|\d{1,3}[.)])\s+(.*)$")
_MD_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def markdown_blocks(text: str, top_level: int = 2) -> list[Block]:
    """Blocks from the light Markdown an AI answers in: ``#`` headings
    (shifted so the shallowest becomes *top_level*), ``-`` / ``1.``
    items nested by indent, ``**bold**``, and paragraphs between blank
    lines."""
    out: list[Block] = []
    para: list[str] = []
    widths: list[int] = []
    heads = [len(m.group(1)) for m in map(_MD_HEAD.match, text.splitlines()) if m]
    shift = top_level - min(heads) if heads else 0

    def rich(s: str) -> tuple[str, list[list]]:
        marks, plain, pos = [], "", 0
        for m in _MD_BOLD.finditer(s):
            plain += s[pos:m.start()]
            inner = m.group(1) or m.group(2)
            marks.append([len(plain), len(inner), "b"])
            plain += inner
            pos = m.end()
        return plain + s[pos:], marks

    def flush() -> None:
        if para:
            t, marks = rich(" ".join(para))
            out.append(Block(kind="typed", text=t, marks=marks))
            para.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            widths.clear()
            continue
        head = _MD_HEAD.match(line.strip())
        item = _MD_ITEM.match(line)
        if head:
            flush()
            level = max(2, min(3, len(head.group(1)) + shift))
            out.append(Block(kind="heading", text=rich(head.group(2).strip("# "))[0], level=level))
        elif item:
            flush()
            width = len(item.group(1).expandtabs(4))
            while widths and widths[-1] > width:
                widths.pop()
            if not widths or widths[-1] < width:
                widths.append(width)
            t, marks = rich(item.group(3).strip())
            out.append(Block(kind="item", text=t, marks=marks, level=min(3, len(widths) - 1),
                             numbered=item.group(2)[0].isdigit()))
        else:
            para.append(line.strip())
    flush()
    return out
