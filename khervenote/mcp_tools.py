# KherveNote — the MCP tools, run against the live window
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Each ``_t_<name>`` handles one entry of ``mcp_schema.TOOLS``.

They run on the GUI thread (the bridge calls them from its socket
handler) and must never open a modal dialog — a QMessageBox nobody asked
for would freeze the app.  Sections and paragraphs are read straight off
the page (``NoteEditor``), so the indices get_note gives are the ones the
writing tools use; every write is one edit block, so one Ctrl+Z undoes it.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QTextCursor

from . import compiler, library
from .editor import (_LINE_SEP, _OBJ, _write_block, apply_style, block_kind, block_time,
                     insert_section, list_level, list_numbered)
from .knote_file import EXTENSION
from .mcp_schema import check_args
from .model import Block, markdown_blocks
from .serializer import to_latex

#: Tool kind names -> the page's block kinds.
_KINDS = {"text": "typed", "important": "important", "question": "question",
          "transcript": "transcript"}
_NAMES = {v: k for k, v in _KINDS.items()}


class _ToolError(Exception):
    pass


class McpToolExecutor:
    def __init__(self, window):
        self._w = window

    @property
    def editor(self):
        return self._w.editor

    @property
    def note(self):
        return self._w.note

    def execute(self, name, args):
        args = args or {}
        err = check_args(name, args)
        if err:
            return {"error": err}
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            return {"error": f"Tool {name!r} is not implemented."}
        try:
            return handler(**args)
        except _ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    # ── reading the page ────────────────────────────────────────
    def _sections(self):
        """[(first block, start, end, title, [paragraph blocks])]."""
        out = []
        for first, start, end in self.editor.section_windows():
            heading = block_kind(first) == ("heading", 1)
            blocks, b = [], (first.next() if heading else first)
            while b.isValid() and block_kind(b) != ("heading", 1):
                if b.text().replace(_OBJ, "").strip() or _OBJ in b.text():
                    blocks.append(b)
                b = b.next()
            out.append((first, start, end, first.text().strip() if heading else "", blocks))
        return out

    def _section(self, index):
        secs = self._sections()
        if not 0 <= index < len(secs):
            raise _ToolError(f"No section {index}: the note has {len(secs)} "
                             f"(0-{len(secs) - 1}).")
        return secs[index]

    def _label(self, t):
        return self._w._time_label(t) if t is not None else None

    def _paragraph(self, i, b):
        kind, level = block_kind(b)
        lvl = list_level(b)
        text = b.text().replace(_LINE_SEP, "\n")
        d = {"index": i, "time": self._label(block_time(b))}
        if _OBJ in text:
            d["kind"] = "image or attached document"
            text = text.replace(_OBJ, "").strip()
        elif lvl is not None:
            d.update(kind="numbered item" if list_numbered(b) else "bullet item", level=lvl)
        elif kind == "heading":
            d.update(kind="subheading", level=level)
        else:
            d["kind"] = _NAMES.get(kind, kind)
        d["text"] = text
        return d

    # ── tools: reading ──────────────────────────────────────────
    def _t_get_note(self):
        w = self._w
        w.header.store(self.note)
        m = self.note.meta
        return {
            "title": m.title, "speaker": m.speaker, "date": m.date, "place": m.place,
            "summary": self.note.summary,
            "file": str(w.path) if w.path else None,
            "unsaved_changes": bool(w.dirty),
            "layout": m.layout,
            "terms_of_this_talk": m.vocabulary,
            "speech_lines": len(self.note.transcript),
            "sections": [
                {"index": i, "title": title or "(before the first section)",
                 "started": self._label(start),
                 "paragraphs": [self._paragraph(j, b) for j, b in enumerate(blocks)]}
                for i, (_f, start, _e, title, blocks) in enumerate(self._sections())],
        }

    def _t_get_transcript(self, section: Optional[int] = None, max_lines: int = 2000):
        segs = self.note.transcript
        span = None
        if section is not None:
            _f, start, end, title, _b = self._section(section)
            a, b = self._w._speech_window(start, end)
            segs = self.note.speech_between(a, b)
            span = {"section": section, "title": title,
                    "from": self._label(a if a is None else max(a, 0.0)),
                    "to": self._label(b)}
        lines = [{"time": self._label(g.t), "text": g.text} for g in segs[:max_lines]]
        out = {"lines": lines, "total": len(segs)}
        if span:
            out["window"] = span
        if not self.note.transcript:
            out["note"] = "Nothing has been said yet in this note (no speech transcript)."
        return out

    def _t_list_notes(self):
        root = self._w.library.root
        found = []

        def walk(folder, rel):
            for info in folder.notes:
                found.append({"path": str(info.path), "title": info.label,
                              "date": info.date, "folder": rel or "(top)",
                              "open": self._w.path is not None
                              and Path(info.path) == Path(self._w.path)})
            for sub in folder.folders:
                walk(sub, f"{rel}/{sub.name}" if rel else sub.name)
        walk(library.scan(root), "")
        return {"library": str(root), "notes": found}

    # ── tools: notes ────────────────────────────────────────────
    def _t_open_note(self, path: str):
        p = Path(path).expanduser()
        root = Path(self._w.library.root).resolve()
        if not p.is_absolute():
            p = root / p
        p = p.resolve()
        if p.suffix != EXTENSION or not p.is_file():
            raise _ToolError(f"{path} is not a {EXTENSION} note.")
        if root not in p.parents:
            raise _ToolError(f"{path} is not in the notes library ({root}).")
        if self._w.path is None or Path(self._w.path).resolve() != p:
            if not self._w._flush():
                raise _ToolError("The current note could not be saved, so it was "
                                 "not closed.")
            self._w.open_path(p)
        return self._t_get_note()

    def _t_new_note(self, title: str = ""):
        self._w.new_note()
        if title:
            self._w.header.title.setText(title)
            self._w._header_changed()
        return {"ok": True, "title": title}

    def _t_set_header(self, **fields):
        h = self._w.header
        for key in ("title", "speaker", "date", "place"):
            if key in fields and fields[key] is not None:
                getattr(h, key).setText(fields[key])
                getattr(h, key).setCursorPosition(0)
        if fields.get("summary") is not None:
            h.summary.setPlainText(fields["summary"])
            h.summary.setVisible(bool(fields["summary"].strip()))
        self._w._header_changed()
        return {"ok": True, "changed": sorted(k for k, v in fields.items() if v is not None)}

    def _t_save_note(self):
        if not self._w.save():
            raise _ToolError("The note could not be saved.")
        return {"ok": True, "file": str(self._w.path)}

    # ── tools: writing ──────────────────────────────────────────
    def _blocks(self, body, kind=None):
        blocks = markdown_blocks(body or "")
        if kind:
            for b in blocks:
                if b.kind == "typed":
                    b.kind = _KINDS[kind]
        return blocks

    def _t_add_section(self, title: str, body: str = ""):
        insert_section(self.editor, title, self._blocks(body), at_end=True)
        return {"ok": True, "section": len(self._sections()) - 1}

    def _t_fill_section(self, section: int, body: str, title: str = ""):
        first, start, end, _t, _b = self._section(section)
        if not title:
            a, b = self._w._speech_window(start, end)
            segs = self.note.speech_between(a, b)
            span = (f" ({self._label(segs[0].t)}–{self._label(segs[-1].t)})"
                    if segs else "")
            title = f"From the speech{span}"
        blocks = self._blocks(body)
        if not blocks:
            raise _ToolError("Nothing to add: body is empty.")
        insert_section(self.editor, title, blocks, level=2, within=first)
        return {"ok": True, "section": section, "heading": title,
                "paragraphs_added": len(blocks)}

    def _t_append_to_section(self, section: int, body: str, kind: Optional[str] = None):
        first, _s, _e, _t, blocks = self._section(section)
        last = blocks[-1] if blocks else first
        new = self._blocks(body, kind)
        if not new:
            raise _ToolError("Nothing to add: body is empty.")
        cur = QTextCursor(last)
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.EndOfBlock)
        doc = self.editor.document()
        blank = doc.blockCount() == 1 and not doc.firstBlock().text().strip()
        t = self.editor.clock()
        for i, b in enumerate(new):
            b.t = t
            _write_block(self.editor, cur, b, not (blank and i == 0))
        cur.endEditBlock()
        self.editor.gutter.update()
        return {"ok": True, "section": section, "paragraphs_added": len(new)}

    def _t_set_paragraph(self, section: int, paragraph: int, text: str,
                         kind: Optional[str] = None):
        _f, _s, _e, _t, blocks = self._section(section)
        if not 0 <= paragraph < len(blocks):
            raise _ToolError(f"Section {section} has {len(blocks)} paragraphs "
                             f"(0-{len(blocks) - 1}).")
        b = blocks[paragraph]
        if _OBJ in b.text():
            raise _ToolError("That paragraph holds a picture or an attached document; "
                             "it cannot be rewritten as text.")
        cur = QTextCursor(b)
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        cur.insertText(text.replace("\n", _LINE_SEP))
        if kind:
            apply_style(cur.block(), _KINDS[kind])
        cur.endEditBlock()
        return {"ok": True}

    # ── tools: export ───────────────────────────────────────────
    def _latex(self, layout, show_times, transcript):
        w = self._w
        return to_latex(w._sync_note(), layout, show_times=show_times,
                        transcript=transcript, asset_dir=w.work_dir)

    def _t_export_latex(self, path: str, layout: Optional[str] = None,
                        show_times: bool = False, transcript: bool = False):
        dest = Path(path).expanduser()
        if not dest.is_absolute():
            raise _ToolError("path must be absolute.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self._latex(layout, show_times, transcript), encoding="utf-8")
        if self.note.asset_paths() and (self._w.work_dir / "assets").is_dir():
            shutil.copytree(self._w.work_dir / "assets", dest.parent / "assets",
                            dirs_exist_ok=True)
        return {"ok": True, "path": str(dest)}

    def _t_export_pdf(self, path: str, layout: Optional[str] = None,
                      show_times: bool = False, transcript: bool = False):
        dest = Path(path).expanduser()
        if not dest.is_absolute():
            raise _ToolError("path must be absolute.")
        tex = self._latex(layout, show_times, transcript)
        res = compiler.compile_tex(tex, self._w.work_dir / "build-mcp", self._w.work_dir)
        if not res.ok:
            raise _ToolError(f"The PDF could not be built: {res.error}\n"
                             f"{res.log[-1500:]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(res.pdf_path, dest)
        heights = compiler.pdf_page_heights_mm(dest)
        return {"ok": True, "path": str(dest), "pages": len(heights),
                "page_heights_mm": [round(h) for h in heights]}
