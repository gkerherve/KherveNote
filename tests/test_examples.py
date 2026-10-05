import pytest

from khervenote import compiler, examples
from khervenote.knote_file import load_knote
from khervenote.serializer import to_latex


@pytest.mark.parametrize("ex", examples.EXAMPLES, ids=lambda e: e.title[:30])
def test_example_is_a_full_note(ex):
    n = examples.build(ex)
    assert n.meta.title == ex.title and n.meta.started
    assert len(n.sections) >= 3 and all(s.title for s in n.sections)
    kinds = {b.kind for s in n.sections for b in s.blocks}
    assert {"typed", "item", "important", "question"} <= kinds
    assert len(n.transcript) >= 6
    times = [b.t for s in n.sections for b in s.blocks]
    assert times == sorted(times)                     # written in order
    assert "$" in n.plain_text()                      # there is maths in it


def test_install_writes_each_once_and_keeps_edits(tmp_path):
    paths = examples.install(tmp_path)
    assert len(paths) == len(examples.EXAMPLES) and all(p.exists() for p in paths)
    assert all(p.parent.name == "Examples" for p in paths)
    paths[0].write_bytes(b"edited")
    examples.install(tmp_path)
    assert paths[0].read_bytes() == b"edited"
    note = load_knote(paths[1], tmp_path / "w")
    assert note.transcript and note.sections


needs_tectonic = pytest.mark.skipif(compiler.find_tectonic() is None,
                                    reason="tectonic not installed")


@needs_tectonic
@pytest.mark.parametrize("ex", examples.EXAMPLES, ids=lambda e: e.title[:30])
def test_example_compiles_to_pdf(ex, tmp_path):
    res = compiler.compile_tex(to_latex(examples.build(ex), transcript=True), tmp_path)
    assert res.ok, res.error or res.log[-2000:]
    assert "Missing character" not in res.log, [l for l in res.log.splitlines()
                                                 if "Missing character" in l][:5]
