import math

import pytest
from conftest import assert_pt
from tvgreader import parse

from windvg import (
    BLACK,
    BLUE,
    ArcCircle,
    Circle,
    Close,
    Compound,
    Line,
    Path,
    PathBuilder,
    Point,
    Polygon,
    Polyline,
    Scene,
    regular_polygon,
    rgb,
)
from windvg.ext import Transform, rounded, scaled, transformed


class TestPathBasics:
    def test_line_box_track(self):
        box = (
            PathBuilder((0, 0))
            .line_to((10, 0))
            .line_to((10, 10))
            .line_to((0, 10))
            .close()
            .build()
        )
        assert box.perimeter() == pytest.approx(40)
        assert_pt(box.point_at_distance(5), (5, 0))
        assert box.closed
        assert box.fillable
        assert box.winding_sign == 1  # clockwise on screen

    def test_open_path_clamps(self):
        open_path = PathBuilder((0, 0)).line_to((10, 0)).build()
        assert not open_path.closed
        assert not open_path.fillable
        assert_pt(open_path.point_at_distance(99), (10, 0))
        assert_pt(open_path.point_at_distance(-5), (0, 0))

    def test_quad_and_cubic_endpoints(self):
        path = (
            PathBuilder((0, 0))
            .quad_to((5, 10), (10, 0))
            .cubic_to((15, 10), (20, -10), (25, 0))
            .build()
        )
        assert path.perimeter() > 10  # curves are longer than their chords
        assert_pt(path.point_at_distance(0), (0, 0))
        end = path.point_at_distance(path.perimeter())
        assert (end.x, end.y) == pytest.approx((25, 0), abs=1e-9)

    def test_arc_instruction_flattening(self):
        # up, then a clockwise semicircle: travel leaves (0, 10) heading north
        # and arcs over the top through (5, 5) before landing at (10, 10)
        path = (
            PathBuilder((0, 0))
            .line_to((0, 10))
            .arc_circle_to(5, (10, 10), sweep_cw=True)
            .build()
        )
        samples = [path.point_at_distance(d) for d in (15, 16, 17)]
        assert any(p.y < 7 for p in samples)  # passes well above the chord
        # chordal flattening underestimates the arc slightly
        assert path.perimeter() == pytest.approx(10 + 5 * math.pi, rel=1e-2)

    def test_multi_subpath_project(self):
        ring = (
            PathBuilder((0, 0))
            .line_to((10, 0))
            .line_to((10, 10))
            .line_to((0, 10))
            .close()
            .move_to((100, 100))
            .line_to((110, 100))
            .build()
        )
        d = ring.project(Point(105, 100))
        assert_pt(ring.point_at_distance(d), (105, 100))

    def test_winding_sign_flips_with_mirror(self):
        box = (
            PathBuilder((0, 0))
            .line_to((10, 0))
            .line_to((10, 10))
            .line_to((0, 10))
            .close()
            .build()
        )
        assert transformed(box, Transform.mirror_x()).winding_sign == -1


class TestPathRoundTrip:
    def test_mixed_instructions_survive(self):
        path = (
            PathBuilder((20, 20))
            .line_to((80, 20))
            .quad_to((95, 20), (95, 35))
            .cubic_to((95, 70), (20, 95), (20, 50))
            .close()
            .build()
        )
        scene = Scene(120, 120)
        scene.fill(path, rgb(0.2, 0.5, 0.9))
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "fill"
        assert len(shape["paths"]) == 1
        commands = shape["paths"][0]["commands"]
        assert commands[0]["cmd"] == "line"
        assert commands[1]["cmd"] == "quad"
        assert commands[2]["cmd"] == "cubic"
        assert commands[3] == {"cmd": "close"}
        # endpoints quantize exactly
        assert commands[1]["to"] == pytest.approx((95, 35), abs=0.05)

    def test_stroke_path_is_line_path(self):
        path = PathBuilder((10, 10)).line_to((50, 10)).arc_circle_to(10, (50, 30)).build()
        scene = Scene(100, 100)
        scene.stroke(path, BLACK, width=1.5)
        parsed = parse(scene.to_tinyvg())
        assert parsed["shapes"][0]["op"] == "stroke"
        assert parsed["shapes"][0]["paths"][0]["commands"][0]["cmd"] == "line"

    def test_transformed_path_round_trips(self):
        path = PathBuilder((0, 0)).line_to((10, 0)).arc_circle_to(5, (10, 10)).build()
        moved = scaled(path, 3, 3)
        scene = Scene(100, 100)
        scene.stroke(moved, BLACK, width=1.0)
        parsed = parse(scene.to_tinyvg())
        arc = parsed["shapes"][0]["paths"][0]["commands"][1]
        assert arc["cmd"] == "arc"
        assert arc["radius"] == pytest.approx(15, abs=0.05)
        assert arc["target"] == pytest.approx((30, 30), abs=0.05)


