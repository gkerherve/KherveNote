# KherveNote — the note editor
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""One endless rich-text page you write on directly, like a notepad.

Every paragraph (``QTextBlock``) is one model block.  Its kind lives in
the block format (``KIND``/``LEVEL`` properties), so it survives undo
and copy-paste; its capture time lives in the block's user data, so
stamping a new paragraph never touches the document or the undo stack.
A section is a level-1 heading; lists are ``QTextList``s.

The editor is the live view.  ``document_to_note`` reads it back into
the model (for saving, export and the AI tools) and ``load_note`` fills
it from the model; nothing else crosses between the two.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor, QFont, QImage, QPainter, QTextBlock, QTextBlockFormat,
    QTextBlockUserData, QTextCharFormat, QTextCursor, QTextDocument,
    QTextFormat, QTextImageFormat, QTextListFormat,
)
from PySide6.QtWidgets import QTextEdit, QWidget

from . import theme
from .model import Block, Note, Section
from .serializer import format_time

KIND = QTextFormat.UserProperty + 1
LEVEL = QTextFormat.UserProperty + 2

#: (label, kind, level) for the style picker, in menu order.
STYLES = (
    ("Text", "typed", 0),
    ("Section", "heading", 1),
    ("Subsection", "heading", 2),
    ("Sub-subsection", "heading", 3),
    ("Key point", "important", 0),
    ("Question", "question", 0),
    ("Transcript", "transcript", 0),
)
_HEADING_PT = {1: 20.0, 2: 16.0, 3: 13.5}
BASE_PT = 13.0
_NUMBERED = (QTextListFormat.ListDecimal, QTextListFormat.ListLowerAlpha,
             QTextListFormat.ListUpperAlpha, QTextListFormat.ListLowerRoman,
             QTextListFormat.ListUpperRoman)
_MARKER_RE = re.compile(r"\s*([-*•]|\d{1,3}[.)])")
_OBJ = "￼"           # where an image sits in block text
_LINE_SEP = " "      # Shift+Enter inside a paragraph
MAX_COLUMN = 780
GUTTER = 64


class BlockMeta(QTextBlockUserData):
    def __init__(self, t: Optional[float]) -> None:
        super().__init__()
        self.t = t
        #: When speech was last appended to this paragraph.
        self.t_last = t


# ── per-block styling ───────────────────────────────────────────────

def block_kind(block: QTextBlock) -> tuple[str, int]:
    fmt = block.blockFormat()
    kind = fmt.property(KIND) or "typed"
    return kind, int(fmt.property(LEVEL) or 0)


def block_time(block: QTextBlock) -> Optional[float]:
    meta = block.userData()
    return meta.t if isinstance(meta, BlockMeta) else None


def _style_formats(kind: str, level: int) -> tuple[QTextBlockFormat, QTextCharFormat]:
    bf = QTextBlockFormat()
    bf.setProperty(KIND, kind)
    bf.setProperty(LEVEL, level)
    cf = QTextCharFormat()
    cf.setForeground(theme.color("text"))
    cf.setFontPointSize(BASE_PT)
    cf.setFontWeight(QFont.Normal)
    cf.setFontItalic(False)
    bf.setTopMargin(0)
    bf.setBottomMargin(6)
    bf.clearBackground()
    if kind == "heading":
        bf.setTopMargin({1: 22, 2: 14, 3: 10}.get(level, 10))
        bf.setBottomMargin(4)
        cf.setFontPointSize(_HEADING_PT.get(level, BASE_PT))
        cf.setFontWeight(QFont.Bold)
        cf.setForeground(theme.color("heading"))
    elif kind == "transcript":
        cf.setForeground(theme.color("muted"))
    elif kind == "important":
        bf.setBackground(theme.color("key_bg"))
        cf.setForeground(theme.color("key_fg"))
    elif kind == "question":
        cf.setForeground(theme.color("question"))
        cf.setFontItalic(True)
    return bf, cf


