"""Minimal SVG exporter: the same scene rendered as simple SVG shapes.

Useful as a human-readable preview and for checking geometry in a browser;
TinyVG remains the primary output format.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .geometry import Point
from .path import ArcCircle, ArcEllipse, Close, Cubic, Line, Path, Quad
from .scene import FillOp, OutlineFillOp, StrokeOp
from .shapes import Arc, Circle, Compound, Ellipse, Polyline

if TYPE_CHECKING:
    from .color import Color
    from .scene import Op, Scene


def _fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def _points_attr(points) -> str:
    return " ".join(f"{_fmt(p.x)},{_fmt(p.y)}" for p in points)


def _fill_attrs(color: Color) -> str:
    attrs = f'fill="{color.hex_rgb()}"'
    if color.a < 1.0:
        attrs += f' fill-opacity="{color.a:.3f}"'
    return attrs


def _stroke_attrs(color: Color, width: float) -> str:
    attrs = (
        f'stroke="{color.hex_rgb()}" stroke-width="{_fmt(width)}"'
        ' stroke-linecap="round" stroke-linejoin="round"'
    )
    if color.a < 1.0:
        attrs += f' stroke-opacity="{color.a:.3f}"'
    return attrs


def _arc_flags(large: bool, sweep_cw: bool) -> tuple[int, int]:
    # SVG: large-arc flag as-is; sweep flag 1 = positive angle = CW on screen
    return (1 if large else 0), (1 if sweep_cw else 0)


def _shape_to_d(shape) -> str:
    """Path-data fragment for one closed shape (Polygon/Circle/Ellipse/Path)."""
    if isinstance(shape, Path):
        parts = []
        for sub in shape.subpaths:
            parts.append(f"M {_fmt(sub.start.x)} {_fmt(sub.start.y)}")
            for instr in sub.instructions:
                if isinstance(instr, Line):
                    parts.append(f"L {_fmt(instr.to.x)} {_fmt(instr.to.y)}")
                elif isinstance(instr, Quad):
                    parts.append(
                        f"Q {_fmt(instr.ctrl.x)} {_fmt(instr.ctrl.y)}"
                        f" {_fmt(instr.to.x)} {_fmt(instr.to.y)}"
                    )
                elif isinstance(instr, Cubic):
                    parts.append(
                        f"C {_fmt(instr.c1.x)} {_fmt(instr.c1.y)}"
                        f" {_fmt(instr.c2.x)} {_fmt(instr.c2.y)}"
                        f" {_fmt(instr.to.x)} {_fmt(instr.to.y)}"
                    )
                elif isinstance(instr, (ArcCircle, ArcEllipse)):
                    rx = instr.radius if isinstance(instr, ArcCircle) else instr.rx
                    ry = instr.radius if isinstance(instr, ArcCircle) else instr.ry
                    rot = 0 if isinstance(instr, ArcCircle) else instr.rotation_deg
                    large, sweep = _arc_flags(instr.large, instr.sweep_cw)
                    parts.append(
                        f"A {_fmt(rx)} {_fmt(ry)} {_fmt(rot)} {large} {sweep}"
                        f" {_fmt(instr.to.x)} {_fmt(instr.to.y)}"
                    )
                elif isinstance(instr, Close):
                    parts.append("Z")
        return " ".join(parts)
    if isinstance(shape, Circle):
        left = Point(shape.center.x - shape.radius, shape.center.y)
        right = Point(shape.center.x + shape.radius, shape.center.y)
        r = _fmt(shape.radius)
        return (
            f"M {_fmt(right.x)} {_fmt(right.y)}"
            f" A {r} {r} 0 1 1 {_fmt(left.x)} {_fmt(left.y)}"
            f" A {r} {r} 0 1 1 {_fmt(right.x)} {_fmt(right.y)} Z"
        )
    if isinstance(shape, Ellipse):
        phi = _fmt(shape.rotation_deg)
        p0 = shape.point_at_param(0.0)
        p1 = shape.point_at_param(math.pi)
        rx, ry = _fmt(shape.rx), _fmt(shape.ry)
        return (
            f"M {_fmt(p0.x)} {_fmt(p0.y)}"
            f" A {rx} {ry} {phi} 1 1 {_fmt(p1.x)} {_fmt(p1.y)}"
            f" A {rx} {ry} {phi} 1 1 {_fmt(p0.x)} {_fmt(p0.y)} Z"
        )
    pts = list(shape.points)
    head = f"M {_fmt(pts[0].x)} {_fmt(pts[0].y)}"
    body = " ".join(f"L {_fmt(p.x)} {_fmt(p.y)}" for p in pts[1:])
    return f"{head} {body} Z"


def _encode_op(op: Op) -> str:
    shape = op.shape
    if isinstance(shape, Compound):
        d = " ".join(_shape_to_d(sub) for sub in shape.shapes)
        base = f'<path d="{d}" fill-rule="evenodd"'
        if isinstance(op, FillOp):
            return f"{base} {_fill_attrs(op.color)}/>"
        return f'{base} fill="none" {_stroke_attrs(op.color, op.width)}/>'
    if isinstance(shape, Path):
        base = f'<path d="{_shape_to_d(shape)}" fill-rule="evenodd"'
        if isinstance(op, FillOp):
            return f"{base} {_fill_attrs(op.color)}/>"
        if isinstance(op, StrokeOp):
            style = f'fill="none" {_stroke_attrs(op.color, op.width)}'
            return f"{base} {style}/>"
        style = f"{_fill_attrs(op.color)} {_stroke_attrs(op.outline_color, op.width)}"
        return f"{base} {style}/>"
    if isinstance(shape, Circle):
        base = (
            f'<circle cx="{_fmt(shape.center.x)}" cy="{_fmt(shape.center.y)}"'
            f' r="{_fmt(shape.radius)}"'
        )
    elif isinstance(shape, Ellipse):
        base = (
            f'<ellipse cx="{_fmt(shape.center.x)}" cy="{_fmt(shape.center.y)}"'
            f' rx="{_fmt(shape.rx)}" ry="{_fmt(shape.ry)}"'
        )
        if shape.rotation_deg:
            base += (
                f' transform="rotate({_fmt(shape.rotation_deg)}'
                f' {_fmt(shape.center.x)} {_fmt(shape.center.y)})"'
            )
    elif isinstance(shape, Arc):
        large = 1 if abs(shape.sweep_deg) > 180 else 0
        sweep = 1 if shape.sweep_deg > 0 else 0
        d = (
            f"M {_fmt(shape.start_point.x)} {_fmt(shape.start_point.y)}"
            f" A {_fmt(shape.radius)} {_fmt(shape.radius)} 0 {large} {sweep}"
            f" {_fmt(shape.end_point.x)} {_fmt(shape.end_point.y)}"
        )
        return f'<path d="{d}" fill="none" {_stroke_attrs(op.color, op.width)}/>'
    elif isinstance(shape, Polyline):
        base = f'<polyline points="{_points_attr(shape.points)}"'
    else:
        base = f'<polygon points="{_points_attr(shape.points)}"'

    if isinstance(op, FillOp):
        return f"{base} {_fill_attrs(op.color)}/>"
    if isinstance(op, StrokeOp):
        return f'{base} fill="none" {_stroke_attrs(op.color, op.width)}/>'
    if isinstance(op, OutlineFillOp):
        return (
            f"{base} {_fill_attrs(op.color)} {_stroke_attrs(op.outline_color, op.width)}/>"
        )
    raise TypeError(f"unknown op type: {type(op).__name__}")


def encode(scene: Scene) -> str:
    """Encode a scene as an SVG document string.

    Operations with ``visible=False`` are skipped entirely, as if they were
    never added.
    """
    w, h = _fmt(scene.width), _fmt(scene.height)
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"'
    lines = [
        f'{header} viewBox="0 0 {w} {h}">',
        *(f"  {_encode_op(op)}" for op in scene.ops if op.visible),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"