class TestCompound:
    def make_donut(self) -> Compound:
        outer = regular_polygon((100, 100), 80, 4)
        inner = Circle((100, 100), 20)
        return Compound([outer, inner])

    def test_fill_round_trips_two_segments(self):
        scene = Scene(200, 200)
        scene.fill(self.make_donut(), rgb(0.9, 0.3, 0.2))
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "fill"
        assert len(shape["paths"]) == 2  # square segment + circle segment
        assert shape["paths"][1]["commands"][0]["cmd"] == "arc"

    def test_stroke_expands_to_each_part(self):
        scene = Scene(200, 200)
        scene.stroke(self.make_donut(), BLACK, width=2.0)
        parsed = parse(scene.to_tinyvg())
        assert [shape["op"] for shape in parsed["shapes"]] == ["stroke", "stroke"]

    def test_outline_fill_rejected(self):
        with pytest.raises(ValueError):
            Scene(200, 200).outline_fill(self.make_donut(), BLUE, BLACK)

    def test_track_queries_raise(self):
        donut = self.make_donut()
        with pytest.raises(NotImplementedError):
            donut.point_at_distance(5)
        with pytest.raises(NotImplementedError):
            donut.project(Point(100, 100))

    def test_validation(self):
        with pytest.raises(ValueError):
            Compound([])
        with pytest.raises(ValueError):
            Compound([Polyline([(0, 0), (5, 5)])])  # not fillable


class TestRounded:
    def test_rounded_square_perimeter_shrinks(self):
        square = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
        soft = rounded(square, 4)
        assert isinstance(soft, Path)
        # 4 straight edges of 12 plus 4 quarter arcs of radius 4; chordal
        # flattening underestimates slightly, hence the loose tolerance
        expected = 4 * 12 + 2 * math.pi * 4
        assert soft.perimeter() == pytest.approx(expected, rel=5e-3)
        assert soft.fillable

    def test_corners_are_arcs(self):
        square = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
        soft = rounded(square, 4)
        instructions = [type(i) for i in soft.subpaths[0].instructions]
        # starts with vertex 0's fillet; close() makes the final straight hop
        assert instructions == [
            ArcCircle, Line, ArcCircle, Line, ArcCircle, Line, ArcCircle, Close
        ]

    def test_radius_too_large_raises(self):
        square = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
        with pytest.raises(ValueError):
            rounded(square, 15)

    def test_ccw_polygon_flips_arc_direction(self):
        ccw = Polygon(list(reversed([(0, 0), (20, 0), (20, 20), (0, 20)])))
        soft = rounded(ccw, 4)
        arc = next(i for i in soft.subpaths[0].instructions if isinstance(i, ArcCircle))
        assert arc.sweep_cw is False

    def test_round_trip(self):
        square = regular_polygon((50, 50), 40, 4)
        soft = rounded(square, 8)
        scene = Scene(120, 120)
        scene.fill(soft, rgb(0.2, 0.5, 0.9))
        parsed = parse(scene.to_tinyvg())
        commands = parsed["shapes"][0]["paths"][0]["commands"]
        assert sum(1 for c in commands if c["cmd"] == "arc") == 4
        assert commands[-1] == {"cmd": "close"}
