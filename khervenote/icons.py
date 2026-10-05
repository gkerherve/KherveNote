# KherveNote — toolbar icons
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Toolbar icons drawn with QPainter, so no image files ship."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from . import theme

_SIZE = 24


def _fg() -> QColor:
    return theme.color("text")


def _accent() -> QColor:
    return theme.color("accent")


def _accent2() -> QColor:
    return theme.color("accent2")


def _red() -> QColor:
    return theme.color("red")


def _paper() -> QColor:
    return theme.color("page")


def _canvas() -> tuple[QPixmap, QPainter]:
    px = QPixmap(_SIZE, _SIZE)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    return px, p


def _pen(color: QColor | None = None, w: float = 2.0) -> QPen:
    pen = QPen(color if color is not None else _fg(), w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _done(px: QPixmap, p: QPainter) -> QIcon:
    p.end()
    return QIcon(px)


def _page(p: QPainter) -> None:
    p.setPen(_pen(_fg(), 1.6))
    p.setBrush(_paper())
    path = QPainterPath()
    path.moveTo(5, 3)
    path.lineTo(15, 3)
    path.lineTo(19, 7)
    path.lineTo(19, 21)
    path.lineTo(5, 21)
    path.closeSubpath()
    p.drawPath(path)


def new_note() -> QIcon:
    px, p = _canvas()
    _page(p)
    p.setPen(_pen(_accent(), 2))
    p.drawLine(QPointF(12, 10), QPointF(12, 16))
    p.drawLine(QPointF(9, 13), QPointF(15, 13))
    return _done(px, p)


def open_note() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.6))
    p.setBrush(QColor("#f3c969"))
    p.drawPolygon(QPolygonF([QPointF(2, 6), QPointF(9, 6), QPointF(11, 8),
                             QPointF(22, 8), QPointF(22, 19), QPointF(2, 19)]))
    return _done(px, p)


def save_note() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.6))
    p.setBrush(_accent())
    p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2, 2)
    p.setBrush(_paper())
    p.drawRect(QRectF(7, 3.5, 10, 6))
    p.drawRect(QRectF(7, 13, 10, 7.5))
    return _done(px, p)


def microphone(recording: bool = False) -> QIcon:
    px, p = _canvas()
    color = _red() if recording else _fg()
    p.setPen(_pen(color, 1.8))
    p.setBrush(color if recording else Qt.NoBrush)
    p.drawRoundedRect(QRectF(9, 2.5, 6, 11), 3, 3)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(6, 6, 12, 11), 180 * 16, 180 * 16)
    p.drawLine(QPointF(12, 17), QPointF(12, 21))
    p.drawLine(QPointF(8.5, 21), QPointF(15.5, 21))
    return _done(px, p)


def new_section() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_accent(), 2.4))
    p.drawLine(QPointF(3, 6), QPointF(21, 6))
    p.setPen(_pen(_fg(), 1.6))
    for y in (11, 15, 19):
        p.drawLine(QPointF(3, y), QPointF(21 if y < 19 else 14, y))
    return _done(px, p)


def star() -> QIcon:
    px, p = _canvas()
    pts = []
    for i in range(10):
        r = 9.5 if i % 2 == 0 else 4
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(QPointF(12 + r * math.cos(a), 12.5 + r * math.sin(a)))
    p.setPen(_pen(_accent2(), 1.4))
    p.setBrush(_accent2())
    p.drawPolygon(QPolygonF(pts))
    return _done(px, p)


def question() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_accent(), 1.6))
    p.drawEllipse(QRectF(2.5, 2.5, 19, 19))
    f = QFont()
    f.setPointSize(13)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(2.5, 2.5, 19, 19), Qt.AlignCenter, "?")
    return _done(px, p)


def bullets() -> QIcon:
    px, p = _canvas()
    for y, x in ((6, 3), (12, 7), (18, 3)):
        p.setPen(Qt.NoPen)
        p.setBrush(_accent())
        p.drawEllipse(QRectF(x, y - 1.6, 3.2, 3.2))
        p.setPen(_pen(_fg(), 1.8))
        p.drawLine(QPointF(x + 6, y), QPointF(21, y))
    return _done(px, p)


def numbering() -> QIcon:
    px, p = _canvas()
    f = QFont()
    f.setPixelSize(7)
    f.setBold(True)
    p.setFont(f)
    for y, x, label in ((6, 1, "1"), (12, 5, "1.1"), (18, 1, "2")):
        p.setPen(_accent())
        p.drawText(QRectF(x, y - 4, 10, 8), Qt.AlignLeft | Qt.AlignVCenter, label)
        p.setPen(_pen(_fg(), 1.8))
        p.drawLine(QPointF(x + (10 if len(label) > 1 else 6), y), QPointF(21, y))
    return _done(px, p)


