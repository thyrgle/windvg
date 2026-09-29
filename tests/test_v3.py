"""v3 constructs: point offsets, polar points, defs/use, stroke markers."""

import math

import pytest

import windvg as wv
import windvg.document as wvd
from windvg.document import (
    BetweenPoint,
    Document,
    Marker,
    Node,
    PolarPoint,
    SegmentPoint,
    UseSpec,
)


def make_doc():
    doc = Document(200.0, 200.0)
    doc.define("tooth", wvd.PolySpec(
        closed=True,
        points=((-6.0, -2.0), (6.0, -2.0), (9.0, -15.0), (-9.0, -15.0)),
    ))
    doc.fill("t1", UseSpec("tooth"), wv.rgb(0.2, 0.3, 0.4))
    doc.fill("g", wv.Circle((100.0, 100.0), 40.0), wv.rgb(0, 0, 0), visible=False)
    return doc


def ops_of(doc):
    return doc.resolve_to_json()


def test_use_expands_def():
    doc = make_doc()
    ops = ops_of(doc)
    assert ops[0]["shape"]["kind"] == "polygon"
    assert len(ops[0]["shape"]["points"]) == 4


def test_use_unknown_def_is_error():
    doc = make_doc()
    doc.fill("bad", UseSpec("nope"), wv.RED)
    with pytest.raises(ValueError, match="unknown def"):
        doc.resolve()


def test_def_cycle_is_error():
    doc = make_doc()
    doc.define("a", wvd.UseSpec("b"))
    doc.define("b", wvd.UseSpec("a"))
    doc.fill("u", UseSpec("a"), wv.RED)
    with pytest.raises(ValueError, match="cyclic"):
        doc.resolve()


def test_anchor_offset_applies_after_resolution():
    doc = make_doc()
    # 25% cw of the r=40 circle = bottom point (100, 140)
    doc.fill("off", wvd.CircleSpec(
        wvd.AnchorPoint("g", pct=25.0, offset=(10.0, 0.0)), 4.0), wv.RED)
    c = ops_of(doc)[1]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((110.0, 140.0))


def test_between_offset_applies_to_blend():
    doc = make_doc()
    doc.fill("b", wvd.CircleSpec(
        BetweenPoint((0.0, 0.0), (20.0, 10.0), 50.0, offset=(5.0, 5.0)), 3.0),
        wv.RED)
    c = ops_of(doc)[1]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((15.0, 10.0))


def test_polar_point_resolves():
    doc = make_doc()
    doc.fill("p", wvd.CircleSpec(
        PolarPoint((100.0, 100.0), 40.0, 30.0), 5.0), wv.RED)
    c = ops_of(doc)[1]["shape"]["center"]
    assert c[0] == pytest.approx(100.0 + 40.0 * math.cos(math.radians(30.0)))
    assert c[1] == pytest.approx(100.0 + 40.0 * math.sin(math.radians(30.0)))


def test_polar_center_can_be_anchor():
    doc = make_doc()
    doc.fill("p", wvd.CircleSpec(
        PolarPoint(wvd.AnchorPoint("g", pct=0.0), 10.0, 0.0), 3.0), wv.RED)
    c = ops_of(doc)[1]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((150.0, 100.0))


def test_segment_point_resolves_midpoint():
    doc = make_doc()
    doc.stroke("rail", wvd.PolySpec(
        closed=False, points=((80.0, 80.0), (120.0, 80.0))), wv.rgb(0, 0, 0))
    doc.fill("s", wvd.CircleSpec(SegmentPoint("rail", 0, 50.0), 3.0), wv.RED)
    c = ops_of(doc)[2]["shape"]["center"]
    assert (c[0], c[1]) == pytest.approx((100.0, 80.0))


def test_marker_triangle_bakes_polygon():
    doc = make_doc()
    doc.stroke("tie", wvd.PolySpec(
        closed=False, points=((100.0, 60.0), (100.0, 140.0))),
        wv.rgb(0, 0, 0), 2.0,
        markers=[Marker("end", "triangle", 10.0)])
    node = doc.nodes[-1]
    ops = doc.resolve_to_json()
    fills = [o for o in ops if o["op"] == "fill" and o["id"] == node.id]
    assert len(fills) == 1
    pts = fills[0]["shape"]["points"]
    # tip at the track end (100, 140); tangent (0,1), normal (1,0)
    assert pts[0] == pytest.approx([100.0, 140.0])
    assert pts[1] == pytest.approx([104.0, 130.0])   # P − t·s + n·0.4s
    assert pts[2] == pytest.approx([96.0, 130.0])    # P − t·s − n·0.4s


def test_marker_both_and_bar():
    doc = make_doc()
    doc.stroke("tie", wvd.PolySpec(
        closed=False, points=((100.0, 60.0), (100.0, 140.0))),
        wv.rgb(0, 0, 0), 2.0,
        markers=[Marker("both", "bar", 10.0)])
    node = doc.nodes[-1]
    ops = doc.resolve_to_json()
    fills = [o for o in ops if o["op"] == "fill" and o["id"] == node.id]
    assert len(fills) == 2  # start + end bars
    for f in fills:
        assert len(f["shape"]["points"]) == 4


def test_marker_on_fill_node_is_error():
    doc = make_doc()
    node = Node(id="nx", name="bad", op="fill", visible=True,
                shape=wvd.CircleSpec((10.0, 10.0), 4.0),
                paint=wv.RED, stroke_width=1.0, outline_paint=None,
                markers=[Marker("end", "triangle", 8.0)])
    doc.nodes.append(node)
    with pytest.raises(ValueError):
        doc.resolve()


def test_dicts_and_code_round_trip():
    doc = make_doc()
    doc.fill("t2", wvd.TransformSpec(
        (1.0, 0.0, 0.0, 1.0, 30.0, 0.0), UseSpec("tooth")), wv.rgb(0.2, 0.3, 0.4))
    doc.fill("off", wvd.CircleSpec(
        wvd.AnchorPoint("g", pct=25.0, offset=(10.0, 0.0)), 4.0), wv.RED)
    doc.fill("pol", wvd.CircleSpec(
        PolarPoint(wvd.AnchorPoint("g", pct=0.0), 10.0, 0.0), 3.0), wv.RED)
    doc.stroke(
        "tie",
        wvd.PolySpec(
            closed=False,
            points=(wvd.AnchorPoint("g", pct=0.0), wvd.AnchorPoint("g", pct=25.0)),
        ),
        wv.rgb(0, 0, 0),
        2.0,
        markers=[Marker("end", "triangle", 10.0)],
    )
    d = doc.to_dict()
    assert Document.from_dict(d).to_dict() == d
    assert Document.from_code(doc.generate_code()).to_dict() == d