def apply_style(block: QTextBlock, kind: str, level: int = 0,
                cursor: Optional[QTextCursor] = None) -> None:
    """Give *block* a style.  Inline bold / italic / underline the user
    added survive, except bold that came from a heading and italic that
    came from a question."""
    old_kind, _ = block_kind(block)
    bf, cf = _style_formats(kind, level)
    cur = QTextCursor(block)
    merged = block.blockFormat()
    merged.merge(bf)
    if kind != "important":
        merged.clearBackground()
    cur.setBlockFormat(merged)
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        it += 1
        if not frag.isValid() or frag.charFormat().isImageFormat():
            continue
        fcf = frag.charFormat()
        own = QTextCharFormat(cf)
        if kind != "heading" and old_kind != "heading" and fcf.fontWeight() >= QFont.DemiBold:
            own.setFontWeight(QFont.Bold)
        if old_kind != "question" and fcf.fontItalic():
            own.setFontItalic(True)
        c = QTextCursor(block.document())
        c.setPosition(frag.position())
        c.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
        c.mergeCharFormat(own)
    cur.setPosition(block.position())
    cur.setBlockCharFormat(cf)


# ── lists ───────────────────────────────────────────────────────────

def list_level(block: QTextBlock) -> Optional[int]:
    lst = block.textList()
    return None if lst is None else lst.format().indent() - 1


def list_numbered(block: QTextBlock) -> bool:
    lst = block.textList()
    return lst is not None and lst.format().style() in _NUMBERED


def set_list(block: QTextBlock, numbered: Optional[bool], level: int = 0) -> None:
    """Make *block* an item at *level* (joining the list above it so
    numbering continues), or a plain paragraph when *numbered* is None."""
    old = block.textList()
    if old is not None:
        old.remove(block)
        # remove() folds the list's indent into the paragraph's.
        bf = block.blockFormat()
        bf.setIndent(0)
        QTextCursor(block).setBlockFormat(bf)
    if numbered is None:
        return
    level = max(0, min(3, level))
    style = QTextListFormat.ListDecimal if numbered else QTextListFormat.ListDisc
    b = block.previous()
    while b.isValid() and b.textList() is not None:
        ind = b.textList().format().indent()
        if ind == level + 1:
            if b.textList().format().style() == style:
                b.textList().add(block)
                return
            break
        if ind < level + 1:
            break
        b = b.previous()
    fmt = QTextListFormat()
    fmt.setStyle(style)
    fmt.setIndent(level + 1)
    QTextCursor(block).createList(fmt)


# ── the gutter ──────────────────────────────────────────────────────

