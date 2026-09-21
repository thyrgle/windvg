"""Affine transforms with per-shape baking: shapes become transformed shapes.

Positive rotation angles run visually clockwise on screen (y-down), matching
every other angle convention in windvg. Baking means the result is a plain
baked shape (no scene-tree transforms to resolve at export time):

    from windvg.ext import rotated, scaled, transformed

    badge = scaled(star, 1.5, about=(100, 100))
    badge = transformed(badge, Transform.translate(20, 0))
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from windvg.geometry import Point
from windvg.shapes import Arc, Circle, Ellipse, Polygon, Polyline

if TYPE_CHECKING:
    from windvg.shapes import Shape

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class Transform:
    """A 2D affine transform: x' = a*x + c*y + e, y' = b*x + d*y + f."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @classmethod
    def identity(cls) -> Transform:
        return cls()

    @classmethod
    def translate(cls, tx: float, ty: float) -> Transform:
        return cls(e=tx, f=ty)

    @classmethod
    def rotate(
        cls, angle_deg: float, about: tuple[float, float] | Point = (0.0, 0.0)
    ) -> Transform:
        """Rotation clockwise on screen for positive angles, around `about`."""
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        rotation = cls(a=cos_a, b=sin_a, c=-sin_a, d=cos_a)
        if about != (0.0, 0.0):
            return cls.translate(*about) @ rotation @ cls.translate(-about[0], -about[1])
        return rotation

    @classmethod
    def scale(
        cls,
        sx: float,
        sy: float | None = None,
        about: tuple[float, float] | Point = (0.0, 0.0),
    ) -> Transform:
        if sy is None:
            sy = sx
        scaling = cls(a=sx, d=sy)
        if about != (0.0, 0.0):
            return cls.translate(*about) @ scaling @ cls.translate(-about[0], -about[1])
        return scaling

    @classmethod
    def mirror_x(cls, axis: float = 0.0) -> Transform:
        """Reflect across the vertical line x = axis."""
        return cls(a=-1.0, e=2.0 * axis)

    @classmethod
    def mirror_y(cls, axis: float = 0.0) -> Transform:
        """Reflect across the horizontal line y = axis."""
        return cls(d=-1.0, f=2.0 * axis)

    def __matmul__(self, other: Transform) -> Transform:
        """Compose: (self @ other) applies `other` first, then `self`."""
        return Transform(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, pt: Point) -> Point:
        return Point(
            self.a * pt.x + self.c * pt.y + self.e,
            self.b * pt.x + self.d * pt.y + self.f,
        )

    def __call__(self, pt: Point) -> Point:
        return self.apply(pt)

    @property
    def determinant(self) -> float:
        return self.a * self.d - self.b * self.c

    @property
    def is_similarity(self) -> bool:
        """True for uniform scale + rotation + translation (angle-preserving)."""
        cross_term = abs(self.a * self.c + self.b * self.d) < _EPS
        norm_x = self.a * self.a + self.b * self.b
        norm_y = self.c * self.c + self.d * self.d
        scales_equal = abs(norm_x - norm_y) < _EPS
        return cross_term and scales_equal and abs(self.determinant) > _EPS

    @property
    def scale_factor(self) -> float:
        return math.sqrt(self.a * self.a + self.b * self.b)


def _ellipse_from_linear(a: float, b: float, c: float, d: float, center: Point) -> Ellipse:
    """The ellipse that the linear map [[a, c], [b, d]] makes from the unit circle.

    Semi-axes are the singular values, axes directions the eigenvectors of
    the map's Gram matrix; rotation is the major-axis direction in y-down
    degrees (visually clockwise from +x).
    """
    g00, g01, g11 = a * a + c * c, a * b + c * d, b * b + d * d
    mean = (g00 + g11) / 2.0
    radius = math.hypot((g00 - g11) / 2.0, g01)
    rotation_deg = math.degrees(math.atan2(2.0 * g01, g00 - g11) / 2.0)
    return Ellipse(center, math.sqrt(mean + radius), math.sqrt(mean - radius), rotation_deg)


def transformed(shape: Shape, t: Transform) -> Shape:
    """Bake an affine transform into a new shape."""
    if isinstance(shape, Polygon):
        return Polygon([t.apply(p) for p in shape.points])
    if isinstance(shape, Polyline):
        return Polyline([t.apply(p) for p in shape.points])
    if isinstance(shape, Circle):
        center = t.apply(shape.center)
        if t.is_similarity:
            return Circle(center, shape.radius * t.scale_factor)
        r = shape.radius
        return _ellipse_from_linear(t.a * r, t.b * r, t.c * r, t.d * r, center)
    if isinstance(shape, Ellipse):
        local = Transform(
            a=shape.rx * math.cos(math.radians(shape.rotation_deg)),
            b=shape.rx * math.sin(math.radians(shape.rotation_deg)),
            c=-shape.ry * math.sin(math.radians(shape.rotation_deg)),
            d=shape.ry * math.cos(math.radians(shape.rotation_deg)),
        )
        e = t @ local
        return _ellipse_from_linear(e.a, e.b, e.c, e.d, t.apply(shape.center))
    if isinstance(shape, Arc):
        center = t.apply(shape.center)
        if not t.is_similarity:
            raise NotImplementedError(
                "affine-warped arcs become elliptical arcs; bake them once Path exists"
            )
        start = t.apply(shape.start_point)
        start_deg = math.degrees(math.atan2(start.y - center.y, start.x - center.x))
        sweep = shape.sweep_deg * (1.0 if t.determinant > 0 else -1.0)
        return Arc(center, shape.radius * t.scale_factor, start_deg, sweep)
    raise TypeError(f"cannot transform {type(shape).__name__}")


def translated(shape: Shape, dx: float, dy: float) -> Shape:
    return transformed(shape, Transform.translate(dx, dy))


def rotated(
    shape: Shape, angle_deg: float, about: tuple[float, float] | Point = (0.0, 0.0)
) -> Shape:
    return transformed(shape, Transform.rotate(angle_deg, about))


def scaled(
    shape: Shape,
    sx: float,
    sy: float | None = None,
    about: tuple[float, float] | Point = (0.0, 0.0),
) -> Shape:
    return transformed(shape, Transform.scale(sx, sy, about))


def mirrored_x(shape: Shape, axis: float = 0.0) -> Shape:
    return transformed(shape, Transform.mirror_x(axis))


def mirrored_y(shape: Shape, axis: float = 0.0) -> Shape:
    return transformed(shape, Transform.mirror_y(axis))
