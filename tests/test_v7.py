"""v7 constructs: arc_between connectors + intersects point form (§7.22/§7.23)."""

import math

import pytest

import windvg as wv
import windvg.document as wvd
from windvg.document import (
    ArcBetweenSpec,
    Document,
    IntersectsPoint,
)
from windvg.shapes import Arc


def geom_doc():
    doc = Document(220.0, 160.0)
    doc.fill(
        "rail",
        wvd.PolySpec(closed=False, points=((30.0, 110.0), (190.0, 50.0))),
        wv.rgb(0, 0, 0),
        visible=False,
    )
    doc.fill("hoop", wv.Circle((110.0, 80.0), 45.0), wv.rgb(0, 0, 0), visible=False)
    return doc


def test_arc_between_90():
    r = wvd._Resolver(Document(10.0, 10.0))
    arc = r.expand(ArcBetweenSpec((40.0, 120.0), (180.0, 120.0), 90.0))[0]
    assert isinstance(arc, Arc)
    assert abs(arc.center.x - 110.0) < 1e-9
    assert abs(arc.center.y - 190.0) < 1e-9
    assert abs(arc.radius - 70.0 * math.sqrt(2.0)) < 1e-9
    assert abs(arc.start_deg - (-135.0)) < 1e-9
    assert abs(arc.sweep_deg - 90.0) < 1e-9


def test_arc_between_negative_bulges_other_way():
    r = wvd._Resolver(Document(10.0, 10.0))
    arc = r.expand(ArcBetweenSpec((40.0, 120.0), (180.0, 120.0), -60.0))[0]
    assert abs(arc.radius - 140.0) < 1e-9
    assert arc.center.y < 120.0, "negative sweep bulges opposite"
    # ends at q
    end = arc.point_at_distance(arc.perimeter())
    assert abs(end.x - 180.0) < 1e-9 and abs(end.y - 120.0) < 1e-9


def test_arc_between_resolves_through_spec():
    doc = Document(220.0, 160.0)
    doc.stroke(
        "deck",
        ArcBetweenSpec((40.0, 120.0), (180.0, 120.0), 90.0),
        wv.rgb(0, 0, 0),
        2.0,
    )
    ops = doc.resolve_to_json()
    assert ops[0]["shape"]["kind"] == "arc"
    assert ops[0]["shape"]["sweep_deg"] == 90.0
    scene = doc.resolve()
    svg = scene.to_svg()
    assert "A 98.995 98.995" in svg or "98.995" in svg


def test_arc_between_parametric_endpoints():
    doc = geom_doc()
    doc.stroke(
        "bridge",
        ArcBetweenSpec(
            wvd.AnchorPoint("rail", pct=0.0),
            wvd.AnchorPoint("rail", pct=100.0),
            60.0,
        ),
        wv.rgb(0, 0, 0),
        1.5,
    )
    ops = doc.resolve_to_json()
    assert ops[-1]["shape"]["kind"] == "arc"


def test_arc_between_validation():
    r = wvd._Resolver(Document(10.0, 10.0))
    with pytest.raises(ValueError, match="must differ"):
        r.expand(ArcBetweenSpec((5.0, 5.0), (5.0, 5.0), 90.0))
    with pytest.raises(ValueError, match="nonzero"):
        r.expand(ArcBetweenSpec((0.0, 0.0), (10.0, 0.0), 0.0))
    with pytest.raises(ValueError, match="within"):
        r.expand(ArcBetweenSpec((0.0, 0.0), (10.0, 0.0), 360.0))


def test_intersects_finds_both_crossings():
    r = wvd._Resolver(geom_doc())
    p1 = r.resolve_point(IntersectsPoint("rail", "hoop", 1))
    p2 = r.resolve_point(IntersectsPoint("rail", "hoop", 2))
    assert p1.x < p2.x, "chain order runs along the rail"
    # both lie on the hoop
    for p in (p1, p2):
        d = math.hypot(p.x - 110.0, p.y - 80.0)
        assert abs(d - 45.0) < 0.2, f"not on the hoop: {d}"


def test_intersects_symmetry_and_missing_k():
    r = wvd._Resolver(geom_doc())
    a1 = r.resolve_point(IntersectsPoint("rail", "hoop", 1))
    b1 = r.resolve_point(IntersectsPoint("hoop", "rail", 1))
    assert abs(a1.x - b1.x) < 1e-9 and abs(a1.y - b1.y) < 1e-9
    with pytest.raises(ValueError, match="no intersection #3"):
        r.resolve_point(IntersectsPoint("rail", "hoop", 3))


def test_intersects_roundtrip_and_codegen():
    doc = geom_doc()
    doc.fill(
        "cross",
        wvd.CircleSpec(IntersectsPoint("rail", "hoop", 1), 4.0),
        wv.rgb(1, 0, 0),
    )
    doc2 = Document.from_dict(doc.to_dict())
    pt = doc2.nodes[-1].shape.center
    assert isinstance(pt, IntersectsPoint)
    assert pt.k == 1
    assert doc2.resolve_to_json()[-1]["bbox"] == doc.resolve_to_json()[-1]["bbox"]
    code = doc.generate_code()
    assert "IntersectsPoint(a='rail', b='hoop', k=1)" in code
    assert "ArcBetweenSpec" not in code


def test_arc_between_codegen_roundtrip():
    doc = Document(220.0, 160.0)
    doc.stroke(
        "deck",
        ArcBetweenSpec((40.0, 120.0), (180.0, 120.0), 90.0),
        wv.rgb(0, 0, 0),
        2.0,
    )
    doc2 = Document.from_code(doc.generate_code())
    spec = doc2.nodes[0].shape
    assert isinstance(spec, ArcBetweenSpec)
    assert spec.deg == 90.0
    assert doc2.resolve_to_json() == doc.resolve_to_json()
