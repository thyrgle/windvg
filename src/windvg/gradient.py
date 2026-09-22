"""Gradient paints: TinyVG's two-point linear and radial fills.

A gradient is used anywhere a Color is, and its endpoint colors join the
file's color table like any other. Points are absolute canvas coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import Color
from .geometry import Point
from .shapes import _as_point


@dataclass(frozen=True, slots=True)
class LinearGradient:
    """Color ramp along the line from `start` to `end`.

    Points project orthogonally onto the ramp line; the end colors hold
    beyond it.
    """

    start: Point
    end: Point
    start_color: Color
    end_color: Color

    def __init__(
        self,
        start: tuple[float, float] | Point,
        end: tuple[float, float] | Point,
        start_color: Color,
        end_color: Color,
    ):
        object.__setattr__(self, "start", _as_point(start))
        object.__setattr__(self, "end", _as_point(end))
        object.__setattr__(self, "start_color", start_color)
        object.__setattr__(self, "end_color", end_color)


@dataclass(frozen=True, slots=True)
class RadialGradient:
    """Color ramp from `center` out to `edge` (a point on the radius circle).

    Samples inside the circle interpolate toward `edge_color`; samples beyond
    it take `edge_color`.
    """

    center: Point
    edge: Point
    center_color: Color
    edge_color: Color

    def __init__(
        self,
        center: tuple[float, float] | Point,
        edge: tuple[float, float] | Point,
        center_color: Color,
        edge_color: Color,
    ):
        object.__setattr__(self, "center", _as_point(center))
        object.__setattr__(self, "edge", _as_point(edge))
        object.__setattr__(self, "center_color", center_color)
        object.__setattr__(self, "edge_color", edge_color)


Paint = Color | LinearGradient | RadialGradient


def paint_colors(paint: Paint) -> list[Color]:
    """The colors a paint contributes to the color table, in ramp order."""
    if isinstance(paint, Color):
        return [paint]
    if isinstance(paint, LinearGradient):
        return [paint.start_color, paint.end_color]
    if isinstance(paint, RadialGradient):
        return [paint.center_color, paint.edge_color]
    raise TypeError(f"unknown paint {type(paint).__name__}")
