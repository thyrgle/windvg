"""v2 constructs: TransformSpec, RectSpec, PieSpec, BetweenPoint."""


import pytest

import windvg as wv
import windvg.document as wvd
from windvg.document import (
    BetweenPoint,
    Document,
    PieSpec,
    RectSpec,
    TransformSpec,
)


def test_transform_bakes_on_resolve():
    doc = Document(200, 200)
    doc.fill("t", TransformSpec((0, 1, -1, 0, 150, 50), wvd.CircleSpec((0, 0), 30)), wv.RED)
    ops = doc.resolve_to_json()
    # a pure rotation is a similarity: the circle stays a circle
    assert ops[0]["shape"]["kind"] == "circle"
    c = ops[0]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((150, 50))


def test_rect_resolves_to_clockwise_polygon():
    doc = Document(100, 100)
    doc.fill("r", RectSpec((50, 50), 40, 20), wv.RED)
    pts = doc.resolve_to_json()[0]["shape"]["points"]
    assert [(p[0], p[1]) for p in pts] == [
        (30, 40), (70, 40), (70, 60), (30, 60),
    ]


def test_pie_and_chord_paths():
    doc = Document(200, 200)
    doc.fill("w", PieSpec((100, 100), 40, 0, 90), wv.RED)
    doc.fill("c", PieSpec((100, 100), 40, 0, 90, chord=True), wv.BLUE)
    wedge = doc.resolve_to_json()[0]["shape"]
    chord = doc.resolve_to_json()[1]["shape"]
    assert wedge["kind"] == "path" and chord["kind"] == "path"
    w0, c0 = wedge["subpaths"][0], chord["subpaths"][0]
    # wedge: arc + line to center + close = 3 instructions
    assert len(w0["instructions"]) == 3
    assert w0["instructions"][1]["cmd"] == "line"
    # chord: arc + close = 2 instructions
    assert len(c0["instructions"]) == 2


def test_between_resolves_and_extrapolates():
    doc = Document(200, 200)
    doc.fill(
        "m",
        wvd.CircleSpec(BetweenPoint((10, 10), (30, 30), 50), 5),
        wv.RED,
    )
    doc.fill(
        "e",
        wvd.CircleSpec(BetweenPoint((10, 10), (30, 30), 150), 5),
        wv.BLUE,
    )
    ops = doc.resolve_to_json()
    c = ops[0]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((20, 20))
    c = ops[1]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((40, 40))  # extrapolation


def test_between_with_anchor_operands():
    doc = Document(100, 100)
    doc.fill("g", wvd.CircleSpec((50, 50), 40), wv.RED)
    a = wvd.AnchorPoint("g", pct=0.0)
    b = wvd.AnchorPoint("g", pct=25.0)  # bottom of the circle: (50, 90)
    doc.fill("m", wvd.CircleSpec(BetweenPoint(a, b, 50.0), 3), wv.BLUE)
    c = doc.resolve_to_json()[1]["shape"]["center"]
    # 0% is the rightmost point (90,50); 25% cw is the bottom (50,90)
    assert (c[0], c[1]) == pytest.approx((70, 70))


def test_transform_group_reference_rotates():
    from windvg.ext.transform import Transform

    doc = Document(200, 200)
    t = Transform.rotate(90, (100, 100))
    doc.fill(
        "t",
        TransformSpec(
            (t.a, t.b, t.c, t.d, t.e, t.f),
            wvd.RectSpec((100, 100), 40, 20),
        ),
        wv.RED,
    )
    pts = doc.resolve_to_json()[0]["shape"]["points"]
    # rotating the wide rect by 90° about its center makes it tall
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert pytest.approx(max(xs) - min(xs)) == 20
    assert pytest.approx(max(ys) - min(ys)) == 40


def test_dicts_round_trip():
    doc = Document(200, 200)
    doc.fill("t", TransformSpec((0, 1, -1, 0, 150, 50), wvd.CircleSpec((0, 0), 30)), wv.RED)
    doc.fill("r", RectSpec((50, 150), 40, 20), wv.RED)
    doc.fill("p", PieSpec((150, 150), 30, 0, 90, chord=True), wv.RED)
    doc.fill("b", wvd.CircleSpec(BetweenPoint((10, 10), (30, 30), 50), 5), wv.RED)
    d = doc.to_dict()
    assert Document.from_dict(d).to_dict() == d
    assert Document.from_code(doc.generate_code()).to_dict() == d
