import pytest

from windvg import Arc, Circle, Orientation, Point, Polyline, regular_polygon
from windvg.ext import Transform, along, grid, polar, sample

CW = Orientation.CW


class TestSample:
    def test_closed_track_n_points_no_duplicate(self):
        circle = Circle((100, 100), 20)
        pts = sample(circle, 4)
        assert pts[0] == Circle((100, 100), 20).point_at_distance(0)
        assert pts[1] == Circle((100, 100), 20).point_at_distance(circle.perimeter() / 4)
        assert len(pts) == 4

    def test_offset_shifts_start(self):
        circle = Circle((100, 100), 20)
        pts = sample(circle, 4, offset_pct=50)
        assert pts[0] == circle.point_at_distance(circle.perimeter() / 2)

    def test_open_track_includes_both_ends(self):
        arc = Arc((0, 0), 10, 0, 90)
        pts = sample(arc, 3)
        assert pts[0] == arc.start_point
        assert pts[2] == arc.end_point

    def test_needs_at_least_one_point(self):
        with pytest.raises(ValueError):
            sample(Circle((0, 0), 1), 0)


class TestAlong:
    def test_places_motif_at_track_points(self):
        circle = Circle((0, 0), 10)
        motif = Polyline([(0, 0), (3, 0)])
        placed = along(circle, [motif], 4)
        assert len(placed) == 4
        origins = [p.points[0] for p in placed]
        expected = [
            Circle((0, 0), 10).point_at_distance(i * circle.perimeter() / 4)
            for i in range(4)
        ]
        for got, want in zip(origins, expected, strict=True):
            assert (got.x, got.y) == pytest.approx((want.x, want.y), abs=1e-9)

    def test_tangent_alignment_rotates_motif(self):
        circle = Circle((0, 0), 10)
        motif = Polyline([(0, 0), (3, 0)])
        placed = along(circle, [motif], 4, align="tangent")
        first = placed[0]
        # first copy sits at the circle origin (10, 0); the CW tangent there
        # is (0, 1), so the motif's +x tip rotates to point straight down
        assert (first.points[0].x, first.points[0].y) == pytest.approx((10, 0), abs=1e-9)
        assert (first.points[1].x, first.points[1].y) == pytest.approx((10, 3), abs=1e-9)

    def test_no_align_keeps_orientation(self):
        circle = Circle((0, 0), 10)
        motif = Polyline([(0, 0), (3, 0)])
        placed = along(circle, [motif], 2, align=None)
        # translated onto the track, but not rotated
        assert placed[0].points[0] == Point(10, 0)
        assert placed[0].points[1] == Point(13, 0)

    def test_multiple_motifs_interleaved(self):
        circle = Circle((0, 0), 10)
        a = Polyline([(0, 0), (1, 0)])
        b = Polyline([(0, 0), (2, 0)])
        placed = along(circle, [a, b], 2)
        assert [p.perimeter() for p in placed] == [1, 2, 1, 2]

    def test_open_track_n1(self):
        arc = Arc((0, 0), 10, 0, 90)
        motif = Polyline([(0, 0), (1, 0)])
        placed = along(arc, [motif], 1)
        assert placed[0].points[0] == arc.start_point


class TestPolar:
    def test_places_on_circle_at_angles(self):
        motif = Polyline([(0, 0), (1, 0)])
        placed = polar((50, 50), [motif], 4, radius=20, start_deg=90)
        circle = Circle((50, 50), 20).transformed(Transform.rotate(90, about=(50, 50)))
        for got, want in zip((p.points[0] for p in placed), sample(circle, 4), strict=True):
            assert (got.x, got.y) == pytest.approx((want.x, want.y), abs=1e-9)

    def test_tangent_align(self):
        motif = Polyline([(0, 0), (5, 0)])
        placed = polar((0, 0), [motif], 1, radius=10, start_deg=0, align="tangent")
        # at the rightmost point of the circle, the CW tangent points down
        assert placed[0].points[1].y == pytest.approx(5)


class TestGrid:
    def test_grid_translations(self):
        motif = regular_polygon((0, 0), 2, 3)
        placed = grid([motif], 3, 2, dx=10, dy=5)
        assert len(placed) == 6
        assert placed[4].points[0] == motif.points[0] + Point(10, 5)

    def test_grid_validates(self):
        with pytest.raises(ValueError):
            grid([Polyline([(0, 0), (1, 0)])], 0, 2, 10, 10)
