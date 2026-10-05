from khervenote.lists import nest, parse_item


def test_parse_item():
    assert parse_item("  - dot").text == "dot"
    assert parse_item("12) twelve").numbered
    assert parse_item("1.5 eV") is None
    assert parse_item("-dash") is None


def test_nest_uses_relative_indents():
    levels = [ln.level for ln in nest(["- a", "    - b", "        - c", "    - d", "- e"])]
    assert levels == [0, 1, 2, 1, 0]
    assert [ln.level for ln in nest(["\t- a", "\t\t- b"])] == [0, 1]


def test_nest_caps_depth():
    lines = [" " * (2 * i) + "- x" for i in range(6)]
    assert max(ln.level for ln in nest(lines)) == 3
