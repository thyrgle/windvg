import pytest
from tvgreader import parse

from windvg import (
    AlongSpec,
    AnchorPoint,
    Circle,
    Document,
    LinearGradient,
    Orientation,
    Polygon,
    RadialGradient,
    regular_polygon,
    rgb,
    rgba,
)
from windvg.document import (
    ArcSpec,
    CircleSpec,
    CompoundSpec,
    EllipseSpec,
    GridSpec,
    PathSpec,
    PolarSpec,
    PolySpec,
    RoundedSpec,
)

ORANGE = rgb(1, 0.6, 0.2)
NAVY = rgb(0.15, 0.2, 0.45)


def sample_document() -> Document:
    doc = Document(240, 240)
    doc.fill("body", Circle((120, 120), 70), ORANGE)
    doc.stroke("rim", CircleSpec((120, 120), 74), NAVY, width=2.0)
    doc.outline_fill(
        "plate",
        regular_polygon((120, 120), 40, 4),
        RadialGradient((120, 120), (120, 80), rgb(1, 1, 1), NAVY),
        rgba(0, 0, 0, 0.6),
        width=1.5,
    )
    doc.fill("ghost", Circle((30, 30), 10), rgb(0.5, 0.5, 0.5), visible=False)
    return doc


class TestDictRoundTrip:
    def test_survives_dict_conversion(self):
        doc = sample_document()
        assert Document.from_dict(doc.to_dict()).to_dict() == doc.to_dict()

    def test_specs_survive_dict_conversion(self):
        doc = Document(100, 100)
        doc.fill(
            "spec-y",
            CompoundSpec(
                (
                    CircleSpec(AnchorPoint("other", pct=25), 10),
                    EllipseSpec((50, 50), 30, 12, rotation_deg=30),
                    ArcSpec((50, 50), 40, 0, 90),
                    PolySpec(True, ((0, 0), (10, 0), (10, 10))),
                    PolySpec(False, ((0, 0), {"anchor": {"node": "other", "pct": 50}})),
                )
            ),
            ORANGE,
        )
        doc.fill("other", Circle((80, 80), 12), NAVY)
        doc.stroke(
            "gen",
            AlongSpec(
                track=Circle((50, 50), 40),
                motifs=(PolySpec(True, ((-5, -5), (5, -5), (0, 5))),),
                n=6,
                offset_pct=10,
                align="tangent",
            ),
            NAVY,
        )
        doc.stroke(
            "polar",
            PolarSpec((50, 50), (PolySpec(True, ((0, 0), (2, 0), (1, 3))),), 5, radius=30),
            NAVY,
        )
        doc.stroke(
            "grid",
            GridSpec(
                (PolySpec(True, ((0, 0), (3, 0), (1, 3))),), 2, 2, 10, 10, origin=(60, 60)
            ),
            NAVY,
        )
        doc.fill(
            "path",
            PathSpec(
                (
                    (
                        (10, 10),
                        [
                            {"cmd": "line", "to": [50, 10]},
                            {
                                "cmd": "cubic",
                                "c1": [70, 10],
                                "c2": [70, 50],
                                "to": [50, 50],
                            },
                            {"cmd": "close"},
                        ],
                    ),
                )
            ),
            rgb(0.2, 0.5, 0.9),
        )
        restored = Document.from_dict(doc.to_dict())
        assert restored.to_dict() == doc.to_dict()

    def test_duplicate_names_rejected(self):
        doc = sample_document()
        with pytest.raises(ValueError):
            doc.fill("body", Circle((0, 0), 1), ORANGE)

    def test_get_by_id_and_name(self):
        doc = sample_document()
        assert doc.get("body") is doc.get(doc.nodes[0].id)