class _Gutter(QWidget):
    """Times and kind markers to the left of the text column."""

    _MARKS = {"important": ("★", "accent2"), "question": ("?", "accent"),
              "transcript": ("…", "muted")}

    def __init__(self, editor: "NoteEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        ed = self.editor
        doc = ed.document()
        layout = doc.documentLayout()
        scroll = ed.verticalScrollBar().value()
        small = QFont(ed.font())
        small.setPointSizeF(9)
        p.setFont(small)
        block = doc.begin()
        prev_list = False
        while block.isValid():
            rect = layout.blockBoundingRect(block)
            if rect.top() - scroll > self.height():
                break
            in_list = block.textList() is not None
            tl = block.layout()
            if (rect.bottom() - scroll >= 0 and tl.lineCount() and block.text().strip()
                    and not (in_list and prev_list)):
                kind, _ = block_kind(block)
                line = tl.lineAt(0)
                y = tl.position().y() + line.y() - scroll
                box = QRectF(0, y, self.width() - 22, line.height())
                stamp = format_time(block_time(block))
                if stamp:
                    p.setPen(theme.color("muted"))
                    p.drawText(box, Qt.AlignRight | Qt.AlignVCenter, stamp)
                mark = self._MARKS.get(kind)
                if mark:
                    p.setPen(theme.color(mark[1]))
                    p.drawText(QRectF(self.width() - 18, y, 14, line.height()),
                               Qt.AlignCenter, mark[0])
            prev_list = in_list
            block = block.next()
        p.end()


# ── the editor ──────────────────────────────────────────────────────

class NoteEditor(QTextEdit):
    outline_changed = Signal()
    style_at_cursor = Signal(str, int)
    image_pasted = Signal(QImage)
    #: "rephrase", "summarise" or "summarise_note" from the context menu.
    ai_requested = Signal(str)

    def __init__(self, clock: Callable[[], Optional[float]], parent=None) -> None:
        super().__init__(parent)
        self.clock = clock
        self.work_dir = None
        self.setAcceptRichText(False)
        self.setFrameShape(QTextEdit.NoFrame)
        self.setTabChangesFocus(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setPlaceholderText("Start writing… — Ctrl+1 for a section, “- ” or “1. ” "
                                "for a list, the microphone to write what is said")
        doc = self.document()
        doc.setDocumentMargin(28)
        f = QFont(self.font())
        f.setPointSizeF(BASE_PT)
        doc.setDefaultFont(f)
        doc.contentsChange.connect(self._stamp)
        self._outline_timer = QTimer(self, singleShot=True, interval=400)
        self._outline_timer.timeout.connect(self.outline_changed)
        doc.contentsChanged.connect(self._outline_timer.start)
        self.cursorPositionChanged.connect(self._report_style)
        self.gutter = _Gutter(self)
        self.verticalScrollBar().valueChanged.connect(self.gutter.update)
        doc.documentLayout().documentSizeChanged.connect(lambda *_: self.gutter.update())
        self.apply_theme()

    # theme & geometry

    def apply_theme(self) -> None:
        page, text = theme.hex_("page"), theme.hex_("text")
        self.setStyleSheet(f"QTextEdit{{background:{page}; color:{text}; border:none;}}")
        block = self.document().begin()
        cur = QTextCursor(self.document())
        cur.beginEditBlock()
        while block.isValid():
            kind, level = block_kind(block)
            apply_style(block, kind, level, cur)
            block = block.next()
        cur.endEditBlock()
        self.gutter.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        # Margins first: QTextEdit lays the text out for the viewport
        # width in its own resizeEvent.  (The viewport's resizes arrive
        # here too, so measure the widget, not the event.)
        side = max(GUTTER + 8, (self.width() - MAX_COLUMN) // 2)
        self.setViewportMargins(side, 0, max(16, side - GUTTER), 0)
        super().resizeEvent(event)
        self.gutter.setGeometry(side - GUTTER - 4, 0, GUTTER, self.viewport().height())

    def sizeHint(self) -> QSize:
        return QSize(900, 700)

    # stamping & state

    def _stamp(self, pos: int, removed: int, added: int) -> None:
        doc = self.document()
        block = doc.findBlock(pos)
        end = doc.findBlock(pos + added)
        t = None
        while block.isValid():
            if not isinstance(block.userData(), BlockMeta):
                if t is None:
                    t = self.clock()
                block.setUserData(BlockMeta(t))
            if block == end:
                break
            block = block.next()

    def _report_style(self) -> None:
        block = self.textCursor().block()
        kind, level = block_kind(block)
        self.style_at_cursor.emit(kind, level)

    def _selected_blocks(self) -> list[QTextBlock]:
        cur = self.textCursor()
        doc = self.document()
        first = doc.findBlock(cur.selectionStart())
        last = doc.findBlock(cur.selectionEnd())
        out = []
        b = first
        while b.isValid():
            out.append(b)
            if b == last:
                break
            b = b.next()
        return out

    # commands

    def set_style(self, kind: str, level: int = 0) -> None:
        cur = self.textCursor()
        cur.beginEditBlock()
        for block in self._selected_blocks():
            if kind == "heading" and block.textList() is not None:
                set_list(block, None)
            apply_style(block, kind, level, QTextCursor(cur))
        cur.endEditBlock()
        self._report_style()

    def toggle_list(self, numbered: bool) -> None:
        cur = self.textCursor()
        cur.beginEditBlock()
        blocks = self._selected_blocks()
        on = not all(b.textList() is not None and list_numbered(b) == numbered for b in blocks)
        for block in blocks:
            kind, _ = block_kind(block)
            if on and kind == "heading":
                apply_style(block, "typed", 0, QTextCursor(cur))
            set_list(block, numbered if on else None, list_level(block) or 0)
        cur.endEditBlock()

    def indent_item(self, step: int) -> None:
        cur = self.textCursor()
        cur.beginEditBlock()
        for block in self._selected_blocks():
            level = list_level(block)
            if level is None:
                continue
            if level + step < 0:
                set_list(block, None)
            else:
                set_list(block, list_numbered(block), level + step)
        cur.endEditBlock()

    def set_mark(self, style: str) -> None:
        cf = QTextCharFormat()
        cur = self.textCursor()
        cur_cf = cur.charFormat()
        if style == "b":
            cf.setFontWeight(QFont.Normal if cur_cf.fontWeight() >= QFont.DemiBold else QFont.Bold)
        elif style == "i":
            cf.setFontItalic(not cur_cf.fontItalic())
        else:
            cf.setFontUnderline(not cur_cf.fontUnderline())
        self.mergeCurrentCharFormat(cf)

    def new_section(self, title: str = "") -> None:
        """A section heading on a new line after the current paragraph."""
        cur = self.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.EndOfBlock)
        if cur.block().text().strip() or cur.block().textList() is not None:
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
        set_list(cur.block(), None)
        apply_style(cur.block(), "heading", 1, QTextCursor(cur))
        if title:
            cur.insertText(title)
        cur.endEditBlock()
        self.setTextCursor(cur)

    def insert_image(self, rel: str, image: QImage, caption: str = "") -> None:
        self.document().addResource(QTextDocument.ImageResource, QUrl(rel), image)
        cur = self.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.EndOfBlock)
        if cur.block().text().strip():
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
        set_list(cur.block(), None)
        apply_style(cur.block(), "typed", 0, QTextCursor(cur))
        _insert_image_at(cur, rel, image)
        if caption:
            cur.insertText(" " + caption)
        cur.insertBlock()
        apply_style(cur.block(), "typed", 0, QTextCursor(cur))
        cur.endEditBlock()
        self.setTextCursor(cur)

    def append_transcript(self, text: str, t: float) -> None:
        """Write recognised speech at the end of the note, without
        disturbing the user: if they are typing in the last paragraph,
        the speech goes just above it; their cursor and selection never
        move.  Speech that follows on quickly joins the paragraph before
        it, so the transcript reads as prose rather than one line per
        pause."""
        doc = self.document()
        user = self.textCursor()
        pos, anchor = user.position(), user.anchor()
        last = doc.lastBlock()
        kind_last, _ = block_kind(last)
        if last.previous().isValid() and (
                not last.text().strip()
                or (user.block() == last and kind_last not in ("heading", "transcript"))):
            after = last.previous()
        else:
            after = last
        cur = QTextCursor(after)
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.EndOfBlock)
        insert_at = cur.position()
        meta = after.userData()
        kind_after, _ = block_kind(after)
        if (kind_after == "transcript" and isinstance(meta, BlockMeta)
                and meta.t_last is not None and t - meta.t_last < 25
                and len(after.text()) < 500):
            cur.insertText(" " + text)
            meta.t_last = t
        elif not after.text().strip() and after.textList() is None and kind_after != "heading":
            apply_style(after, "transcript")
            after.setUserData(BlockMeta(t))
            cur.insertText(text)
        else:
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
            apply_style(cur.block(), "transcript")
            cur.block().setUserData(BlockMeta(t))
            cur.insertText(text)
        cur.endEditBlock()
        if insert_at >= max(pos, anchor):
            # Text went in at or after the user's cursor, so its numbers
            # still hold — but Qt pushes a cursor sitting exactly at the
            # insertion point along with the new text; put it back.
            restore = QTextCursor(doc)
            restore.setPosition(anchor)
            restore.setPosition(pos, QTextCursor.KeepAnchor)
            self.setTextCursor(restore)
        self.gutter.update()

    def loadResource(self, rtype: int, url: QUrl):  # noqa: N802
        if rtype == QTextDocument.ImageResource and self.work_dir is not None:
            img = QImage(str(self.work_dir / url.toString()))
            if not img.isNull():
                return img
        return super().loadResource(rtype, url)

    def headings(self) -> list[tuple[int, str, int]]:
        """(level, title, block number) of every heading, for the outline."""
        out = []
        block = self.document().begin()
        while block.isValid():
            kind, level = block_kind(block)
            if kind == "heading":
                out.append((level, block.text().strip(), block.blockNumber()))
            block = block.next()
        return out

    def go_to_block(self, number: int) -> None:
        block = self.document().findBlockByNumber(number)
        if not block.isValid():
            return
        cur = QTextCursor(block)
        self.setTextCursor(cur)
        top = self.document().documentLayout().blockBoundingRect(block).top()
        self.verticalScrollBar().setValue(int(top) - 12)
        self.setFocus()

    # keys

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key, mods = event.key(), event.modifiers()
        cur = self.textCursor()
        block = cur.block()
        if key in (Qt.Key_Return, Qt.Key_Enter) and not mods & Qt.ShiftModifier:
            if block.textList() is not None and not block.text().strip():
                # Enter on an empty item steps out of the list, like Word.
                self.indent_item(-1)
                return
            kind, _ = block_kind(block)
            super().keyPressEvent(event)
            if kind in ("heading", "transcript"):
                # A new line after a heading (or what the microphone
                # wrote) is the user's own text.
                apply_style(self.textCursor().block(), "typed")
            return
        if key == Qt.Key_Tab and block.textList() is not None:
            self.indent_item(1)
            return
        if key == Qt.Key_Backtab and block.textList() is not None:
            self.indent_item(-1)
            return
        if key == Qt.Key_Backspace and block.textList() is not None and cur.positionInBlock() == 0 \
                and not cur.hasSelection():
            self.indent_item(-1)
            return
        if key == Qt.Key_Space and not cur.hasSelection() and block.textList() is None:
            before = block.text()[:cur.positionInBlock()]
            m = _MARKER_RE.fullmatch(before)
            kind, _ = block_kind(block)
            if m and kind in ("typed", "important", "question"):
                cur.beginEditBlock()
                cur.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
                cur.removeSelectedText()
                set_list(cur.block(), m.group(1)[0].isdigit(), 0)
                cur.endEditBlock()
                return
        super().keyPressEvent(event)

    # local AI

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self.textCursor().hasSelection():
            self.setTextCursor(self.cursorForPosition(event.pos()))
        menu = self.createStandardContextMenu(event.pos())
        menu.addSeparator()
        sel = self.textCursor().hasSelection()
        menu.addAction("Rephrase with local AI" + ("" if sel else " (this paragraph)"),
                       lambda: self.ai_requested.emit("rephrase"))
        menu.addAction("Summarise with local AI" + ("" if sel else " (this section)"),
                       lambda: self.ai_requested.emit("summarise"))
        menu.addAction("Summarise the whole note with local AI",
                       lambda: self.ai_requested.emit("summarise_note"))
        menu.exec(event.globalPos())

    def paragraph_range(self) -> QTextCursor:
        """The selection, or the paragraph under the cursor."""
        cur = QTextCursor(self.textCursor())
        if not cur.hasSelection():
            cur.movePosition(QTextCursor.StartOfBlock)
            cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        return cur

    def section_range(self) -> QTextCursor:
        """The selection, or the body of the section the cursor is in
        (after its heading, up to the next section)."""
        cur = QTextCursor(self.textCursor())
        if cur.hasSelection():
            return cur
        block = cur.block()
        start = block
        while start.isValid() and block_kind(start) != ("heading", 1):
            start = start.previous()
        first = start.next() if start.isValid() else self.document().begin()
        end = first
        while end.next().isValid() and block_kind(end.next()) != ("heading", 1):
            end = end.next()
        cur.setPosition(first.position())
        cur.setPosition(end.position() + end.length() - 1, QTextCursor.KeepAnchor)
        return cur

    def section_title(self) -> str:
        block = self.textCursor().block()
        while block.isValid():
            if block_kind(block) == ("heading", 1):
                return block.text().strip()
            block = block.previous()
        return ""

    def replace_range(self, cur: QTextCursor, text: str) -> None:
        """Put *text* where *cur* selects, as the user's own text: what
        the microphone wrote becomes ordinary paragraphs once rewritten."""
        cur.beginEditBlock()
        start = cur.selectionStart()
        cur.insertText(text.strip())
        end = cur.position()
        block = self.document().findBlock(start)
        while block.isValid() and block.position() <= end:
            if block_kind(block)[0] == "transcript":
                apply_style(block, "typed")
            block = block.next()
        cur.endEditBlock()

    def insert_summary_after(self, cur: QTextCursor, text: str) -> None:
        """A key-point paragraph holding *text*, after the range *cur*."""
        at = QTextCursor(self.document())
        at.setPosition(cur.selectionEnd())
        at.beginEditBlock()
        at.movePosition(QTextCursor.EndOfBlock)
        at.insertBlock(QTextBlockFormat(), QTextCharFormat())
        set_list(at.block(), None)
        apply_style(at.block(), "important")
        at.block().setUserData(BlockMeta(self.clock()))
        at.insertText(text.strip().replace("\n", _LINE_SEP))
        at.endEditBlock()
        self.setTextCursor(at)

    # paste

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        if source.hasImage() and not source.hasText():
            img = QImage(source.imageData())
            if not img.isNull():
                self.image_pasted.emit(img)
                return
        super().insertFromMimeData(source)


