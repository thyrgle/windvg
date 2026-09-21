"""Repetition: place motif shapes along tracks, circles, and grids.

A motif is a sequence of shapes built around the origin, typically pointing
along +x. Placement bakes a transform per copy, so results are plain shapes
ready for `scene.fill` / `scene.stroke`:

    petal = windvg.Ellipse((0, -20), 12, 20)   # built pointing up from origin
    for placed in along(circle, [petal], 8, align="tangent"):
        scene.fill(placed, color)
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from windvg.ext.transform import Transform, transformed
from windvg.geometry import Point
from windvg.shapes import Circle, Orientation, Shape

Motifs = Sequence[Shape]


def _spacing(shape, n: int) -> float:
    """Percent step between placements: loops divide evenly, open tracks span end to end."""
    if n < 2:
        return 100.0
    return 100.0 / n if shape.closed else 100.0 / (n - 1)


def sample(
    shape,
    n: int,
    offset_pct: float = 0.0,
    direction: Orientation = Orientation.CW,
) -> list[Point]:
    """n evenly spaced points along the shape's track.

    Closed tracks place points i*100/n apart (the last point is not the first
    point again); open tracks include both endpoints.
    """
    if n < 1:
        raise ValueError("sample needs at least 1 point")
    anchor = shape.anchor(shape.point_at_distance(0.0), direction)
    step = _spacing(shape, n)
    return [anchor.point(offset_pct + i * step) for i in range(n)]


def along(
    track,
    motifs: Motifs,
    n: int,
    offset_pct: float = 0.0,
    align: str | None = "tangent",
    direction: Orientation = Orientation.CW,
) -> list[Shape]:
    """Place the motifs n times around the track.

    With ``align="tangent"`` each copy is rotated so its +x axis follows the
    track's travel direction; with ``align=None`` copies keep their original
    orientation.
    """
    anchor = track.anchor(track.point_at_distance(0.0), direction)
    step = _spacing(track, n)
    placed: list[Shape] = []
    for i in range(n):
        pct = offset_pct + i * step
        origin = anchor.point(pct)
        placement = Transform.translate(origin.x, origin.y)
        if align == "tangent":
            tangent = anchor.tangent(pct)
            placement @= Transform.rotate(math.degrees(math.atan2(tangent.y, tangent.x)))
        elif align is not None:
            raise ValueError("align must be 'tangent' or None")
        placed.extend(motif.transformed(placement) for motif in motifs)
    return placed


def polar(
    center: tuple[float, float] | Point,
    motifs: Motifs,
    n: int,
    radius: float,
    start_deg: float = 0.0,
    align: str | None = None,
) -> list[Shape]:
    """Place the motifs n times on a circle around `center`."""
    circle = Circle(center, radius)
    if start_deg:
        circle = transformed(circle, Transform.rotate(start_deg, about=center))
    return along(circle, motifs, n, align=align)


def grid(
    motifs: Motifs,
    cols: int,
    rows: int,
    dx: float,
    dy: float,
    origin: tuple[float, float] | Point = (0.0, 0.0),
) -> list[Shape]:
    """Place the motifs on a cols x rows lattice with spacing dx, dy."""
    if cols < 1 or rows < 1:
        raise ValueError("grid needs at least 1 column and 1 row")
    ox, oy = (origin.x, origin.y) if isinstance(origin, Point) else origin
    placed: list[Shape] = []
    for row in range(rows):
        for col in range(cols):
            placement = Transform.translate(ox + col * dx, oy + row * dy)
            placed.extend(motif.transformed(placement) for motif in motifs)
    return placed