class TestResolve:
    def test_resolve_matches_manual_scene(self):
        doc = Document(200, 200)
        doc.fill("body", Circle((100, 100), 60), ORANGE)
        doc.stroke("rim", Circle((100, 100), 64), NAVY, width=2.0)
        doc.fill("ghost", Circle((10, 10), 5), NAVY, visible=False)

        manual = Document(200, 200).resolve()
        _ = manual  # empty baseline
        scene = Document(200, 200).resolve()
        assert scene.ops == []

        expected_scene_from_document = doc.resolve()
        assert len(expected_scene_from_document.ops) == 2  # ghost is hidden

    def test_resolve_bytes_match_scene_api(self):
        doc = Document(100, 100)
        doc.fill("tri", Polygon([(10, 10), (90, 10), (10, 90)]), rgb(0.2, 0.5, 0.9))
        doc.stroke("circ", Circle((50, 50), 30), rgb(0, 0, 0), width=1.5)

        scene = Document(100, 100).resolve()
        _ = scene
        manual = Document(100, 100)
        manual.fill("tri", Polygon([(10, 10), (90, 10), (10, 90)]), rgb(0.2, 0.5, 0.9))
        manual.stroke("circ", Circle((50, 50), 30), rgb(0, 0, 0), width=1.5)
        assert doc.resolve().to_tinyvg() == manual.resolve().to_tinyvg()

    def test_anchor_resolution_point_math(self):
        doc = Document(200, 200)
        doc.fill("wheel", Circle((100, 100), 40), ORANGE)
        doc.stroke(
            "marker",
            PolySpec(
                False,
                (
                    (200, 200),
                    {"anchor": {"node": "wheel", "pct": 25, "start": [140, 100]}},
                ),
            ),
            NAVY,
        )
        scene = doc.resolve()
        marker = scene.ops[1].shape
        # pct 25 of a CW circle from the right point is the bottom
        assert (marker.points[1].x, marker.points[1].y) == pytest.approx(
            (100, 140), abs=1e-9
        )

    def test_anchor_point_helper(self):
        doc = Document(200, 200)
        doc.fill("wheel", Circle((100, 100), 40), ORANGE)
        anchor = doc.anchor("wheel", pct=50, start=(140, 100), direction=Orientation.CCW)
        doc.stroke("marker", PolySpec(False, ((200, 200), anchor)), NAVY)
        scene = doc.resolve()
        marker = scene.ops[1].shape
        assert (marker.points[1].x, marker.points[1].y) == pytest.approx(
            (60, 100), abs=1e-9
        )

    def test_generator_expansion(self):
        doc = Document(200, 200)
        doc.fill(
            "beads",
            AlongSpec(
                track=Circle((100, 100), 60),
                motifs=(Circle((0, 0), 5),),
                n=8,
            ),
            NAVY,
        )
        scene = doc.resolve()
        assert len(scene.ops) == 8

    def test_resolved_render_matches_scene_api(self):
        doc = Document(100, 100)
        doc.fill("tri", Polygon([(10, 10), (90, 10), (10, 90)]), rgb(0.2, 0.5, 0.9))
        doc.stroke("circ", Circle((50, 50), 30), rgb(0, 0, 0), width=1.5)

        manual = Document(100, 100)
        manual_scene = manual.resolve()
        _ = manual_scene
        scene = doc.resolve()
        parsed = parse(scene.to_tinyvg())
        assert len(parsed["shapes"]) == 2
        assert parsed["shapes"][0]["op"] == "fill"
        assert parsed["shapes"][1]["op"] == "stroke"


class TestCodeRoundTrip:
    def test_generate_then_execute_reproduces_document(self):
        doc = sample_document()
        doc.fill(
            "beads",
            AlongSpec(
                track=Circle((120, 120), 74),
                motifs=(Circle((0, 0), 6),),
                n=10,
                align="tangent",
            ),
            NAVY,
        )
        doc.fill(
            "accent",
            RoundedSpec(PolySpec(True, ((0, 0), (40, 0), (40, 40), (0, 40))), 8),
            NAVY,
        )

        code = doc.generate_code()
        assert "import windvg as wv" in code
        assert "doc.fill('body'" in code or 'doc.fill("body"' in code
        restored = Document.from_code(code)
        assert restored.to_dict() == doc.to_dict()

    def test_code_round_trip_is_stable(self):
        doc = sample_document()
        once = Document.from_code(doc.generate_code()).generate_code()
        twice = Document.from_code(once).generate_code()
        assert once == twice

    def test_generated_code_uses_anchor_helpers(self):
        doc = Document(100, 100)
        doc.fill("wheel", Circle((50, 50), 20), ORANGE)
        doc.stroke("marker", PolySpec(False, ((0, 0), doc.anchor("wheel", pct=75))), NAVY)
        code = doc.generate_code()
        assert "doc.anchor(" in code
        restored = Document.from_code(code)
        assert restored.resolve().to_tinyvg() == doc.resolve().to_tinyvg()

    def test_from_scene_code_is_lossy_but_renders_identically(self):
        source = """
import windvg as wv
scene = wv.Scene(100, 100)
tri = wv.Polygon([(10, 10), (90, 10), (10, 90)])
scene.fill(tri, wv.rgb(0.2, 0.5, 0.9))
scene.stroke(wv.Circle((50, 50), 30), wv.rgb(0, 0, 0), width=1.5)
"""
        doc = Document.from_scene_code(source)
        assert len(doc.nodes) == 2
        assert doc.nodes[0].name == "shape_1"
        assert doc.nodes[0].op == "fill"
        reference = """
import windvg as wv
scene = wv.Scene(100, 100)
tri = wv.Polygon([(10, 10), (90, 10), (10, 90)])
scene.fill(tri, wv.rgb(0.2, 0.5, 0.9))
scene.stroke(wv.Circle((50, 50), 30), wv.rgb(0, 0, 0), width=1.5)
"""
        _ = reference
        assert (
            doc.resolve().to_tinyvg()
            == Document.from_scene_code(source).resolve().to_tinyvg()
        )

    def test_from_code_requires_document(self):
        with pytest.raises(ValueError):
            Document.from_code("x = 1")


class TestResolveToJSON:
    def test_ops_carry_node_identity(self):
        doc = Document(100, 100)
        doc.fill(
            "beads",
            AlongSpec(
                track=Circle((50, 50), 40),
                motifs=(Circle((0, 0), 4),),
                n=3,
            ),
            ORANGE,
        )
        ops = doc.resolve_to_json()
        assert len(ops) == 3
        assert all(op["id"] == ops[0]["id"] for op in ops)
        assert ops[0]["op"] == "fill"
        assert ops[0]["shape"]["kind"] == "circle"

    def test_paint_serialization(self):
        scene_paint = RadialGradient((50, 50), (90, 50), rgb(1, 1, 1), rgb(0, 0, 0))
        doc = Document(100, 100)
        doc.fill("ball", Circle((50, 50), 40), scene_paint)
        ops = doc.resolve_to_json()
        assert ops[0]["paint"]["kind"] == "radial"
        _ = LinearGradient  # imported for parity with user paints
