"""Minimal SVG exporter: the same scene rendered as simple SVG shapes.

Useful as a human-readable preview and for checking geometry in a browser;
TinyVG remains the primary output format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .scene import FillOp, OutlineFillOp, StrokeOp
from .shapes import Circle, Polyline

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


def _encode_op(op: Op) -> str:
    shape = op.shape
    if isinstance(shape, Circle):
        base = (
            f'<circle cx="{_fmt(shape.center.x)}" cy="{_fmt(shape.center.y)}"'
            f' r="{_fmt(shape.radius)}"'
        )
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
