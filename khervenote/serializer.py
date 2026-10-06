# KherveNote — LaTeX serializer
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
r"""Note model → LaTeX.

Two layouts come from the same body:

``continuous``
    The whole note on one PDF page exactly as tall as its content.  Each
    section is typeset into a box (``knotechunk``); boxes are stacked and
    the page height is set from the stack before it is shipped out.  PDF
    viewers cap a page near 200 in (5.08 m), so when the next section
    would push the stack past ``\knote@limit`` the stack is shipped as
    one tall page and a new one starts — the note then breaks only
    between sections, never inside one.  A single section taller than
    the limit falls back to ordinary page breaking on maximum-height
    pages.

    Inside a box TeX cannot float or place footnotes, so the body uses
    neither: figures are ``\captionof`` in place and there are no
    footnotes.

``paged``
    Ordinary A4 pages for printing; ``knotechunk`` does nothing.

The output is one self-contained ``.tex`` that only needs the note's
``assets/`` folder next to it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .lists import ListLine, is_list_line, nest
from .model import Block, Note, Section

#: geometry's paper height in continuous mode, below the PDF viewer cap.
CONTINUOUS_PAPER_MM = 5000
MARGIN_MM = 20
#: Tallest stack of sections put on one page.
CONTINUOUS_LIMIT_MM = CONTINUOUS_PAPER_MM - 2 * MARGIN_MM - 10

_SPECIALS = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
}
_SPECIALS_RE = re.compile(r"[&%$#_{}~^\\]")
_TIGHT = r"\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}"


#: Characters the text font (Latin Modern) has no glyph for — they would
#: come out blank — and the maths command that draws them.
_SYMBOLS = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon",
    "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta", "ι": r"\iota", "κ": r"\kappa",
    "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho",
    "σ": r"\sigma", "τ": r"\tau", "υ": r"\upsilon", "φ": r"\phi", "χ": r"\chi",
    "ψ": r"\psi", "ω": r"\omega", "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta",
    "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi",
    "Ψ": r"\Psi", "Ω": r"\Omega", "∆": r"\Delta", "≈": r"\approx", "≤": r"\leq",
    "≥": r"\geq", "≠": r"\neq", "→": r"\rightarrow", "←": r"\leftarrow",
    "↔": r"\leftrightarrow", "⇒": r"\Rightarrow", "⇌": r"\rightleftharpoons",
    "∞": r"\infty", "∝": r"\propto", "∂": r"\partial", "∇": r"\nabla", "∫": r"\int",
    "∑": r"\sum", "√": r"\surd", "·": r"\cdot", "∼": r"\sim", "≡": r"\equiv",
    "⊥": r"\perp", "∥": r"\parallel", "ℏ": r"\hbar", "−": "-",
}
_SYMBOLS_RE = re.compile("|".join(map(re.escape, _SYMBOLS)))


_SUB = dict(zip("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ", "0123456789+-=()aeoxhklmnpst"))
_SUP = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ", "0123456789+-=()ni"))
_SUB_RE = re.compile("[" + "".join(_SUB) + "]+")
_SUP_RE = re.compile("[" + "".join(_SUP) + "]+")


def escape(text: str) -> str:
    """Make plain text safe to typeset.  Unicode sub- and superscripts
    (H₂O, Al³⁺, cm⁻¹) become real ones: the text font has no glyphs for
    most of them."""
    out = _SPECIALS_RE.sub(lambda m: _SPECIALS[m.group()], text)
    out = _SUB_RE.sub(lambda m: r"\textsubscript{" + "".join(_SUB[c] for c in m.group())
                      + "}", out)
    out = _SUP_RE.sub(lambda m: r"\textsuperscript{" + "".join(_SUP[c] for c in m.group())
                      + "}", out)
    return _SYMBOLS_RE.sub(lambda m: r"\ensuremath{" + _SYMBOLS[m.group()] + "}", out)


#: Maths as people type it in notes, LaTeX-style: $$…$$ and \[…\] on their
#: own, $…$ and \(…\) in a sentence.  A $ only opens maths when followed by
#: a non-space and only closes it after a non-space and before a non-digit,
#: so "it costs $5 and $10" stays text.
_MATH_RE = re.compile(
    r"\$\$(?P<dd>.+?)\$\$"
    r"|\\\[(?P<db>.+?)\\\]"
    r"|\\\((?P<ib>.+?)\\\)"
    r"|\$(?P<id>[^\s$](?:[^$]*?[^\s$])?)\$(?!\d)", re.DOTALL)


_MATH_ONLY = {"°": r"^{\circ}", "×": r"\times ", "±": r"\pm ", "µ": r"\mu "}


def _math(src: str) -> str:
    # Greek letters and symbols typed straight into maths still need
    # commands — the maths fonts have none of them.
    for ch, cmd in _MATH_ONLY.items():
        src = src.replace(ch, cmd)
    return _SYMBOLS_RE.sub(lambda m: _SYMBOLS[m.group()] + " ", src)


def tex(text: str) -> str:
    """Text with any maths in it kept as maths and the rest escaped."""
    out, pos = [], 0
    for m in _MATH_RE.finditer(text):
        out.append(escape(text[pos:m.start()]))
        display = m.group("dd") or m.group("db")
        if display is not None:
            out.append(r"\[" + _math(display.strip()) + r"\]")
        else:
            out.append("$" + _math((m.group("ib") or m.group("id")).strip()) + "$")
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out)


def format_time(t: Optional[float]) -> str:
    if t is None:
        return ""
    s = int(t)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _render_list(lines: list[ListLine]) -> str:
    """Nested itemize/enumerate from lines whose text is already LaTeX."""
    out: list[str] = []
    stack: list[str] = []
    for ln in lines:
        if not ln.item:
            out[-1] += r"\newline " + ln.text
            continue
        env = "enumerate" if ln.numbered else "itemize"
        level = min(ln.level, len(stack))
        while stack and (len(stack) > level + 1
                         or (len(stack) == level + 1 and stack[-1] != env)):
            out.append("  " * (len(stack) - 1) + "\\end{%s}" % stack.pop())
        if len(stack) == level:
            out.append("  " * level + "\\begin{%s}" % env + _TIGHT)
            stack.append(env)
        out.append("  " * len(stack) + r"\item " + ln.text)
    while stack:
        out.append("  " * (len(stack) - 1) + "\\end{%s}" % stack.pop())
    return "\n".join(out)


def _list_latex(lines: list[str]) -> str:
    return _render_list([ListLine(ln.level, ln.numbered, tex(ln.text), ln.item)
                         for ln in nest(lines)])


_MARK_MACROS = {"b": r"\textbf{%s}", "i": r"\textit{%s}", "u": r"\underline{%s}"}


def rich_to_latex(text: str, marks: list) -> str:
    """Text with inline bold / italic / underline spans; newlines inside
    the text are line breaks."""
    def plain(seg: str) -> str:
        return "\\newline\n".join(tex(x) for x in seg.split("\n"))
    if not marks:
        return plain(text)
    cuts = sorted({0, len(text)} | {max(0, min(len(text), c)) for m in marks
                                    for c in (m[0], m[0] + m[1])})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        seg = plain(text[a:b])
        for style in sorted({m[2] for m in marks if m[0] <= a and m[0] + m[1] >= b}):
            seg = _MARK_MACROS[style] % seg
        out.append(seg)
    return "".join(out)


def text_to_latex(text: str) -> str:
    """Blank lines separate paragraphs, single newlines are kept as line
    breaks, and bullet / numbered items (see ``lists``) become nested
    itemize / enumerate lists — the way people type notes."""
    out = []
    for para in re.split(r"\n\s*\n", text.strip("\n")):
        parts: list[str] = []
        lines: list[str] = []
        items: list[str] = []
        for ln in [ln.rstrip() for ln in para.splitlines() if ln.strip()] + [""]:
            listed = bool(ln) and is_list_line(ln, bool(items))
            if lines and (listed or not ln):
                parts.append("\\newline\n".join(lines))
                lines = []
            if items and not listed:
                parts.append(_list_latex(items))
                items = []
            if listed:
                items.append(ln)
            elif ln:
                lines.append(tex(ln.strip()))
        if parts:
            out.append("\n".join(parts))
    return "\n\n".join(out)


def _preamble(note: Note, layout: str, limit_pt: Optional[float]) -> str:
    m = note.meta
    if layout == "continuous":
        geometry = (f"paperwidth=210mm,paperheight={CONTINUOUS_PAPER_MM}mm,"
                    f"margin={MARGIN_MM}mm")
        limit = (f"{limit_pt:.2f}pt" if limit_pt is not None
                 else f"{CONTINUOUS_LIMIT_MM}mm")
        chunks = rf"""\makeatletter
