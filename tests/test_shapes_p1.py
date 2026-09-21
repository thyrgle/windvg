import math

import pytest
from conftest import assert_pt

from windvg import Arc, Circle, Ellipse, Point, Polygon, Polyline


def ramanujan_perimeter(rx: float, ry: float) -> float:
    return math.pi * (3 * (rx + ry) - math.sqrt((3 * rx + ry) * (rx + 3 * ry)))


class TestEllipse:
    def test_perimeter_matches_ramanujan(self):
        ellipse = Ellipse((0, 0), 10, 6, rotation_deg=33)
        # rotation must not change the perimeter
        assert ellipse.perimeter() == pytest.approx(ramanujan_perimeter(10, 6), rel=1e-4)

    def test_param_points_respect_rotation(self):
        ellipse = Ellipse((100, 100), 20, 10, rotation_deg=90)
        # parameter 0 sits along the rotated +x axis: +90 deg maps it to straight down
        assert_pt(ellipse.point_at_param(0.0), (100, 120))

    def test_track_round_trip(self):
        ellipse = Ellipse((50, 50), 30, 15)
        for d in (0, 10, ellipse.perimeter() / 2, ellipse.perimeter() - 0.1):
            d2 = ellipse._table.param_to_distance(
                ellipse._table.distance_to_param(d)
            )
            assert d2 == pytest.approx(d, abs=1e-6)

    def test_project_finds_nearest_point(self):
        ellipse = Ellipse((50, 50), 30, 15)
        d = ellipse.project(Point(90, 50))
        assert_pt(ellipse.point_at_distance(d), (80, 50))

    def test_winding_sign(self):
        assert Ellipse((0, 0), 10, 5).winding_sign == 1

    def test_validation(self):
        with pytest.raises(ValueError):
            Ellipse((0, 0), 0, 5)
        with pytest.raises(ValueError):
            Ellipse((0, 0), 5, -1)


class TestArc:
    def test_perimeter_is_fraction_of_circle(self):
        assert Arc((0, 0), 10, 0, 90).perimeter() == pytest.approx(5 * math.pi)
        assert Arc((0, 0), 10, 0, -90).perimeter() == pytest.approx(5 * math.pi)

    def test_positive_sweep_travels_clockwise(self):
        arc = Arc((100, 100), 20, 0, 90)
        assert_pt(arc.point_at_distance(0), (120, 100))
        assert_pt(arc.point_at_distance(arc.perimeter()), (100, 120))  # bottom
        assert arc.winding_sign == 1

    def test_negative_sweep_travels_counter_clockwise(self):
        arc = Arc((100, 100), 20, 0, -90)
        assert_pt(arc.point_at_distance(arc.perimeter()), (100, 80))  # top
        assert arc.winding_sign == -1

    def test_points_along_sweep(self):
        arc = Arc((0, 0), 10, 0, 180)
        assert_pt(arc.point_at_distance(arc.perimeter() / 2), (0, 10))
        diag = 10 * math.cos(math.pi / 4)
        assert_pt(arc.point_at_distance(arc.perimeter() / 4), (diag, diag))

    def test_project_clamps_to_nearest_end(self):
        arc = Arc((100, 100), 20, 0, 90)
        probe = Arc((100, 100), 20, 0, 90)
        # inside the sweep: plain projection
        assert arc.project(probe.point_at_deg(45)) == pytest.approx(arc.perimeter() / 2)
        # beyond the end but nearer the end than the start
        assert arc.project(probe.point_at_deg(350)) == pytest.approx(arc.perimeter())
        # way past the end, nearer the start again
        assert arc.project(probe.point_at_deg(200)) == 0.0

    def test_tangent_is_perpendicular_to_radius(self):
        arc = Arc((0, 0), 10, 20, 45)
        for d in (0, arc.perimeter() / 2, arc.perimeter()):
            t = arc.tangent_at_distance(d)
            radial = arc.point_at_distance(d) - arc.center
            assert t.dot(radial) == pytest.approx(0, abs=1e-9)
            assert t.length() == pytest.approx(1.0)

    def test_sweep_bounds(self):
        with pytest.raises(ValueError):
            Arc((0, 0), 10, 0, 360)
        with pytest.raises(ValueError):
            Arc((0, 0), 10, 0, 0)

    def test_not_fillable(self):
        assert Arc((0, 0), 10, 0, 90).fillable is False


class TestTangents:
    def test_polygon_tangent_follows_vertex_order(self):
        square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        assert_pt(square.tangent_at_distance(2), (1, 0))
        assert_pt(square.tangent_at_distance(12), (0, 1))
        assert_pt(square.tangent_at_distance(22), (-1, 0))
        assert_pt(square.tangent_at_distance(32), (0, -1))

    def test_polyline_tangent(self):
        line = Polyline([(0, 0), (3, 4), (3, 10)])
        assert_pt(line.tangent_at_distance(1), (0.6, 0.8))
        assert_pt(line.tangent_at_distance(6), (0, 1))

    def test_circle_tangent_is_clockwise_travel(self):
        circle = Circle((0, 0), 10)
        assert_pt(circle.tangent_at_distance(0), (0, 1))  # heading down at the right point
