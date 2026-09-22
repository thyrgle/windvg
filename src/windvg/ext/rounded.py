"""Rounded-corner polygons, built from exact line + arc path segments."""

from __future__ import annotations

import math

from windvg.path import Path, PathBuilder
from windvg.shapes import Polygon


def rounded(shape: Polygon, radius: float) -> Path:
    """A Path tracing the polygon with each corner replaced by a fillet arc.

    The result fills (and strokes) exactly: corners become real arc
    instructions, not polyline approximations. The radius must leave at
    least half of every edge straight.
    """
    if radius <= 0:
        raise ValueError("fillet radius must be positive")
    points = list(shape.points)
    n = len(points)
    sweep_cw = shape.winding_sign > 0
    builder: PathBuilder | None = None
    for i, corner in enumerate(points):
        incoming = points[(i - 1) % n] - corner
        outgoing = points[(i + 1) % n] - corner
        l1, l2 = incoming.length(), outgoing.length()
        if l1 == 0 or l2 == 0:
            raise ValueError("rounded polygons cannot have repeated points")
        cos_a = max(-1.0, min(1.0, incoming.dot(outgoing) / (l1 * l2)))
        alpha = math.acos(cos_a)  # angle between the edges at this corner
        cut = radius / math.tan(alpha / 2.0)
        limit = 0.5 * min(l1, l2)
        if cut > limit:
            raise ValueError(
                f"fillet radius {radius:g} does not fit corner {i}; "
                f"largest safe radius is about {limit * math.tan(alpha / 2.0):g}"
            )
        if cut < 1e-9:
            continue  # straight-through corner: no arc needed
        t_in = corner + incoming * (cut / l1)
        t_out = corner + outgoing * (cut / l2)
        if builder is None:
            builder = PathBuilder(t_in)
        else:
            builder.line_to(t_in)
        builder.arc_circle_to(radius, t_out, large=False, sweep_cw=sweep_cw)
    if builder is None:  # every corner was straight
        builder = PathBuilder(points[0])
        for pt in points[1:]:
            builder.line_to(pt)
    return builder.close().build()