\newdimen\knote@limit \knote@limit={limit}
\newbox\knote@page \newbox\knote@chunk
\def\knote@ht#1{{\dimexpr\ht#1+\dp#1\relax}}
\def\knote@setheight#1{{\global\pdfpageheight=#1\relax
  \special{{pdf:pagesize width \the\paperwidth\space height \the\pdfpageheight}}}}
\def\knote@flush{{\ifvoid\knote@page\else
  \knote@setheight{{\dimexpr\knote@ht\knote@page+{2 * MARGIN_MM}mm+2mm\relax}}%
  \box\knote@page\par\clearpage\global\pdfpageheight=\paperheight\fi}}
\newenvironment{{knotechunk}}
  {{\par\setbox\knote@chunk=\vbox\bgroup\hsize=\textwidth\linewidth=\textwidth}}
  {{\par\egroup
   \ifdim\knote@ht\knote@chunk>\knote@limit
     \knote@flush\unvbox\knote@chunk\par\clearpage
   \else\ifvoid\knote@page
     \global\setbox\knote@page=\vbox{{\unvbox\knote@chunk}}%
   \else\ifdim\dimexpr\knote@ht\knote@page+\knote@ht\knote@chunk\relax>\knote@limit
     \knote@flush\global\setbox\knote@page=\vbox{{\unvbox\knote@chunk}}%
   \else
     \global\setbox\knote@page=\vbox{{\unvbox\knote@page\unvbox\knote@chunk}}%
   \fi\fi\fi}}
