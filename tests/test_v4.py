"""v4 constructs: the text node (fidelity tier B, spec §7.19)."""

import pytest

import windvg as wv
from windvg.document import Document, TextSpec
from windvg.shapes import Circle
from windvg.textfont import measure


def make_doc():
    doc = Document(240.0, 120.0)
    doc.fill("dot", Circle((40, 60), 30), wv.rgb(0.2, 0.4, 0.8))
    doc.text("title", (80, 40), "Hi", 16.0)
    doc.text("mid", (200, 40), "Hi", 16.0, anchor="middle")
    doc.text("end", (200, 80), "Hi", 16.0, anchor="end")
    return doc


def test_text_builder_and_roundtrip():
    doc = make_doc()
    node = doc.nodes[1]
    assert node.op == "text"
    assert isinstance(node.shape, TextSpec)
    assert node.shape.content == "Hi"
    d = node.to_dict()
    assert d["shape"]["kind"] == "text"
    assert d["shape"]["anchor"] == "start"
    doc2 = Document.from_dict(doc.to_dict())
    assert doc2.nodes[1].shape == node.shape


def test_resolve_metadata():
    ops = make_doc().resolve_to_json()
    t = ops[1]
    assert t["op"] == "text"
    assert t["content"] == "Hi"
    assert t["at"] == [80, 40]
    assert t["size"] == 16.0
    assert t["anchor"] == "start"
    assert t["width"] == pytest.approx(measure("Hi", 16.0))
    # middle/end keep the raw at; the pen origin shifts in the export
    assert ops[2]["at"] == [200, 40]
    assert ops[3]["anchor"] == "end"


def _fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def test_anchors_in_svg():
    svg = make_doc().resolve().to_svg()
    w = measure("Hi", 16.0)
    assert f'x="{_fmt(80)}"' in svg and 'text-anchor="start"' in svg
    assert f'x="{_fmt(200 - w / 2)}"' in svg and 'text-anchor="middle"' in svg
    assert f'x="{_fmt(200 - w)}"' in svg and 'text-anchor="end"' in svg


def test_svg_golden_exact():
    svg = make_doc().resolve().to_svg()
    assert svg == (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120"'
        ' viewBox="0 0 240 120">\n'
        '  <circle cx="40" cy="60" r="30" fill="#3366CC"/>\n'
        '  <text x="80" y="40" font-family="Noto Sans" font-size="16"'
        ' text-anchor="start" fill="#000000">Hi</text>\n'
        '  <text x="192.008" y="40" font-family="Noto Sans" font-size="16"'
        ' text-anchor="middle" fill="#000000">Hi</text>\n'
        '  <text x="184.016" y="80" font-family="Noto Sans" font-size="16"'
        ' text-anchor="end" fill="#000000">Hi</text>\n'
        "</svg>\n"
    )


def test_tinyvg_fails_by_default_drop_text_opt_in():
    scene = make_doc().resolve()
    with pytest.raises(ValueError, match="tier B"):
        scene.to_tinyvg()
    data = scene.to_tinyvg(drop_text=True)
    assert data[:2] == b"rV"


def test_baked_outlines():
    scene = make_doc().resolve()
    tops = [o for o in scene.ops if type(o).__name__ == "TextOp"]
    assert len(tops) == 3
    for op in tops:
        assert op.shapes, "glyph baking produced no contours"
        lo, hi = op.shapes[0].bbox()
        assert hi.y - lo.y > op.size * 0.5


def test_escapes_roundtrip():
    doc = Document(100.0, 100.0)
    doc.text("q", (10, 20), 'say "hi" \\ ok', 12.0)
    doc2 = Document.from_dict(doc.to_dict())
    assert doc2.nodes[0].shape.content == 'say "hi" \\ ok'
    svg = doc.resolve().to_svg()
    assert "say &quot;" not in svg  # we escape &, <, > only; quotes are fine in text
    assert 'say "hi" \\ ok</text>' in svg


def test_unknown_font_rejected():
    doc = Document(100.0, 100.0)
    doc.text("t", (10, 20), "x", 12.0, font="comic")
    with pytest.raises(ValueError, match="unknown font"):
        doc.resolve_to_json()


def test_hidden_text_skipped():
    doc = make_doc()
    doc.text("ghost", (100, 100), "boo", 12.0, visible=False)
    ops = doc.resolve_to_json()
    assert all(o["op"] != "text" or o["content"] != "boo" for o in ops)
    svg = doc.resolve().to_svg()
    assert "boo" not in svg


def test_code_generation_roundtrip():
    doc = make_doc()
    doc2 = Document.from_code(doc.generate_code())
    assert doc2.nodes[1].shape.content == "Hi"
    assert doc2.nodes[3].shape.anchor == "end"
    assert doc2.resolve_to_json() == doc.resolve_to_json()
