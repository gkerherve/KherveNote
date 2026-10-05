import pytest

from khervenote import compiler
from khervenote.model import Note
from khervenote.serializer import _TIGHT, escape, format_time, text_to_latex, to_latex


def _note():
    n = Note.new()
    n.meta.title, n.meta.speaker, n.meta.place = "Surface science", "Dr A", "Imperial"
    n.add_block("typed", "Opening remarks")
    n.add_section("XPS basics", t=60)
    n.add_block("typed", "- binding energy\n  1. core levels\n  2. valence\n- work function")
    n.add_block("important", "Shirley background", t=75)
    n.add_block("question", "Why 1486.6 eV?")
    n.add_block("transcript", "so the photon comes in", t=3725)
    return n


def test_escape():
    assert escape(r"50% & $5 #1 a_b {x} ~ ^ \ ") == (
        r"50\% \& \$5 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} "
        r"\textbackslash{} ")


def test_format_time():
    assert format_time(None) == ""
    assert format_time(75.9) == "01:15"
    assert format_time(3725) == "1:02:05"


def test_text_to_latex_paragraphs_and_lines():
    assert text_to_latex("one\ntwo\n\nthree") == "one\\newline\ntwo\n\nthree"


def test_bullets_inside_a_paragraph():
    out = text_to_latex("intro\n- a\n* b\nafter")
    assert out == ("intro\n\\begin{itemize}" + _TIGHT + "\n  \\item a\n  \\item b\n"
                   "\\end{itemize}\nafter")


def test_nested_numbered_and_bullet_items():
    out = text_to_latex("1. one\n   - dot\n     2) deeper\n2. two\n    still two")
    assert out == "\n".join([
        "\\begin{enumerate}" + _TIGHT,
        "  \\item one",
        "  \\begin{itemize}" + _TIGHT,
        "    \\item dot",
        "    \\begin{enumerate}" + _TIGHT,
        "      \\item deeper",
        "    \\end{enumerate}",
        "  \\end{itemize}",
        "  \\item two\\newline still two",
        "\\end{enumerate}"])


def test_switching_kind_at_the_same_level_starts_a_new_list():
    out = text_to_latex("- a\n1. b")
    assert out.count("\\begin{itemize}") == 1 and out.count("\\begin{enumerate}") == 1
    assert out.index("\\end{itemize}") < out.index("\\begin{enumerate}")


def test_numbers_in_prose_are_not_items():
    assert "itemize" not in text_to_latex("1.5 eV is the shift")
    assert "enumerate" not in text_to_latex("In 2024 we saw")


def test_untitled_first_section_has_no_heading():
    tex = to_latex(_note())
    assert tex.count(r"\section{") == 1
    assert r"\section{XPS basics}" in tex
    assert "Opening remarks" in tex


def test_later_untitled_section_gets_a_heading():
    n = Note.new()
    n.add_section("")
    n.add_block("typed", "x")
    assert r"\section{Untitled section}" in to_latex(n)


def test_empty_untitled_section_is_skipped():
    n = Note.new()
    n.add_section("")
    n.add_section("Kept")
    tex = to_latex(n)
    assert "Untitled section" not in tex and r"\section{Kept}" in tex


def test_blocks():
    tex = to_latex(_note())
    assert r"\knotekey{Shirley background}" in tex
    assert r"\knotequestion{Why 1486.6 eV?}" in tex
    # transcript always carries its time, typed blocks only on request
    assert r"\knotetime{1:02:05}so the photon" in tex
    assert r"\knotetime{01:15}" not in tex
    assert r"\knotekey{\knotetime{01:15}Shirley" in to_latex(_note(), show_times=True)


def test_continuous_and_paged_preambles():
    cont = to_latex(_note(), "continuous")
    paged = to_latex(_note(), "paged")
    assert "paperheight=5000mm" in cont and r"\knote@flush" in cont
    assert "a4paper" in paged and r"\knote@flush" not in paged
    assert cont.count(r"\begin{knotechunk}") == 2