\AtEndDocument{{\knote@flush}}
\makeatother
\pagestyle{{empty}}"""
    else:
        geometry = f"a4paper,margin={MARGIN_MM}mm"
        chunks = "\\newenvironment{knotechunk}{}{}\n\\pagestyle{plain}"

    return rf"""\documentclass[11pt]{{article}}
\usepackage[{geometry}]{{geometry}}
\usepackage{{amsmath,amssymb,xcolor,graphicx}}
\usepackage[hypcap=false]{{caption}}
\usepackage[hidelinks,bookmarksnumbered,bookmarksopen]{{hyperref}}
\hypersetup{{pdftitle={{{escape(m.title)}}},pdfauthor={{{escape(m.speaker)}}},
  pdfcreator={{KherveNote}}}}
\renewcommand\labelitemii{{\textbullet}}
\renewcommand\labelitemiii{{\textbullet}}
\renewcommand\labelitemiv{{\textbullet}}
\renewcommand\labelenumii{{\arabic{{enumi}}.\arabic{{enumii}}.}}
\renewcommand\labelenumiii{{\arabic{{enumi}}.\arabic{{enumii}}.\arabic{{enumiii}}.}}
\renewcommand\labelenumiv{{\arabic{{enumi}}.\arabic{{enumii}}.\arabic{{enumiii}}.\arabic{{enumiv}}.}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.6em}}
\definecolor{{knoteaccent}}{{HTML}}{{1A6DD8}}
\definecolor{{knotemuted}}{{HTML}}{{6B6B6B}}
\definecolor{{knotekey}}{{HTML}}{{D96B00}}
\newcommand\knotetime[1]{{\leavevmode\llap{{\color{{knotemuted}}\scriptsize #1\hspace{{1em}}}}}}
\newcommand\knotekey[2][]{{\par\noindent#1\colorbox{{knotekey!12}}{{\parbox{{\dimexpr\linewidth-2\fboxsep}}{{%
  \textbf{{\color{{knotekey}}$\star$ Key point.}} #2}}}}\par}}
\newcommand\knotequestion[2][]{{\par\noindent#1{{\color{{knoteaccent}}\textbf{{?}}}}~\emph{{#2}}\par}}
\newenvironment{{knotetranscript}}{{\par\color{{knotemuted}}\small}}{{\par}}
\newcommand\knotesummary[1]{{\par\noindent\fcolorbox{{knoteaccent}}{{knoteaccent!6}}{{%
  \parbox{{\dimexpr\linewidth-2\fboxsep-2\fboxrule}}{{\textbf{{Summary}}\par #1}}}}\par}}
{chunks}
"""


def _title_band(note: Note) -> str:
    m = note.meta
    left = escape(m.speaker)
    right = " \\textperiodcentered{} ".join(escape(x) for x in (m.date, m.place) if x)
    parts = [r"{\color{knoteaccent}\rule{\linewidth}{1.5pt}}\par",
             r"{\LARGE\bfseries " + (tex(m.title) or "Notes") + r"}\par"]
    if left or right:
        parts.append(r"{\large " + left + r"}\hfill{\color{knotemuted}" + right + r"}\par")
    parts.append(r"{\color{knoteaccent}\rule{\linewidth}{0.6pt}}\par")
    if note.summary.strip():
        parts.append(r"\knotesummary{" + text_to_latex(note.summary) + "}")
    return "\n".join(parts)


def _image(block: Block, asset_dir: Optional[Path]) -> str:
    if asset_dir is not None and not (asset_dir / block.path).is_file():
        body = (r"\fbox{\texttt{\small [missing image: "
                + escape(block.path) + r"]}}")
    else:
        body = (r"\includegraphics[width=0.85\linewidth,height=110mm,"
                r"keepaspectratio]{" + block.path + "}")
    cap = (r"\captionof{figure}{" + tex(block.text.strip()) + "}"
           if block.text.strip() else "")
    return "\\begin{center}\n" + body + "\n" + cap + "\n\\end{center}"


def _body(block: Block) -> str:
    # Marks come from the editor; unmarked text may still use the typed
    # list syntax ("- ", "1. ").
    return rich_to_latex(block.text, block.marks) if block.marks else text_to_latex(block.text)


def _block(block: Block, show_times: bool, asset_dir: Optional[Path]) -> str:
    stamp = format_time(block.t)
    lead = (r"\knotetime{" + stamp + "}") if stamp and (
        show_times or block.kind == "transcript") else ""
    if block.kind == "image":
        return _image(block, asset_dir) if block.path else ""
    if block.kind == "attachment":
        return r"{\color{knotemuted}\textbf{Attached document:} " + escape(block.text) + "}"
    if block.kind == "heading":
        title = tex(block.text.strip())
        if not title:
            return ""
        return ("\\subsubsection{" if block.level >= 3 else "\\subsection{") + title + "}"
    body = _body(block)
    if not body:
        return ""
    # The time goes in the optional argument, before the box / the "?",
    # so it lands in the margin and not over the label.
    if block.kind == "important":
        return (r"\knotekey[" + lead + "]{" if lead else r"\knotekey{") + body + "}"
    if block.kind == "question":
        return (r"\knotequestion[" + lead + "]{" if lead else r"\knotequestion{") + body + "}"
    if block.kind == "transcript":
        return "\\begin{knotetranscript}\n" + lead + body + "\n\\end{knotetranscript}"
    return lead + body


def _blocks(blocks: list[Block], show_times: bool, asset_dir: Optional[Path]) -> list[str]:
    """Each block's LaTeX, with runs of list items merged into one list."""
    out: list[str] = []
    run: list[ListLine] = []
    for blk in blocks + [None]:
        if blk is not None and blk.kind == "item":
            if blk.text.strip():
                run.append(ListLine(blk.level, blk.numbered, rich_to_latex(blk.text, blk.marks)))
            continue
        if run:
            out.append(_render_list(run))
            run = []
        if blk is not None:
            tex = _block(blk, show_times, asset_dir)
            if tex:
                out.append(tex)
    return out


def _section(sec: Section, first: bool, show_times: bool,
             asset_dir: Optional[Path]) -> str:
    blocks = _blocks(sec.blocks, show_times, asset_dir)
    if not blocks and not sec.title.strip():
        # A "New section" pressed by mistake, never titled or filled.
        return ""
    parts = []
    if sec.title.strip() or not first:
        parts.append(r"\section{" + (tex(sec.title.strip())
                                     or "Untitled section") + "}")
    return "\n\n".join(parts + blocks)


def _transcript(note: Note) -> str:
    """The speech transcript as a last section, each stretch with the
    time it was said in the margin."""
    rows = [r"\knotetime{" + note.time_label(g.t) + "}" + tex(g.text.strip())
            for g in note.transcript if g.text.strip()]
    if not rows:
        return ""
    return ("\\section{What was said}\n\\begin{knotetranscript}\n"
            + "\n\n".join(rows) + "\n\\end{knotetranscript}")


def to_latex(note: Note, layout: Optional[str] = None, *,
             show_times: bool = False,
             transcript: bool = False,
             asset_dir: Optional[Path] = None,
             limit_pt: Optional[float] = None) -> str:
    """The complete ``.tex`` for *note*.

    *transcript* adds the speech transcript as a last section; *asset_dir*
    lets missing images become a visible placeholder instead of a failed
    compile; *limit_pt* overrides the continuous-page height cap (tests
    use it to force the multi-page fallback).
    """
    layout = layout or note.meta.layout
    chunks = []
    for i, sec in enumerate(note.sections):
        body = _section(sec, i == 0, show_times, asset_dir)
        if i == 0:
            body = _title_band(note) + ("\n\n" + body if body else "")
        if body:
            chunks.append("\\begin{knotechunk}\n" + body + "\n\\end{knotechunk}")
    if transcript and _transcript(note):
        chunks.append("\\begin{knotechunk}\n" + _transcript(note) + "\n\\end{knotechunk}")
    return (_preamble(note, layout, limit_pt) + "\\begin{document}\n"
            + "\n\n".join(chunks) + "\n\\end{document}\n")
