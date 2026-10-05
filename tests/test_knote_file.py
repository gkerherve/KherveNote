import zipfile

from khervenote.knote_file import load_knote, save_knote
from khervenote.model import Note


def test_save_and_load_with_assets(tmp_path):
    work = tmp_path / "work"
    (work / "assets").mkdir(parents=True)
    (work / "assets" / "slide.png").write_bytes(b"\x89PNG fake")
    n = Note.new()
    n.meta.title = "Électrochimie"
    n.add_block("image", "slide 3", path="assets/slide.png")
    path = tmp_path / "lecture.knote"
    save_knote(n, path, work)

    other = tmp_path / "other"
    back = load_knote(path, other)
    assert back.meta.title == "Électrochimie"
    assert (other / "assets" / "slide.png").read_bytes() == b"\x89PNG fake"
    assert not list(tmp_path.glob(".knote-*"))


def test_unreferenced_assets_are_not_saved(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "deleted.png").write_bytes(b"x")
    path = tmp_path / "n.knote"
    save_knote(Note.new(), path, tmp_path)
    assert zipfile.ZipFile(path).namelist() == ["note.json"]


def test_zip_slip_is_ignored(tmp_path):
    path = tmp_path / "evil.knote"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("note.json", '{"format": 1}')
        zf.writestr("../escaped.txt", "x")
    load_knote(path, tmp_path / "work")
    assert not (tmp_path / "escaped.txt").exists()