def _insert_image_at(cur: QTextCursor, rel: str, image: QImage) -> None:
    fmt = QTextImageFormat()
    fmt.setName(rel)
    if not image.isNull():
        w = min(image.width(), 620)
        fmt.setWidth(w)
        fmt.setHeight(image.height() * w / max(1, image.width()))
    cur.insertImage(fmt)


# ── model ⇄ document ────────────────────────────────────────────────

def _marks(block: QTextBlock, kind: str) -> list[list]:
    marks: list[list] = []
    it = block.begin()
    base = block.position()
    while not it.atEnd():
        frag = it.fragment()
        if frag.isValid():
            cf = frag.charFormat()
            start, length = frag.position() - base, frag.length()
            styles = []
            if kind != "heading" and cf.fontWeight() >= QFont.DemiBold:
                styles.append("b")
            if kind != "question" and cf.fontItalic():
                styles.append("i")
            if cf.fontUnderline():
                styles.append("u")
            for st in styles:
                prev = next((m for m in reversed(marks) if m[2] == st), None)
                if prev is not None and prev[0] + prev[1] == start:
                    prev[1] += length
                else:
                    marks.append([start, length, st])
        it += 1
    return sorted(marks)


def document_to_note(doc: QTextDocument, note: Note) -> Note:
    """Rebuild *note*'s sections from the editor's document, keeping its
    meta and summary."""
    sections = [Section()]
    block = doc.begin()
    while block.isValid():
        raw = block.text()
        text = raw.replace(_LINE_SEP, "\n")
        kind, level = block_kind(block)
        t = block_time(block)
        images = []
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                images.append(frag.charFormat().toImageFormat().name())
            it += 1
        lvl = list_level(block)
        if images:
            caption = text.replace(_OBJ, "").strip()
            for i, path in enumerate(images):
                sections[-1].blocks.append(Block(kind="image", path=path, t=t,
                                                 text=caption if i == len(images) - 1 else ""))
        elif lvl is not None:
            sections[-1].blocks.append(Block(kind="item", text=text.strip(), t=t, level=lvl,
                                             numbered=list_numbered(block),
                                             marks=_marks(block, "item")))
        elif kind == "heading" and level <= 1:
            sections.append(Section(title=text.strip(), t=t))
        elif text.strip():
            blk = Block(kind=kind, text=text, t=t, marks=_marks(block, kind),
                        level=level if kind == "heading" else 0)
            sections[-1].blocks.append(blk)
        block = block.next()
    if len(sections) > 1 and not sections[0].blocks:
        # The page starts with a section heading: no untitled lead-in.
        sections.pop(0)
    note.sections = sections
    return note