def image() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.6))
    p.setBrush(_paper())
    p.drawRoundedRect(QRectF(2.5, 4.5, 19, 15), 2, 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#4caf50"))
    p.drawPolygon(QPolygonF([QPointF(4, 18), QPointF(10, 10), QPointF(14, 15),
                             QPointF(16, 13), QPointF(20, 18)]))
    p.setBrush(_accent2())
    p.drawEllipse(QRectF(15, 7, 3.5, 3.5))
    return _done(px, p)


def _badge(text: str, color: QColor) -> QIcon:
    px, p = _canvas()
    _page(p)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(1, 12, 22, 9), 2, 2)
    f = QFont()
    f.setPixelSize(8)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(1, 12, 22, 9), Qt.AlignCenter, text)
    return _done(px, p)


_DOC_BADGES = {"pdf": ("PDF", "#d0302b"), "word": ("DOC", "#2b579a"),
               "slides": ("PPT", "#c43e1c"), "text": ("TXT", "#6b6b6b")}


def document(kind: str) -> QIcon:
    label, color = _DOC_BADGES.get(kind, ("DOC", "#6b6b6b"))
    return _badge(label, QColor(color))


def paperclip() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.7))
    path = QPainterPath()
    path.moveTo(15, 7)
    path.lineTo(15, 17)
    path.arcTo(QRectF(9, 13, 6, 8), 0, -180)
    path.lineTo(9, 5.5)
    path.arcTo(QRectF(9, 1.5, 9, 8), 180, -180)
    path.lineTo(18, 17.5)
    path.arcTo(QRectF(6, 11, 12, 12), 0, -180)
    path.lineTo(6, 8)
    p.drawPath(path)
    return _done(px, p)


def export_pdf() -> QIcon:
    return _badge("PDF", _red())


def export_tex() -> QIcon:
    return _badge("TEX", _accent())


def _letter(text: str, *, bold=False, italic=False, underline=False) -> QIcon:
    px, p = _canvas()
    f = QFont("Georgia")
    f.setPixelSize(17)
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    p.setFont(f)
    p.setPen(_fg())
    p.drawText(QRectF(0, 0, _SIZE, _SIZE), Qt.AlignCenter, text)
    return _done(px, p)


def bold() -> QIcon:
    return _letter("B", bold=True)


def italic() -> QIcon:
    return _letter("I", italic=True)


def underline() -> QIcon:
    return _letter("U", underline=True)


def camera() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(2.5, 7, 19, 13), 2.5, 2.5)
    p.drawRect(QRectF(8, 4, 8, 3))
    p.setPen(_pen(_accent(), 1.8))
    p.drawEllipse(QRectF(8, 9.5, 8, 8))
    return _done(px, p)


def sparkle() -> QIcon:
    """The local-AI (Ollama) actions."""
    px, p = _canvas()
    p.setPen(Qt.NoPen)
    p.setBrush(_accent())
    for cx, cy, r in ((10, 12, 7), (18.5, 5.5, 3.2)):
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.quadTo(cx, cy, cx + r, cy)
        path.quadTo(cx, cy, cx, cy + r)
        path.quadTo(cx, cy, cx - r, cy)
        path.quadTo(cx, cy, cx, cy - r)
        p.drawPath(path)
    return _done(px, p)


def _arrow(mirror: bool) -> QIcon:
    px, p = _canvas()
    if mirror:
        p.translate(_SIZE, 0)
        p.scale(-1, 1)
    p.setPen(_pen(_fg(), 2.0))
    path = QPainterPath()
    path.moveTo(6, 10)
    path.lineTo(15, 10)
    path.cubicTo(22, 10, 22, 20, 15, 20)
    path.lineTo(10, 20)
    p.drawPath(path)
    p.drawLine(QPointF(6, 10), QPointF(10, 6))
    p.drawLine(QPointF(6, 10), QPointF(10, 14))
    return _done(px, p)


def calendar() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 5, 17, 15.5), 2, 2)
    p.drawLine(QPointF(3.5, 9.5), QPointF(20.5, 9.5))
    p.drawLine(QPointF(8, 3), QPointF(8, 7))
    p.drawLine(QPointF(16, 3), QPointF(16, 7))
    p.setPen(Qt.NoPen)
    p.setBrush(_accent())
    for x, y in ((7, 12), (11, 12), (15, 12), (7, 16), (11, 16)):
        p.drawRect(QRectF(x, y, 2.4, 2.4))
    return _done(px, p)


def undo() -> QIcon:
    return _arrow(False)


def redo() -> QIcon:
    return _arrow(True)


def help_book() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(_fg(), 1.6))
    p.drawRoundedRect(QRectF(4, 3, 16, 18), 2, 2)
    f = QFont()
    f.setPixelSize(13)
    f.setBold(True)
    p.setFont(f)
    p.setPen(_accent())
    p.drawText(QRectF(4, 3, 16, 18), Qt.AlignCenter, "?")
    return _done(px, p)


def app_icon() -> QIcon:
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1a6dd8"))
    p.drawRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
    p.setPen(_pen(QColor("white"), 4))
    for y in (22, 32, 42):
        p.drawLine(QPointF(16, y), QPointF(48 if y < 42 else 36, y))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#d0302b"))
    p.drawEllipse(QRectF(40, 38, 14, 14))
    p.end()
    return QIcon(px)
