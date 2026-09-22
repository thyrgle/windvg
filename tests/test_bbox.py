import math

import pytest

from windvg import (
    Arc,
    Circle,
    Compound,
    Cubic,
    Ellipse,
    Line,
    Path,
    Point,
    Polygon,
    Polyline,
    SubPath,
)


def corners(s):
    lo, hi = s.bbox()
    return (lo.x, lo.y, hi.x, hi.y)


def approx_box(actual, expected, tol=1e-6):
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected, strict=True):
        assert a == pytest.approx(e, abs=tol)


class TestBBox:
    def test_polygon(self):
        sq = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        approx_box(corners(sq), (0, 0, 10, 10))

    def test_circle(self):
        approx_box(corners(Circle((5, 7), 2)), (3, 5, 7, 9))

    def test_ellipse_axis_aligned(self):
        approx_box(corners(Ellipse((0, 0), 4, 2)), (-4, -2, 4, 2))

    def test_ellipse_rotated_45(self):
        # rx=4, ry=2 rotated 45deg: half-extent = hypot(4*cos45, 2*sin45)
        hw = math.hypot(4 * math.cos(math.radians(45)), 2 * math.sin(math.radians(45)))
        e = Ellipse((10, 10), 4, 2, rotation_deg=45)
        approx_box(corners(e), (10 - hw, 10 - hw, 10 + hw, 10 + hw))

    def test_ellipse_matches_sampling(self):
        e = Ellipse((3, -2), 5, 3, rotation_deg=30)
        lo, hi = e.bbox()
        n = 4096
        for i in range(n):
            p = e.point_at_distance(e.perimeter() * i / n)
            assert lo.x <= p.x + 1e-6 and p.x <= hi.x + 1e-6
            assert lo.y <= p.y + 1e-6 and p.y <= hi.y + 1e-6

    def test_arc_cardinal_extremes(self):
        # quarter arc through the bottom cardinal (90 deg, y-down)
        a = Arc((0, 0), 5, 0, 90)
        approx_box(corners(a), (0, 0, 5, 5))

    def test_arc_endpoints_only(self):
        a = Arc((0, 0), 5, 10, 40)  # 10..50 deg, no cardinal crossed
        approx_box(
            corners(a),
            (
                5 * math.cos(math.radians(50)),
                5 * math.sin(math.radians(10)),
                5 * math.cos(math.radians(10)),
                5 * math.sin(math.radians(50)),
            ),
        )

    def test_arc_negative_sweep(self):
        a = Arc((0, 0), 5, 0, -90)  # from (5,0) up through (0,-5), y-down
        approx_box(corners(a), (0, -5, 5, 0))

    def test_polyline(self):
        pl = Polyline([(1, 2), (5, -3), (9, 4)])
        approx_box(corners(pl), (1, -3, 9, 4))

    def test_path_flat_bounding(self):
        p = Path(
            [
                SubPath(
                    Point(0, 0),
                    (
                        Cubic(Point(2, 10), Point(8, 10), Point(10, 0)),
                        Line(Point(10, 5)),
                    ),
                )
            ]
        )
        lo, hi = p.bbox()
        assert lo.x == 0 and hi.x == 10
        assert lo.y >= 0 and hi.y <= 10
        # cubic must exceed the endpoints' y=0..5 range
        assert hi.y > 5

    def test_compound_union(self):
        c = Compound([Circle((0, 0), 2), Circle((10, 0), 1)])
        approx_box(corners(c), (-2, -2, 11, 2))

    def test_shape_default_sampling_fallback(self):
        # a bare Shape subclass with only track queries still gets a bbox
        from windvg.shapes import Shape

        class Blob(Shape):
            def perimeter(self):
                return 4.0

            def point_at_distance(self, d):
                return Point(d, d * d)

            def tangent_at_distance(self, d):
                return Point(1, 0)

            def project(self, pt):
                return 0.0

            @property
            def winding_sign(self):
                return 1

        b = Blob()
        lo, hi = b.bbox()
        assert lo.x == pytest.approx(0, abs=4 / 256)
        assert hi.x == pytest.approx(4, abs=4 / 256)
        assert hi.y == pytest.approx(16, abs=0.5)
