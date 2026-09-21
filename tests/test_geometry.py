import math

import pytest

from windvg import Point


def test_point_distance_and_lerp():
    a, b = Point(0, 0), Point(3, 4)
    assert a.distance_to(b) == 5
    assert a.lerp(b, 0.5) == Point(1.5, 2.0)
    assert a.lerp(b, 1.0) == b


def test_dot():
    assert Point(1, 2).dot(Point(3, 4)) == 11


def test_rotated_positive_is_clockwise_on_screen():
    # y is down: rotating (1, 0) by +90 degrees should land on (0, 1), i.e. below.
    result = Point(1, 0).rotated(math.pi / 2, Point(0, 0))
    assert result.x == pytest.approx(0, abs=1e-9)
    assert result.y == pytest.approx(1, abs=1e-9)
