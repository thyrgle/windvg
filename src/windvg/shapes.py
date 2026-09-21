"""Core drawable shapes: polygons, circles, and open polylines.

Every shape exposes an arc-length parameterization: `point_at_distance(d)`
returns the boundary point at distance `d` measured from the shape's origin
*in its positive direction*, which is defined as visually clockwise on screen
(y-down coordinates, matching TinyVG and SVG).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from .geometry import Point, cross


class Orientation(Enum):
    """Traversal direction around a shape, in screen space (y is down).

    CW is visually clockwise on screen; CCW is counter-clockwise.
    """

    CW = 1
    CCW = -1

    @property
    def mult(self) -> int:
        return self.value


CW = Orientation.CW
CCW = Orientation.CCW


def _as_point(pt: tuple[float, float] | Point) -> Point:
    return pt if isinstance(pt, Point) else Point(*pt)


def _closed_pairs(points: tuple[Point, ...]) -> Iterator[tuple[Point, Point]]:
    n = len(points)
    return ((points[i], points[(i + 1) % n]) for i in range(n))


def _open_pairs(points: tuple[Point, ...]) -> Iterator[tuple[Point, Point]]:
    return zip(points, points[1:], strict=False)


def _chain_length(pairs: Iterator[tuple[Point, Point]]) -> float:
    return sum(a.distance_to(b) for a, b in pairs)


def _point_on_chain(
    points: tuple[Point, ...], pairs: Iterator[tuple[Point, Point]], d: float
) -> Point:
    for a, b in pairs:
        seg = a.distance_to(b)
        if d <= seg:
            return a if seg == 0 else a.lerp(b, d / seg)
        d -= seg
    return points[-1]


def _project_on_chain(pairs: Iterator[tuple[Point, Point]], pt: Point) -> float:
    best_dist, best_pos = math.inf, 0.0
    traveled = 0.0
    for a, b in pairs:
        seg = b - a
        seg_len = seg.length()
        t = 0.0 if seg_len == 0 else max(0.0, min(1.0, (pt - a).dot(seg) / seg_len**2))
        dist = (a + seg * t).distance_to(pt)
        if dist < best_dist:
            best_dist, best_pos = dist, traveled + t * seg_len
        traveled += seg_len
    return best_pos


class Shape(ABC):
    """A shape whose boundary is a 1D track that anchors can travel along."""

    @abstractmethod
    def perimeter(self) -> float:
        """Total length of the boundary."""

    @abstractmethod
    def point_at_distance(self, d: float) -> Point:
        """Point at arc-length distance `d` from the shape origin.

        `d` is measured along the positive (visually clockwise) direction and
        wraps around the perimeter via modulo.
        """

    @abstractmethod
    def project(self, pt: Point) -> float:
        """Arc-length position (0..perimeter) of the boundary point nearest to `pt`."""

    @property
    @abstractmethod
    def winding_sign(self) -> int:
        """+1 if the shape's natural parameterization runs visually clockwise."""

    @property
    def fillable(self) -> bool:
        return True

    def anchor(self, start: tuple[float, float] | Point, direction: Orientation = CW):
        """Create an anchor on this shape.

        The start point (any x, y) is projected to the nearest location on the
        boundary; from there anchors travel by a percentage of the perimeter.
        """
        from .anchor import Anchor

        return Anchor(self, self.project(_as_point(start)), direction)


@dataclass(frozen=True, slots=True)
class Polygon(Shape):
    """A closed polygon defined by its vertices in traversal order."""

    points: tuple[Point, ...]

    def __init__(self, points: list[Point] | tuple[Point, ...]):
        pts = tuple(_as_point(p) for p in points)
        if len(pts) < 3:
            raise ValueError("a polygon needs at least 3 points")
        if self._shoelace(pts) == 0:
            raise ValueError("degenerate polygon (zero signed area)")
        object.__setattr__(self, "points", pts)

    @staticmethod
    def _shoelace(pts: tuple[Point, ...]) -> float:
        return sum(cross(a, b) for a, b in _closed_pairs(pts)) / 2.0

    def perimeter(self) -> float:
        return _chain_length(_closed_pairs(self.points))

    def point_at_distance(self, d: float) -> Point:
        pairs = _closed_pairs(self.points)
        return _point_on_chain(self.points, pairs, d % self.perimeter())

    def project(self, pt: Point) -> float:
        return _project_on_chain(_closed_pairs(self.points), pt)

    @property
    def winding_sign(self) -> int:
        return 1 if self._shoelace(self.points) > 0 else -1


@dataclass(frozen=True, slots=True)
class Circle(Shape):
    """A circle; its origin is the rightmost point (angle 0)."""

    center: Point
    radius: float

    def __init__(self, center: tuple[float, float] | Point, radius: float):
        if radius <= 0:
            raise ValueError("circle radius must be positive")
        object.__setattr__(self, "center", _as_point(center))
        object.__setattr__(self, "radius", float(radius))

    def perimeter(self) -> float:
        return 2.0 * math.pi * self.radius

    def point_at_distance(self, d: float) -> Point:
        angle = (d / self.radius) % (2.0 * math.pi)
        return Point(
            self.center.x + self.radius * math.cos(angle),
            self.center.y + self.radius * math.sin(angle),
        )

    def project(self, pt: Point) -> float:
        delta = pt - self.center
        if delta.length() == 0:
            return 0.0
        return (math.atan2(delta.y, delta.x) % (2.0 * math.pi)) * self.radius

    @property
    def winding_sign(self) -> int:
        # Increasing angle in y-down coordinates runs visually clockwise.
        return 1


@dataclass(frozen=True, slots=True)
class Polyline(Shape):
    """An open chain of points.

    Strokable but not fillable. Its positive direction is the order the points
    were given, so CW means forward along the chain and CCW means backward.
    """

    points: tuple[Point, ...]

    def __init__(self, points: list[Point] | tuple[Point, ...]):
        pts = tuple(_as_point(p) for p in points)
        if len(pts) < 2:
            raise ValueError("a polyline needs at least 2 points")
        object.__setattr__(self, "points", pts)

    def perimeter(self) -> float:
        return _chain_length(_open_pairs(self.points))

    def point_at_distance(self, d: float) -> Point:
        return _point_on_chain(self.points, _open_pairs(self.points), d % self.perimeter())

    def project(self, pt: Point) -> float:
        return _project_on_chain(_open_pairs(self.points), pt)

    @property
    def winding_sign(self) -> int:
        return 1

    @property
    def fillable(self) -> bool:
        return False
