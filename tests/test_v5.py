"""v5 constructs: tangent offsets on track-based point refs (spec §7.20)."""


import pytest

import windvg as wv
import windvg.document as wvd
from windvg.document import (
    AnchorPoint,
    Document,
    PolySpec,
    SegmentPoint,
)


def rim_doc():
    doc = Document(200.0, 200.0)
    doc.stroke("rim", wvd.CircleSpec((100.0, 100.0), 60.0), wv.BLACK, 1.0)
    return doc


def resolver(doc):
    return wvd._Resolver(doc)


def approx_pt(p, x, y, tol=1e-9):
    assert abs(p.x - x) < tol and abs(p.y - y) < tol, f"{p} != ({x}, {y})"


def test_tangent_runs_with_travel():
    r = resolver(rim_doc())
    # cw circle at 0%: point (160,100), travel = down
    p = r.resolve_point(rim_doc().anchor("rim", pct=0.0, tangent=20.0))
    approx_pt(p, 160.0, 120.0)


def test_deg90_is_the_normal():
    r = resolver(rim_doc())
    # walking down, right-hand side is west (toward the center)
    p = r.resolve_point(rim_doc().anchor("rim", pct=0.0, tangent=(20.0, 90.0)))
    approx_pt(p, 140.0, 100.0)


def test_deg180_reverses():
    r = resolver(rim_doc())
    p = r.resolve_point(rim_doc().anchor("rim", pct=0.0, tangent=(20.0, 180.0)))
    approx_pt(p, 160.0, 80.0)


def test_negative_length_faces_backward():
    r = resolver(rim_doc())
    p = r.resolve_point(rim_doc().anchor("rim", pct=0.0, tangent=-20.0))
    approx_pt(p, 160.0, 80.0)


def test_anchor_at_percent_tracks_local_frame():
    r = resolver(rim_doc())
    # 25% cw from (160,100) is the 6 o'clock point (100,160); travel = west
    p = r.resolve_point(rim_doc().anchor("rim", pct=25.0, tangent=10.0))
    approx_pt(p, 90.0, 160.0)
    # deg 90 from west rotates to north (right-hand side = outward here)
    q = r.resolve_point(rim_doc().anchor("rim", pct=25.0, tangent=(10.0, 90.0)))
    approx_pt(q, 100.0, 150.0)


def test_segment_ref_tangent():
    doc = Document(200.0, 200.0)
    doc.stroke(
        "rail",
        PolySpec(closed=False, points=((40.0, 40.0), (140.0, 40.0))),
        wv.BLACK,
        1.0,
    )
    r = resolver(doc)
    p = r.resolve_point(
        SegmentPoint(node="rail", index=0, pct=50.0, tangent=(10.0, 90.0))
    )
    # travel is +x; normal (right-hand) is +y
    approx_pt(p, 90.0, 50.0)
    q = r.resolve_point(SegmentPoint(node="rail", index=0, pct=50.0, tangent=10.0))
    approx_pt(q, 100.0, 40.0)


def test_zero_length_segment_rejected():
    doc = Document(200.0, 200.0)
    doc.stroke(
        "rail",
        PolySpec(closed=False, points=((40.0, 40.0), (40.0, 40.0), (80.0, 40.0))),
        wv.BLACK,
        1.0,
    )
    r = resolver(doc)
    with pytest.raises(ValueError, match="zero-length"):
        r.resolve_point(
            SegmentPoint(node="rail", index=0, pct=50.0, tangent=(10.0, 0.0))
        )


def test_tangent_composes_with_literal_offset():
    r = resolver(rim_doc())
    p = r.resolve_point(
        rim_doc().anchor("rim", pct=0.0, tangent=(20.0, 90.0), offset=(5.0, 0.0))
    )
    approx_pt(p, 145.0, 100.0)


def test_tangent_roundtrips_through_dict():
    pt = AnchorPoint(node="rim", pct=12.5, tangent=(16.0, 90.0))
    d = pt.to_dict()
    assert d["anchor"]["tangent"] == [16.0, 90.0]
    back = AnchorPoint.from_dict(d)
    assert back.tangent == (16.0, 90.0)
    seg = SegmentPoint(node="rail", index=0, pct=50.0, tangent=(10.0, 0.0))
    seg2 = SegmentPoint.from_dict(seg.to_dict())
    assert seg2.tangent == (10.0, 0.0)


def test_tangent_shapes_usable_everywhere():
    doc = Document(200.0, 200.0)
    doc.stroke("rim", wvd.CircleSpec((100.0, 100.0), 60.0), wv.BLACK, 1.0)
    # a dot offset outward from the rim — tangent clauses work as any point
    at = doc.anchor("rim", pct=0.0, tangent=(16.0, 90.0))
    doc.fill("dot", wvd.CircleSpec(at, 3.0), wv.RED)
    ops = doc.resolve_to_json()
    dot = ops[-1]
    assert dot["op"] == "fill"
    c = dot["shape"]["center"]
    assert abs(c[0] - 144.0) < 1e-9 and abs(c[1] - 100.0) < 1e-9
