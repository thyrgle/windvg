import pytest
from conftest import assert_pt

from windvg import Arc, Circle, Ellipse, Point, regular_polygon
from windvg.ext import Transform, mirrored_x, scaled, transformed, translated


def assert_points_on_boundary(original, t, result, samples=64):
    """Every mapped boundary point of `original` must lie on `result`."""
    for i in range(samples):
        pt = original.point_at_distance(i * original.perimeter() / samples)
        mapped = t.apply(pt)
        d = result.project(mapped)
        assert result.point_at_distance(d).distance_to(mapped) == pytest.approx(0, abs=0.01)


class TestTransformMatrix:
    def test_apply_and_compose_order(self):
        t = Transform.translate(10, 0) @ Transform.rotate(90)
        # rotate first (1,0)->(0,1), then translate -> (10, 1)
        assert_pt(t.apply(Point(1, 0)), (10, 1))

    def test_rotate_positive_is_clockwise_on_screen(self):
        assert_pt(Transform.rotate(90).apply(Point(1, 0)), (0, 1))

    def test_rotate_about(self):
        t = Transform.rotate(90, about=(10, 0))
        assert_pt(t.apply(Point(20, 0)), (10, 10))  # swings the east point down

    def test_scale_about(self):
        t = Transform.scale(2, about=(10, 10))
        assert_pt(t.apply(Point(10, 10)), (10, 10))  # pinned
        assert_pt(t.apply(Point(15, 10)), (20, 10))

    def test_mirror(self):
        assert_pt(Transform.mirror_x(5).apply(Point(8, 3)), (2, 3))
        assert_pt(Transform.mirror_y(1).apply(Point(8, 3)), (8, -1))

    def test_determinant_and_similarity(self):
        assert Transform.rotate(33).determinant == pytest.approx(1)
        assert Transform.scale(2, 3).determinant == pytest.approx(6)
        assert Transform.mirror_x().determinant == pytest.approx(-1)
        assert Transform.rotate(17, about=(4, 4)).is_similarity
        assert not Transform.scale(2, 3).is_similarity
        assert Transform.scale(2, 2).is_similarity


class TestBaking:
    def test_polygon_translate_and_mirror_flips_winding(self):
        square = regular_polygon((0, 0), 10, 4)
        moved = translated(square, 100, 50)
        assert moved.winding_sign == square.winding_sign
        flipped = mirrored_x(square)
        assert flipped.winding_sign == -square.winding_sign
        assert flipped.perimeter() == pytest.approx(square.perimeter())

    def test_circle_similarity_stays_circle(self):
        circle = Circle((10, 10), 5)
        # compose applies translate first, then rotate
        t = Transform.rotate(45, about=(0, 0)) @ Transform.translate(20, 0)
        result = transformed(circle, t)
        assert isinstance(result, Circle)
        assert result.radius == pytest.approx(5)
        expected = t.apply(circle.center)
        assert_pt(result.center, (expected.x, expected.y))

    def test_circle_non_uniform_scale_becomes_ellipse(self):
        circle = Circle((0, 0), 10)
        result = scaled(circle, 2, 1)
        assert isinstance(result, Ellipse)
        assert result.rx == pytest.approx(20)
        assert result.ry == pytest.approx(10)
        assert result.rotation_deg == pytest.approx(0, abs=1e-9)
        assert_points_on_boundary(circle, Transform.scale(2, 1), result)

    def test_rotated_ellipse_composes(self):
        ellipse = Ellipse((0, 0), 30, 10, rotation_deg=30)
        t = Transform.rotate(60) @ Transform.translate(100, 100)
        result = transformed(ellipse, t)
        assert isinstance(result, Ellipse)
        assert result.rotation_deg == pytest.approx(90, abs=1e-9)
        assert result.rx == pytest.approx(30)
        assert result.ry == pytest.approx(10)
        assert_points_on_boundary(ellipse, t, result)

    def test_ellipse_general_affine(self):
        ellipse = Ellipse((0, 0), 30, 10, rotation_deg=25)
        t = Transform.rotate(10) @ Transform.scale(1.5, 0.8) @ Transform.translate(5, 7)
        result = transformed(ellipse, t)
        assert isinstance(result, Ellipse)
        assert_points_on_boundary(ellipse, t, result)

    def test_arc_similarity_preserves_sweep(self):
        arc = Arc((0, 0), 20, 10, 90)
        result = transformed(arc, Transform.rotate(45, about=(10, 10)))
        assert isinstance(result, Arc)
        assert result.sweep_deg == pytest.approx(90)
        assert result.radius == pytest.approx(20)
        assert result.start_deg == pytest.approx(55)
        # the mapped start point is on the new arc
        start = result.point_at_distance(0)
        mapped = Transform.rotate(45, about=(10, 10)).apply(arc.point_at_distance(0))
        assert start.distance_to(mapped) == pytest.approx(0, abs=1e-9)

    def test_mirror_flips_arc_direction(self):
        arc = Arc((0, 0), 20, 0, 90)
        result = mirrored_x(arc)
        assert result.sweep_deg == pytest.approx(-90)
        # the start point (20, 0) mirrors to (-20, 0), i.e. angle 180
        assert result.start_deg == pytest.approx(180)

    def test_arc_non_similarity_becomes_ellipse_path(self):
        arc = Arc((0, 0), 20, 0, 90)
        t = Transform.scale(2, 1)
        result = scaled(arc, 2, 1)
        # a warped arc is an exact elliptical-arc path now
        assert type(result).__name__ == "Path"
        (instr,) = result.subpaths[0].instructions
        assert type(instr).__name__ == "ArcEllipse"
        assert instr.rx == pytest.approx(40)  # x axis stretched
        assert instr.ry == pytest.approx(20)
        # endpoints map exactly
        start, end = t.apply(arc.start_point), t.apply(arc.end_point)
        assert (result.subpaths[0].start.x, result.subpaths[0].start.y) == pytest.approx(
            (start.x, start.y), abs=1e-9
        )
        assert (instr.to.x, instr.to.y) == pytest.approx((end.x, end.y), abs=1e-9)

    def test_shape_method_dispatch(self):
        square = regular_polygon((0, 0), 10, 4)
        moved = square.transformed(Transform.translate(5, 5))
        assert moved.points[0] == square.points[0] + Point(5, 5)