def load_note(editor: NoteEditor, note: Note) -> None:
    doc = editor.document()
    doc.clear()
    cur = QTextCursor(doc)
    cur.beginEditBlock()
    first = True

    def new_block(kind: str, level: int, t: Optional[float]) -> QTextBlock:
        nonlocal first
        if not first:
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
        first = False
        block = cur.block()
        apply_style(block, kind, level, QTextCursor(cur))
        block.setUserData(BlockMeta(t))
        return block

    for i, sec in enumerate(note.sections):
        if sec.title or i > 0:
            new_block("heading", 1, sec.t)
            cur.insertText(sec.title)
        for b in sec.blocks:
            if b.kind == "image":
                new_block("typed", 0, b.t)
                img = QImage(str(editor.work_dir / b.path)) if editor.work_dir else QImage()
                doc.addResource(QTextDocument.ImageResource, QUrl(b.path), img)
                _insert_image_at(cur, b.path, img)
                if b.text:
                    cur.insertText(" " + b.text)
                continue
            kind = "typed" if b.kind == "item" else b.kind
            block = new_block(kind, b.level if b.kind == "heading" else 0, b.t)
            start = cur.position()
            cur.insertText(b.text.replace("\n", _LINE_SEP))
            for m_start, length, style in b.marks:
                c = QTextCursor(doc)
                c.setPosition(start + m_start)
                c.setPosition(min(start + m_start + length, cur.position()), QTextCursor.KeepAnchor)
                cf = QTextCharFormat()
                if style == "b":
                    cf.setFontWeight(QFont.Bold)
                elif style == "i":
                    cf.setFontItalic(True)
                else:
                    cf.setFontUnderline(True)
                c.mergeCharFormat(cf)
            if b.kind == "item":
                set_list(block, b.numbered, b.level)
    cur.endEditBlock()
    doc.clearUndoRedoStacks()
    doc.setModified(False)
    editor.gutter.update()
    editor.outline_changed.emit()
