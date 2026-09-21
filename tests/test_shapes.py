import math

import pytest
from conftest import assert_pt

from windvg import Circle, Point, Polygon, Polyline

SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]  # visually clockwise (y-down)


class TestPolygon:
    def test_perimeter(self):
        assert Polygon(SQ).perimeter() == 40

    def test_point_at_distance_walks_vertex_order(self):
        square = Polygon(SQ)
        assert square.point_at_distance(0) == Point(0, 0)
        assert square.point_at_distance(5) == Point(5, 0)
        assert square.point_at_distance(15) == Point(10, 5)
        assert square.point_at_distance(25) == Point(5, 10)
        assert square.point_at_distance(35) == Point(0, 5)

    def test_wraps_and_negative(self):
        square = Polygon(SQ)
        assert square.point_at_distance(45) == Point(5, 0)
        assert square.point_at_distance(-5) == Point(0, 5)

    def test_winding_sign(self):
        assert Polygon(SQ).winding_sign == 1
        assert Polygon(list(reversed(SQ))).winding_sign == -1

    def test_project_vertex_order_independent(self):
        # the nearest boundary POINT is vertex-order independent,
        # even though its arc-length position is not
        for pts in (SQ, list(reversed(SQ))):
            square = Polygon(pts)
            d = square.project(Point(7, -3))
            assert_pt(square.point_at_distance(d), (7, 0))

    def test_project_center_hits_first_edge(self):
        square = Polygon(SQ)
        d = square.project(Point(5, 5))
        assert square.point_at_distance(d).distance_to(Point(5, 5)) == pytest.approx(5)

    def test_validation(self):
        with pytest.raises(ValueError):
            Polygon([(0, 0), (1, 1)])
        with pytest.raises(ValueError):
            Polygon([(0, 0), (1, 1), (2, 2)])  # collinear

    def test_accepts_tuples_and_points(self):
        square = Polygon([Point(0, 0), (10, 0), Point(10, 10), (0, 10)])
        assert square.perimeter() == 40


class TestCircle:
    def test_perimeter(self):
        assert Circle((0, 0), 10).perimeter() == pytest.approx(20 * math.pi)

    def test_origin_and_clockwise_travel(self):
        from conftest import assert_pt

        circle = Circle((100, 100), 10)
        assert_pt(circle.point_at_distance(0), (110, 100))
        quarter = circle.perimeter() / 4
        # y-down: a quarter turn clockwise from the right point is the bottom
        assert_pt(circle.point_at_distance(quarter), (100, 110))

    def test_project(self):
        circle = Circle((100, 100), 10)
        assert circle.project(Point(115, 100)) == 0
        assert circle.project(Point(100, 110)) == pytest.approx(circle.perimeter() / 4)
        assert circle.project(Point(100, 90)) == pytest.approx(3 * circle.perimeter() / 4)
        assert circle.project(Point(100, 100)) == 0

    def test_validation(self):
        with pytest.raises(ValueError):
            Circle((0, 0), 0)


class TestPolyline:
    def test_perimeter_and_points(self):
        line = Polyline([(0, 0), (3, 4), (3, 10)])
        assert line.perimeter() == 11
        assert_pt(line.point_at_distance(4), (2.4, 3.2))
        assert_pt(line.point_at_distance(5), (3, 4))
        assert_pt(line.point_at_distance(11), (0, 0))  # full length wraps to start

    def test_not_fillable(self):
        assert Polyline([(0, 0), (1, 1)]).fillable is False

    def test_validation(self):
        with pytest.raises(ValueError):
            Polyline([(0, 0)])
