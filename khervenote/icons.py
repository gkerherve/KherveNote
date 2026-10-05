# KherveNote — toolbar icons
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Toolbar icons drawn with QPainter, so no image files ship."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

_SIZE = 24
FG = QColor("#222")
ACCENT = QColor("#1a6dd8")
ACCENT2 = QColor("#d96b00")
RED = QColor("#d0302b")


def _canvas() -> tuple[QPixmap, QPainter]:
    px = QPixmap(_SIZE, _SIZE)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    return px, p


def _pen(color: QColor = FG, w: float = 2.0) -> QPen:
    pen = QPen(color, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _done(px: QPixmap, p: QPainter) -> QIcon:
    p.end()
    return QIcon(px)


def _page(p: QPainter) -> None:
    p.setPen(_pen(FG, 1.6))
    p.setBrush(QColor("white"))
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
    p.setPen(_pen(ACCENT, 2))
    p.drawLine(QPointF(12, 10), QPointF(12, 16))
    p.drawLine(QPointF(9, 13), QPointF(15, 13))
    return _done(px, p)


def open_note() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(FG, 1.6))
    p.setBrush(QColor("#f3c969"))
    p.drawPolygon(QPolygonF([QPointF(2, 6), QPointF(9, 6), QPointF(11, 8),
                             QPointF(22, 8), QPointF(22, 19), QPointF(2, 19)]))
    return _done(px, p)


def save_note() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(FG, 1.6))
    p.setBrush(ACCENT)
    p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2, 2)
    p.setBrush(QColor("white"))
    p.drawRect(QRectF(7, 3.5, 10, 6))
    p.drawRect(QRectF(7, 13, 10, 7.5))
    return _done(px, p)


def microphone(recording: bool = False) -> QIcon:
    px, p = _canvas()
    color = RED if recording else FG
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
    p.setPen(_pen(ACCENT, 2.4))
    p.drawLine(QPointF(3, 6), QPointF(21, 6))
    p.setPen(_pen(FG, 1.6))
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
    p.setPen(_pen(ACCENT2, 1.4))
    p.setBrush(ACCENT2)
    p.drawPolygon(QPolygonF(pts))
    return _done(px, p)


def question() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(ACCENT, 1.6))
    p.drawEllipse(QRectF(2.5, 2.5, 19, 19))
    f = QFont()
    f.setPointSize(13)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(2.5, 2.5, 19, 19), Qt.AlignCenter, "?")
    return _done(px, p)


def image() -> QIcon:
    px, p = _canvas()
    p.setPen(_pen(FG, 1.6))
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(2.5, 4.5, 19, 15), 2, 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#4caf50"))
    p.drawPolygon(QPolygonF([QPointF(4, 18), QPointF(10, 10), QPointF(14, 15),
                             QPointF(16, 13), QPointF(20, 18)]))
    p.setBrush(ACCENT2)
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


def export_pdf() -> QIcon:
    return _badge("PDF", RED)


def export_tex() -> QIcon:
    return _badge("TEX", ACCENT)


def app_icon() -> QIcon:
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
    p.setPen(_pen(QColor("white"), 4))
    for y in (22, 32, 42):
        p.drawLine(QPointF(16, y), QPointF(48 if y < 42 else 36, y))
    p.setPen(Qt.NoPen)
    p.setBrush(RED)
    p.drawEllipse(QRectF(40, 38, 14, 14))
    p.end()
    return QIcon(px)
