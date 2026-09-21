"""Anchors: named positions reached by traveling a percentage of a perimeter."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Point
from .shapes import Orientation, Shape


@dataclass(frozen=True, slots=True)
class Anchor:
    """A starting location on a shape plus a travel direction.

    `point(pct)` returns the boundary point reached by traveling `pct` percent
    of the shape's full perimeter from the anchor's start, in the anchor's
    direction. Values wrap around via modulo, so `point(150)` is the same
    location as `point(50)`, and negative percentages travel the other way.
    """

    shape: Shape
    start_distance: float
    direction: Orientation

    def point(self, pct: float = 0.0) -> Point:
        signed = self.direction.mult * self.shape.winding_sign
        delta = (pct / 100.0) * self.shape.perimeter() * signed
        return self.shape.point_at_distance(self.start_distance + delta)

    def tangent(self, pct: float = 0.0) -> Point:
        """Unit vector of travel at `pct`, following the anchor's direction."""
        signed = self.direction.mult * self.shape.winding_sign
        return self.shape.tangent_at_distance(self.distance_of(pct)) * signed

    def offset(self, pct: float = 0.0, d: float = 0.0) -> Point:
        """Point at `pct` displaced perpendicular to travel by `d`.

        Positive `d` moves to the left of the travel direction, which is
        outward for clockwise tracks and inward for counter-clockwise ones.
        """
        t = self.tangent(pct)
        return self.point(pct) + Point(t.y, -t.x) * d

    def at(self, pct: float) -> Anchor:
        """A new anchor whose start is this anchor's position after traveling `pct`."""
        return Anchor(self.shape, self.distance_of(pct), self.direction)

    def distance_of(self, pct: float) -> float:
        signed = self.direction.mult * self.shape.winding_sign
        delta = (pct / 100.0) * self.shape.perimeter() * signed
        return (self.start_distance + delta) % self.shape.perimeter()
