"""Core drawable shapes: polygons, circles, ellipses, arcs, and polylines.

Every shape exposes an arc-length parameterization: `point_at_distance(d)`
returns the boundary point at distance `d` measured from the shape's origin
*in its positive direction*, which is defined as visually clockwise on screen
(y-down coordinates, matching TinyVG and SVG). `tangent_at_distance(d)` is the
unit vector of travel at that position.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum

from .arclength import ArcLengthTable
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


def _tangent_on_chain(
    points: tuple[Point, ...], pairs: Iterator[tuple[Point, Point]], d: float
) -> Point:
    for a, b in pairs:
        seg_len = a.distance_to(b)
        if d <= seg_len:
            seg = b - a
            return seg * (1.0 / seg_len) if seg_len > 0 else Point(1.0, 0.0)
        d -= seg_len
    return Point(1.0, 0.0)


class Shape(ABC):
    """A shape whose boundary is a 1D track that anchors can travel along."""

    @abstractmethod
    def perimeter(self) -> float:
        """Total length of the boundary."""

    @abstractmethod
    def point_at_distance(self, d: float) -> Point:
        """Point at arc-length distance `d` from the shape origin.

        `d` is measured along the positive (visually clockwise) direction.
        Closed tracks wrap via modulo; open tracks (Polyline, Arc) clamp to
        [0, perimeter].
        """

    @abstractmethod
    def tangent_at_distance(self, d: float) -> Point:
        """Unit tangent at arc-length `d`, along the positive travel direction."""

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

    @property
    def closed(self) -> bool:
        """Whether the track loops: closed tracks wrap distances, open ones clamp."""
        return True

    def anchor(self, start: tuple[float, float] | Point, direction: Orientation = CW):
        """Create an anchor on this shape.

        The start point (any x, y) is projected to the nearest location on the
        boundary; from there anchors travel by a percentage of the perimeter.
        """
        from .anchor import Anchor

        return Anchor(self, self.project(_as_point(start)), direction)

    def transformed(self, t):
        """A new shape with the affine transform `t` baked in.

        `t` is a windvg.ext.transform.Transform; see that module for details.
        """
        from .ext.transform import transformed

        return transformed(self, t)


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

    def tangent_at_distance(self, d: float) -> Point:
        pairs = _closed_pairs(self.points)
        return _tangent_on_chain(self.points, pairs, d % self.perimeter())

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

    def tangent_at_distance(self, d: float) -> Point:
        angle = (d / self.radius) % (2.0 * math.pi)
        return Point(-math.sin(angle), math.cos(angle))

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
class Ellipse(Shape):
    """A rotated ellipse; its origin is the point at parameter 0.

    Parameter 0 lies along the local +x axis (`rx`), rotated by
    `rotation_deg` clockwise on screen. Track parameters run visually
    clockwise; arc lengths come from a dense chordal table.
    """

    center: Point
    rx: float
    ry: float
    rotation_deg: float = 0.0
    _table: ArcLengthTable = field(init=False, repr=False, compare=False)

    def __init__(
        self, center: tuple[float, float] | Point, rx: float, ry: float,
        rotation_deg: float = 0.0,
    ):
        if rx <= 0 or ry <= 0:
            raise ValueError("ellipse radii must be positive")
        object.__setattr__(self, "center", _as_point(center))
        object.__setattr__(self, "rx", float(rx))
        object.__setattr__(self, "ry", float(ry))
        object.__setattr__(self, "rotation_deg", float(rotation_deg))
        table = ArcLengthTable(0.0, 2.0 * math.pi, self.point_at_param)
        object.__setattr__(self, "_table", table)

    def point_at_param(self, t: float) -> Point:
        """Point at curve parameter t (radians of the unrotated parameterization)."""
        rot = math.radians(self.rotation_deg)
        c, s = math.cos(rot), math.sin(rot)
        u = self.rx * math.cos(t)
        v = self.ry * math.sin(t)
        return Point(self.center.x + u * c - v * s, self.center.y + u * s + v * c)

    def perimeter(self) -> float:
        return self._table.total

    def point_at_distance(self, d: float) -> Point:
        return self.point_at_param(self._table.distance_to_param(d % self.perimeter()))

    def tangent_at_distance(self, d: float) -> Point:
        t = self._table.distance_to_param(d % self.perimeter())
        rot = math.radians(self.rotation_deg)
        c, s = math.cos(rot), math.sin(rot)
        dx = -self.rx * math.sin(t)
        dy = self.ry * math.cos(t)
        vx, vy = dx * c - dy * s, dx * s + dy * c
        norm = math.hypot(vx, vy)
        return Point(vx / norm, vy / norm)

    def project(self, pt: Point) -> float:
        table = self._table
        best_i = min(
            range(len(table.params)),
            key=lambda i: self.point_at_param(table.params[i]).distance_to(pt),
        )
        # refine around the best sample with a ternary search on distance
        step = table.params[1] - table.params[0]
        lo = table.params[max(0, best_i - 1)]
        hi = table.params[min(len(table.params) - 1, best_i + 1)]
        if hi - lo > step:  # best was an endpoint sample
            hi = lo + step if best_i == 0 else hi
            lo = hi - step if best_i == len(table.params) - 1 else lo
        for _ in range(48):
            m1, m2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
            d1 = self.point_at_param(m1).distance_to(pt)
            d2 = self.point_at_param(m2).distance_to(pt)
            if d1 <= d2:
                hi = m2
            else:
                lo = m1
        t = (lo + hi) / 2.0 % (2.0 * math.pi)
        return table.param_to_distance(t)

    @property
    def winding_sign(self) -> int:
        # Increasing parameter in y-down coordinates runs visually clockwise.
        return 1


@dataclass(frozen=True, slots=True)
class Arc(Shape):
    """A partial circle, stroke-only (combine with `to_pie`/`to_chord` later
    for fillable wedges once Path exists).

    The track starts at `start_deg` and travels `sweep_deg` degrees; positive
    sweeps run visually clockwise on screen. As an open track, travel beyond
    its ends clamps to the endpoints.
    """

    center: Point
    radius: float
    start_deg: float
    sweep_deg: float

    def __init__(
        self,
        center: tuple[float, float] | Point,
        radius: float,
        start_deg: float,
        sweep_deg: float,
    ):
        if radius <= 0:
            raise ValueError("arc radius must be positive")
        if not 0 < abs(sweep_deg) < 360:
            raise ValueError("arc sweep must be strictly within +-360 degrees; use Circle")
        object.__setattr__(self, "center", _as_point(center))
        object.__setattr__(self, "radius", float(radius))
        object.__setattr__(self, "start_deg", float(start_deg))
        object.__setattr__(self, "sweep_deg", float(sweep_deg))

    def point_at_deg(self, deg: float) -> Point:
        rad = math.radians(deg)
        return Point(
            self.center.x + self.radius * math.cos(rad),
            self.center.y + self.radius * math.sin(rad),
        )

    @property
    def end_deg(self) -> float:
        return self.start_deg + self.sweep_deg

    @property
    def start_point(self) -> Point:
        return self.point_at_deg(self.start_deg)

    @property
    def end_point(self) -> Point:
        return self.point_at_deg(self.end_deg)

    def perimeter(self) -> float:
        return abs(self.sweep_deg) / 360.0 * 2.0 * math.pi * self.radius

    def point_at_distance(self, d: float) -> Point:
        frac = max(0.0, min(1.0, d / self.perimeter()))
        return self.point_at_deg(self.start_deg + self.sweep_deg * frac)

    def tangent_at_distance(self, d: float) -> Point:
        frac = max(0.0, min(1.0, d / self.perimeter()))
        rad = math.radians(self.start_deg + self.sweep_deg * frac)
        if self.sweep_deg > 0:
            return Point(-math.sin(rad), math.cos(rad))
        return Point(math.sin(rad), -math.cos(rad))

    def project(self, pt: Point) -> float:
        delta = pt - self.center
        if delta.length() == 0:
            return 0.0
        phi = (math.degrees(math.atan2(delta.y, delta.x)) - self.start_deg) % 360.0
        sweep = self.sweep_deg
        if sweep >= 0:
            travel = phi if phi <= sweep else (0.0 if phi < 360.0 - sweep / 2.0 else sweep)
        else:
            phi_ccw = (360.0 - phi) % 360.0
            span = -sweep
            near_start = phi_ccw < 360.0 - span / 2
            travel = phi_ccw if phi_ccw <= span else (0.0 if near_start else span)
        return abs(travel) / abs(self.sweep_deg) * self.perimeter()

    @property
    def winding_sign(self) -> int:
        return 1 if self.sweep_deg > 0 else -1

    @property
    def fillable(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Polyline(Shape):
    """An open chain of points.

    Strokable but not fillable. Its positive direction is the order the points
    were given, so CW means forward along the chain and CCW means backward.
    Unlike closed tracks, travel does not wrap: distances outside
    [0, perimeter] clamp to the nearer endpoint.
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
        pairs = _open_pairs(self.points)
        return _point_on_chain(self.points, pairs, max(0.0, min(self.perimeter(), d)))

    def tangent_at_distance(self, d: float) -> Point:
        pairs = _open_pairs(self.points)
        return _tangent_on_chain(self.points, pairs, max(0.0, min(self.perimeter(), d)))

    def project(self, pt: Point) -> float:
        return _project_on_chain(_open_pairs(self.points), pt)

    @property
    def winding_sign(self) -> int:
        return 1

    @property
    def fillable(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Compound(Shape):
    """Several closed shapes filled together under the even-odd rule.

    An inner shape carves a hole out of an outer one. Fill and stroke work;
    outline fills and track queries are not meaningful and raise.
    """

    shapes: tuple[Shape, ...]

    def __init__(self, shapes: Sequence[Shape]):
        subs = tuple(shapes)
        if not subs:
            raise ValueError("a compound needs at least one shape")
        for sub in subs:
            if not sub.fillable:
                raise ValueError(f"{type(sub).__name__} is not fillable; no compound")
        object.__setattr__(self, "shapes", subs)

    def perimeter(self) -> float:
        return sum(sub.perimeter() for sub in self.shapes)

    def point_at_distance(self, d: float) -> Point:
        raise NotImplementedError("a Compound has no single track")

    def tangent_at_distance(self, d: float) -> Point:
        raise NotImplementedError("a Compound has no single track")

    def project(self, pt: Point) -> float:
        raise NotImplementedError("a Compound has no single track")

    @property
    def winding_sign(self) -> int:
        return 1

    @property
    def closed(self) -> bool:
        return True
