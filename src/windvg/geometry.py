"""Minimal 2D vector geometry primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    """A 2D point in screen space (x right, y down), matching TinyVG/SVG coordinates."""

    x: float
    y: float

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point:
        return Point(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def distance_to(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def dot(self, other: Point) -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def lerp(self, other: Point, t: float) -> Point:
        """Linear interpolation between self (t=0) and other (t=1)."""
        return self + (other - self) * t

    def rotated(self, angle_rad: float, about: Point) -> Point:
        """Rotate by angle_rad around `about`.

        Positive angles rotate clockwise on screen (y-down coordinates).
        """
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        dx, dy = self.x - about.x, self.y - about.y
        return Point(
            about.x + dx * c - dy * s,
            about.y + dx * s + dy * c,
        )


def cross(a: Point, b: Point) -> float:
    """2D cross product (z component).

    Positive in y-down screen space means the turn from `a` to `b` is a
    right turn, i.e. visually clockwise.
    """
    return a.x * b.y - a.y * b.x
