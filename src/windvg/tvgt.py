"""Human-readable debug dump of a scene (a windvg convention, not official .tvgt).

Official TinyVG text format compatibility may come later; this exists so tests
and examples can show what was encoded without a hex editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .shapes import Arc, Circle, Compound, Ellipse, Polyline

if TYPE_CHECKING:
    from .scene import Op, Scene


def _fmt(value: float) -> str:
    return f"{round(value, 3):g}"


def _shape_text(shape) -> str:
    if isinstance(shape, Circle):
        c = f"({_fmt(shape.center.x)},{_fmt(shape.center.y)})"
        return f"circle center={c} r={_fmt(shape.radius)}"
    if isinstance(shape, Ellipse):
        c = f"({_fmt(shape.center.x)},{_fmt(shape.center.y)})"
        text = f"ellipse center={c} rx={_fmt(shape.rx)} ry={_fmt(shape.ry)}"
        if shape.rotation_deg:
            text += f" rot={_fmt(shape.rotation_deg)}"
        return text
    if isinstance(shape, Arc):
        c = f"({_fmt(shape.center.x)},{_fmt(shape.center.y)})"
        return (
            f"arc center={c} r={_fmt(shape.radius)}"
            f" start={_fmt(shape.start_deg)} sweep={_fmt(shape.sweep_deg)}"
        )
    if isinstance(shape, Compound):
        inner = ", ".join(type(sub).__name__ for sub in shape.shapes)
        return f"compound[{inner}]"
    if hasattr(shape, "subpaths"):  # Path
        counts = [len(sub.instructions) for sub in shape.subpaths]
        state = "closed" if shape.closed else "open"
        return f"path {len(shape.subpaths)} subpaths ({state}), instructions {counts}"
    pts = " ".join(f"({_fmt(p.x)},{_fmt(p.y)})" for p in shape.points)
    kind = "polyline" if isinstance(shape, Polyline) else "polygon"
    return f"{kind} [{pts}]"


def _op_text(index: int, op: Op) -> str:
    from .scene import FillOp, OutlineFillOp, StrokeOp

    color = op.color.hex_rgb()
    hidden = "" if op.visible else " (hidden)"
    if isinstance(op, FillOp):
        return f"{index:3d}: fill    {_shape_text(op.shape)} -> {color}{hidden}"
    if isinstance(op, StrokeOp):
        return (
            f"{index:3d}: stroke  {_shape_text(op.shape)} -> {color}"
            f" w={_fmt(op.width)}{hidden}"
        )
    if isinstance(op, OutlineFillOp):
        return (
            f"{index:3d}: o-fill  {_shape_text(op.shape)} -> {color}"
            f" + {op.outline_color.hex_rgb()} w={_fmt(op.width)}{hidden}"
        )
    raise TypeError(f"unknown op type: {type(op).__name__}")


def encode(scene: Scene) -> str:
    """Render a scene as a readable text dump, including hidden operations."""
    header = f"scene {_fmt(scene.width)}x{_fmt(scene.height)}"
    lines = [header, *(_op_text(i, op) for i, op in enumerate(scene.ops))]
    return "\n".join(lines) + "\n"
