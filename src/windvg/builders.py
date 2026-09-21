"""Convenience constructors built on shapes and anchors."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .anchor import Anchor
from .geometry import Point
from .shapes import Circle, Polygon, Polyline, _as_point

AnchorLike = Anchor | tuple[Anchor, float] | Point | tuple[float, float]


def _anchor_point(item: AnchorLike) -> Point:
    if isinstance(item, Anchor):
        return item.point(0.0)
    if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], Anchor):
        anchor, pct = item
        return anchor.point(pct)
    return _as_point(item)


def regular_polygon(
    center: tuple[float, float] | Point,
    radius: float,
    sides: int,
    start_angle_deg: float = 0.0,
) -> Polygon:
    """A regular polygon inscribed in a circle, wound clockwise on screen."""
    if sides < 3:
        raise ValueError("a regular polygon needs at least 3 sides")
    center_pt = _as_point(center)
    cx, cy = center_pt.x, center_pt.y
    step = 2.0 * math.pi / sides
    start = math.radians(start_angle_deg)
    return Polygon(
        [
            Point(
                cx + radius * math.cos(start + i * step),
                cy + radius * math.sin(start + i * step),
            )
            for i in range(sides)
        ]
    )


def star(
    center: tuple[float, float] | Point,
    outer_radius: float,
    inner_radius: float,
    points: int = 5,
    start_angle_deg: float = 0.0,
) -> Polygon:
    """A classic star shape with alternating outer and inner vertices."""
    if points < 2:
        raise ValueError("a star needs at least 2 points")
    center_pt = _as_point(center)
    cx, cy = center_pt.x, center_pt.y
    step = math.pi / points
    start = math.radians(start_angle_deg)
    vertices: list[Point] = []
    for i in range(2 * points):
        radius = outer_radius if i % 2 == 0 else inner_radius
        angle = start + i * step
        vertices.append(Point(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return Polygon(vertices)


def star_polygon(circle: Circle, points: int, skip: int) -> Polygon:
    """A star drawn with the anchor system itself.

    Places `points` anchors evenly around `circle` and connects each one to the
    anchor `skip` positions along, producing shapes like the pentagram
    (`star_polygon(circle, 5, 2)`). Requires gcd(points, skip) == 1 so the
    traversal visits every anchor exactly once.
    """
    if points < 3:
        raise ValueError("a star polygon needs at least 3 points")
    if not 1 < skip < points - 1:
        raise ValueError(f"skip must be between 1 and {points - 1} exclusive")
    if math.gcd(points, skip) != 1:
        raise ValueError("gcd(points, skip) must be 1, otherwise the path splits apart")
    anchor = circle.anchor(circle.point_at_distance(0.0))
    return Polygon([anchor.point(100.0 * i * skip / points) for i in range(points)])


def polygon_from_anchors(items: Iterable[AnchorLike]) -> Polygon:
    """Build a polygon from a sequence of anchors (optionally paired with a pct)."""
    pts = [_anchor_point(item) for item in items]
    return Polygon(pts)


def connect(a: AnchorLike, b: AnchorLike) -> Polyline:
    """A straight segment between two positions, each an anchor, (anchor, pct), or point."""
    return Polyline([_anchor_point(a), _anchor_point(b)])
