import math

import pytest
from conftest import assert_pt

from windvg import (
    CW,
    Circle,
    Point,
    connect,
    polygon_from_anchors,
    regular_polygon,
    star,
    star_polygon,
)


class TestRegularPolygon:
    def test_square_first_vertices_are_clockwise(self):
        square = regular_polygon((0, 0), 10, 4)
        assert_pt(square.points[0], (10, 0))
        # second vertex: +90 degrees (clockwise on screen) -> bottom
        assert_pt(square.points[1], (0, 10))
        assert len(square.points) == 4

    def test_start_angle(self):
        triangle = regular_polygon((0, 0), 10, 3, start_angle_deg=90)
        # y-down: 90 degrees points at the bottom of the circumscribed circle
        assert_pt(triangle.points[0], (0, 10))

    def test_needs_three_sides(self):
        with pytest.raises(ValueError):
            regular_polygon((0, 0), 10, 2)


class TestStar:
    def test_ten_vertices_alternating_radii(self):
        star_shape = star((0, 0), 10, 4, points=5)
        assert len(star_shape.points) == 10
        assert star_shape.points[0].distance_to(Point(0, 0)) == pytest.approx(10)
        assert star_shape.points[1].distance_to(Point(0, 0)) == pytest.approx(4)

    def test_validates_point_count(self):
        with pytest.raises(ValueError):
            star((0, 0), 10, 4, points=1)


class TestStarPolygon:
    def test_pentagram(self):
        circle = Circle((0, 0), 10)
        pentagram = star_polygon(circle, 5, 2)
        assert len(pentagram.points) == 5
        # all vertices lie on the circle
        for pt in pentagram.points:
            assert pt.distance_to(Point(0, 0)) == pytest.approx(10)

    def test_hexagram_is_two_triangles(self):
        with pytest.raises(ValueError):  # gcd(6, 2) = 2
            star_polygon(Circle((0, 0), 10), 6, 2)

    def test_skip_bounds(self):
        with pytest.raises(ValueError):
            star_polygon(Circle((0, 0), 10), 5, 1)  # skip 1 is just a polygon
        with pytest.raises(ValueError):
            star_polygon(Circle((0, 0), 10), 5, 4)


class TestAnchoredBuilders:
    def test_polygon_from_anchors_with_pct_pairs(self):
        circle = Circle((0, 0), 10)
        anchor = circle.anchor((10, 0), CW)
        square = polygon_from_anchors(
            [(anchor, 0), (anchor, 25), (anchor, 50), (anchor, 75)]
        )
        expected = regular_polygon((0, 0), 10, 4)
        for got, want in zip(square.points, expected.points, strict=True):
            assert (got.x, got.y) == pytest.approx((want.x, want.y), abs=1e-9)

    def test_polygon_from_anchors_accepts_plain_points(self):
        triangle = polygon_from_anchors([(0, 0), (10, 0), (0, 10)])
        assert triangle.perimeter() == pytest.approx(10 + 10 + math.sqrt(200))

    def test_connect_anchors_with_pcts(self):
        circle = Circle((0, 0), 10)
        square = regular_polygon((40, 0), 10, 4)
        a = circle.anchor((10, 0), CW)
        b = square.anchor((40, 10), CW)
        line = connect((a, 25), (b, 50))
        assert_pt(line.points[0], (0, 10))
        assert_pt(line.points[1], (40, -10))
