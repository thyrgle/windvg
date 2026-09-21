import math

import pytest
from conftest import assert_pt

from windvg import CCW, CW, Circle, Ellipse, Polygon

SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]  # visually clockwise vertex order


@pytest.fixture
def circle() -> Circle:
    return Circle((100, 100), 20)


class TestAnchorSemantics:
    def test_point_at_pct_zero_is_projected_start(self, circle: Circle):
        anchor = circle.anchor((130, 100), CW)  # right of center -> origin
        assert_pt(anchor.point(0), (120, 100))

    def test_projects_to_nearest_boundary(self, circle: Circle):
        # (100, 70) is 30 above center -> nearest boundary point is the top
        anchor = circle.anchor((100, 70), CW)
        assert_pt(anchor.point(0), (100, 80))

    def test_symmetry_cw_vs_ccw(self, circle: Circle):
        start = (100, 70)
        for pct in (5, 25, 50, 90):
            cw = circle.anchor(start, CW).point(pct)
            ccw = circle.anchor(start, CCW).point(100 - pct)
            assert (cw.x, cw.y) == pytest.approx((ccw.x, ccw.y), abs=1e-9), f"pct={pct}"

    def test_polygon_symmetry_both_windings(self):
        for vertices in (SQ, list(reversed(SQ))):
            square = Polygon(vertices)
            start = (5, -10)  # projects onto the top edge midpoint
            for pct in (10, 50, 90):
                cw = square.anchor(start, CW).point(pct)
                ccw = square.anchor(start, CCW).point(100 - pct)
                assert (cw.x, cw.y) == pytest.approx((ccw.x, ccw.y), abs=1e-9)

    def test_polygon_cw_travels_visually_clockwise(self):
        # even with CCW vertex order, CW anchors move clockwise on screen
        square = Polygon(list(reversed(SQ)))
        top_left = square.anchor((0, 0), CW)
        assert_pt(top_left.point(5), (2, 0))  # 5% of 40 = 2 units right
        assert_pt(top_left.point(95), (0, 2))  # ...or 2 units down

    def test_wrap_over_100_percent(self, circle: Circle):
        anchor = circle.anchor((120, 100), CW)
        assert (anchor.point(150).x, anchor.point(150).y) == pytest.approx(
            (anchor.point(50).x, anchor.point(50).y), abs=1e-9
        )

    def test_negative_pct_wraps_backwards(self, circle: Circle):
        anchor = circle.anchor((120, 100), CW)
        assert (anchor.point(-20).x, anchor.point(-20).y) == pytest.approx(
            (anchor.point(80).x, anchor.point(80).y), abs=1e-9
        )

    def test_full_lap_returns_to_start(self, circle: Circle):
        anchor = circle.anchor((100, 70), CW)
        start = anchor.point(0)
        assert (anchor.point(100).x, anchor.point(100).y) == pytest.approx(
            (start.x, start.y), abs=1e-9
        )

    def test_at_returns_shifted_anchor(self, circle: Circle):
        base = circle.anchor((120, 100), CW)
        shifted = base.at(25)  # quarter turn clockwise from the right point
        assert shifted.start_distance == pytest.approx(math.pi / 2 * 20)
        assert_pt(shifted.point(0), (100, 120))

    def test_anchor_direction_preserved_through_at(self, circle: Circle):
        base = circle.anchor((120, 100), CCW)
        assert base.at(25).direction is CCW


class TestAnchorTangentAndOffset:
    def test_tangent_follows_anchor_direction(self, circle: Circle):
        right = circle.anchor((120, 100))
        assert_pt(right.tangent(0), (0, 1))  # CW: heading down at the right point
        assert_pt(right.tangent(25), (-1, 0))  # at the bottom, heading left
        ccw = circle.anchor((120, 100), CCW)
        assert_pt(ccw.tangent(0), (0, -1))  # CCW: heading up

    def test_tangent_after_travel(self, circle: Circle):
        anchor = circle.anchor((120, 100), CW)
        at_bottom = anchor.at(25)
        assert_pt(at_bottom.point(0), (100, 120))
        assert_pt(at_bottom.tangent(0), (-1, 0))

    def test_offset_positive_is_outward_for_cw(self, circle: Circle):
        right = circle.anchor((120, 100), CW)
        assert_pt(right.offset(0, 5), (125, 100))  # away from center
        assert_pt(right.offset(0, -5), (115, 100))  # toward center

    def test_offset_is_left_of_travel_so_ccw_flips(self, circle: Circle):
        # CCW anchors travel the other way, so positive offset points inward
        top = circle.anchor((100, 80), CCW)  # heading west (-x) at the top
        assert_pt(top.tangent(0), (-1, 0))
        assert_pt(top.offset(0, 5), (100, 85))  # left of west is down: inward

    def test_offset_on_polygon_edge(self):
        square = Polygon(SQ)  # clockwise vertex order
        top_edge = square.anchor((5, 0), CW)  # traveling +x along the top edge
        assert_pt(top_edge.tangent(0), (1, 0))
        assert_pt(top_edge.offset(0, 2), (5, -2))  # above the edge, outside

    def test_tangent_on_ellipse(self):
        ellipse = Ellipse((0, 0), 20, 10)
        origin = ellipse.anchor((20, 0), CW)
        assert_pt(origin.tangent(0), (0, 1))