def test_summary_box():
    n = _note()
    n.summary = "Key ideas"
    assert r"\knotesummary{Key ideas}" in to_latex(n)


def test_missing_image_becomes_placeholder(tmp_path):
    n = Note.new()
    n.add_block("image", "Slide", path="assets/gone.png")
    tex = to_latex(n, asset_dir=tmp_path)
    assert "missing image" in tex and r"\captionof{figure}{Slide}" in tex
    assert r"\includegraphics" in to_latex(n)


needs_tectonic = pytest.mark.skipif(compiler.find_tectonic() is None,
                                    reason="tectonic not installed")


@needs_tectonic
def test_continuous_pdf_is_one_page_fitted_to_content(tmp_path):
    res = compiler.compile_tex(to_latex(_note()), tmp_path)
    assert res.ok, res.log
    heights = compiler.pdf_page_heights_mm(res.pdf_path)
    assert len(heights) == 1
    assert 60 < heights[0] < 250


@needs_tectonic
def test_continuous_pdf_splits_between_sections_past_the_limit(tmp_path):
    n = _note()
    for i in range(3):
        n.add_section(f"Extra {i}")
        n.add_block("typed", "words " * 200)
    res = compiler.compile_tex(to_latex(n, limit_pt=300), tmp_path)
    assert res.ok, res.log
    import pymupdf
    with pymupdf.open(res.pdf_path) as doc:
        assert len(doc) > 1
        for page in doc:
            # every page starts with a section (or the title)
            first = page.get_text("blocks")[0][4]
            assert "Extra" in first or "XPS" in first or "Surface" in first
        assert [t[1] for t in doc.get_toc()][:2] == ["1 XPS basics", "2 Extra 0"]


@needs_tectonic
def test_paged_pdf_is_a4(tmp_path):
    res = compiler.compile_tex(to_latex(_note(), "paged"), tmp_path)
    assert res.ok, res.log
    assert [round(h) for h in compiler.pdf_page_heights_mm(res.pdf_path)] == [297]


@needs_tectonic
def test_one_section_taller_than_the_limit_still_compiles(tmp_path):
    n = Note.new()
    n.add_section("Long")
    n.add_block("typed", "\n\n".join(["words " * 80] * 6))
    res = compiler.compile_tex(to_latex(n, limit_pt=200), tmp_path)
    assert res.ok, res.log
    assert len(compiler.pdf_page_heights_mm(res.pdf_path)) >= 2


def test_item_blocks_become_one_nested_list():
    n = Note.new()
    n.add_block("item", "one", numbered=True)
    n.add_block("item", "sub", level=1, numbered=True)
    n.add_block("item", "dot", level=1)
    n.add_block("typed", "after")
    tex = to_latex(n)
    assert tex.count(r"\begin{enumerate}") == 2 and tex.count(r"\begin{itemize}") == 1
    assert tex.index(r"\item one") < tex.index(r"\item sub") < tex.index(r"\item dot")
    assert tex.index(r"\end{enumerate}") < tex.index("after")


def test_subsection_headings():
    n = Note.new()
    n.add_block("heading", "Part A", level=2)
    n.add_block("heading", "Detail", level=3)
    n.add_block("heading", "  ", level=2)
    tex = to_latex(n)
    assert r"\subsection{Part A}" in tex and r"\subsubsection{Detail}" in tex
    assert tex.count("subsection{") == 2


def test_rich_marks():
    from khervenote.serializer import rich_to_latex
    assert rich_to_latex("a bold_word end", [[2, 9, "b"], [7, 4, "i"]]) == (
        r"a \textbf{bold\_}\textit{\textbf{word}} end")
    assert rich_to_latex("x\ny", []) == "x\\newline\ny"
    n = Note.new()
    n.add_block("typed", "- not a list", marks=[[2, 3, "u"]])
    assert r"\underline{not}" in to_latex(n) and "itemize" not in to_latex(n)
