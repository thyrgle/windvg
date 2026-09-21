"""TinyVG 1.0 binary writer.

Implements the format described at https://tinyvg.tech/specification:
a fixed-point coordinate system with a configurable number of fraction bits,
a color lookup table, and a sequence of draw commands terminated by 0x00.

Only flat-colored styles and the RGBA8888 color encoding are emitted; circles
and ellipses are encoded exactly as fill/stroke paths built from two arc
instructions (sweep bit 0 = right turns = visually clockwise on screen).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .geometry import Point
from .scene import OutlineFillOp, StrokeOp
from .shapes import Arc, Circle, Ellipse, Polyline

if TYPE_CHECKING:
    from .color import Color
    from .scene import Op, Scene

MAGIC = b"\x72\x56"
VERSION = 1

COLOR_RGBA8888 = 0
COORD_DEFAULT = 0  # 16-bit units
COORD_ENHANCED = 2  # 32-bit units

END_OF_DOCUMENT = 0x00
FILL_POLYGON = 1
FILL_PATH = 3
DRAW_LINE_LOOP = 5
DRAW_LINE_STRIP = 6
DRAW_LINE_PATH = 7
OUTLINE_FILL_POLYGON = 8
OUTLINE_FILL_PATH = 10

STYLE_FLAT = 0

INSTR_ARC_CIRCLE = 4
INSTR_ARC_ELLIPSE = 5
INSTR_CLOSE_PATH = 6


def write_varuint(value: int) -> bytes:
    """LEB128-style unsigned integer: 7 payload bits per byte, high bit = continue."""
    if value < 0:
        raise ValueError("varuint cannot encode negative values")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


class _Writer:
    def __init__(self, scale: int, bits: int):
        self.buf = bytearray()
        self.scale = scale
        self.bits = bits
        self._limit = 2 ** (bits - 1) - 1

    def unit(self, value: float) -> None:
        q = round(value * (2**self.scale))
        if abs(q) > self._limit:
            raise ValueError(f"coordinate {value} does not fit in {self.bits}-bit units")
        self.buf += int(q).to_bytes(self.bits // 8, "little", signed=True)

    def point(self, pt: Point) -> None:
        self.unit(pt.x)
        self.unit(pt.y)

    def varuint(self, value: int) -> None:
        self.buf += write_varuint(value)

    def byte(self, value: int) -> None:
        self.buf.append(value)

    def command(self, index: int, style_kind: int = STYLE_FLAT) -> None:
        self.byte(index | (style_kind << 6))

    def fill_style(self, color_index: int) -> None:
        self.varuint(color_index)

    def line_style(self, color_index: int, width: float) -> None:
        self.varuint(color_index)
        self.unit(width)


def _collect_colors(ops: list[Op]) -> list[Color]:
    colors: list[Color] = []
    for op in ops:
        for color in (getattr(op, "color", None), getattr(op, "outline_color", None)):
            if color is not None and color not in colors:
                colors.append(color)
    return colors


def _units_needed(ops: list[Op]) -> tuple[float, float]:
    """Smallest and largest unit values any encoded coordinate or width needs."""
    units: list[float] = []
    for op in ops:
        shape = op.shape
        if isinstance(shape, Circle):
            r = shape.radius
            cx, cy = shape.center.x, shape.center.y
            units += [cx - r, cy - r, cx + r, cy + r]
        elif isinstance(shape, Ellipse):
            # exact axis-aligned bounds of a rotated ellipse
            rot = math.radians(shape.rotation_deg)
            cos_r, sin_r = math.cos(rot), math.sin(rot)
            ex = math.sqrt((shape.rx * cos_r) ** 2 + (shape.ry * sin_r) ** 2)
            ey = math.sqrt((shape.rx * sin_r) ** 2 + (shape.ry * cos_r) ** 2)
            units += [
                shape.center.x - ex, shape.center.y - ey,
                shape.center.x + ex, shape.center.y + ey,
            ]
        elif isinstance(shape, Arc):
            for i in range(65):
                p = shape.point_at_deg(shape.start_deg + shape.sweep_deg * i / 64)
                units += [p.x, p.y]
        else:
            for pt in shape.points:
                units += [pt.x, pt.y]
        width = getattr(op, "width", None)
        if width is not None:
            units += [width]
    if not units:
        return 0.0, 0.0
    return min(units), max(units)


def _choose_coord_range(ops: list[Op], scale: int) -> int:
    lo, hi = _units_needed(ops)
    lo_q, hi_q = round(lo * 2**scale), round(hi * 2**scale)
    if lo_q >= -(2**15) and hi_q <= 2**15 - 1:
        return COORD_DEFAULT
    if lo_q >= -(2**31) and hi_q <= 2**31 - 1:
        return COORD_ENHANCED
    raise ValueError("coordinates do not fit even in 32-bit units; reduce the scale")


def _emit_arc_instruction(writer: _Writer, large_arc: bool, sweep_cw: bool) -> None:
    # flags: large_arc (bit 0), sweep (bit 1); sweep 0 = right turns = CW on screen
    writer.byte((1 if large_arc else 0) | (0 if sweep_cw else 0b10))


def _emit_closed_curve_path(writer: _Writer, shape: Circle | Ellipse) -> None:
    """One path segment: two half arcs, origin -> opposite point -> origin."""
    if isinstance(shape, Circle):
        opposite = Point(shape.center.x - shape.radius, shape.center.y)
        origin = Point(shape.center.x + shape.radius, shape.center.y)
        emit_half = _emit_circle_half
    else:
        origin = shape.point_at_param(0.0)
        opposite = shape.point_at_param(math.pi)
        emit_half = _emit_ellipse_half
    writer.varuint(2)  # command count - 1 (two arcs + close)
    writer.point(origin)
    for target in (opposite, origin):
        emit_half(writer, shape, target)
    writer.byte(INSTR_CLOSE_PATH)


def _emit_circle_half(writer: _Writer, circle: Circle, target: Point) -> None:
    writer.byte(INSTR_ARC_CIRCLE)
    _emit_arc_instruction(writer, large_arc=False, sweep_cw=True)
    writer.unit(circle.radius)
    writer.point(target)


def _emit_ellipse_half(writer: _Writer, ellipse: Ellipse, target: Point) -> None:
    writer.byte(INSTR_ARC_ELLIPSE)
    _emit_arc_instruction(writer, large_arc=False, sweep_cw=True)
    writer.unit(ellipse.rx)
    writer.unit(ellipse.ry)
    # TinyVG stores rotation in the "mathematical negative direction", i.e.
    # the opposite sign of our clockwise-on-screen rotation_deg (verified
    # against the official renderer).
    writer.unit(-ellipse.rotation_deg)
    writer.point(target)


def _emit_arc_path(writer: _Writer, arc: Arc) -> None:
    """One open path segment holding a single arc-circle instruction."""
    writer.varuint(0)  # command count - 1 (one arc)
    writer.point(arc.start_point)
    writer.byte(INSTR_ARC_CIRCLE)
    _emit_arc_instruction(
        writer, large_arc=abs(arc.sweep_deg) > 180, sweep_cw=arc.sweep_deg > 0
    )
    writer.unit(arc.radius)
    writer.point(arc.end_point)


def encode(scene: Scene, scale: int = 4) -> bytes:
    """Encode a scene as a TinyVG 1.0 binary file.

    Operations with ``visible=False`` are skipped entirely, as if they were
    never added.
    """
    if not 0 <= scale <= 15:
        raise ValueError("scale must fit in 4 bits (0..15)")

    ops = [op for op in scene.ops if op.visible]
    coord_range = _choose_coord_range(ops, scale)
    bits = {COORD_DEFAULT: 16, COORD_ENHANCED: 32}[coord_range]
    writer = _Writer(scale, bits)

    # Header
    writer.buf += MAGIC
    writer.byte(VERSION)
    writer.byte(scale | (COLOR_RGBA8888 << 4) | (coord_range << 6))
    width_bytes = bits // 8
    for dimension in (scene.width, scene.height):
        value = round(dimension)
        if not 0 < value < 2 ** (bits - 1):
            raise ValueError(
                f"scene dimension {dimension} out of range for {bits}-bit headers"
            )
        writer.buf += value.to_bytes(width_bytes, "little")

    # Color table
    colors = _collect_colors(ops)
    writer.varuint(len(colors))
    for color in colors:
        writer.buf += bytes(color.rgba8())

    # Commands
    index = {color: i for i, color in enumerate(colors)}
    for op in ops:
        shape = op.shape
        fill_index = index[op.color]
        outline_index = index[getattr(op, "outline_color", op.color)]
        is_outline_fill = isinstance(op, OutlineFillOp)
        is_stroke = isinstance(op, StrokeOp)

        if isinstance(shape, (Circle, Ellipse)):
            if is_stroke:
                writer.command(DRAW_LINE_PATH)
                writer.varuint(0)  # 1 segment (off by one)
                writer.line_style(fill_index, op.width)
                _emit_closed_curve_path(writer, shape)
            elif is_outline_fill:
                writer.command(OUTLINE_FILL_PATH)
                writer.byte(0)  # 1 segment (u6, off by one) | secondary style kind 0 (u2)
                writer.fill_style(fill_index)
                writer.line_style(outline_index, op.width)
                _emit_closed_curve_path(writer, shape)
            else:
                writer.command(FILL_PATH)
                writer.varuint(0)  # 1 segment (off by one)
                writer.fill_style(fill_index)
                _emit_closed_curve_path(writer, shape)
            continue

        if isinstance(shape, Arc):
            if not is_stroke:
                raise ValueError("arcs can only be stroked; fill a pie or chord instead")
            writer.command(DRAW_LINE_PATH)
            writer.varuint(0)
            writer.line_style(fill_index, op.width)
            _emit_arc_path(writer, shape)
            continue

        points = list(shape.points)
        if is_outline_fill and len(points) > 64:
            # Too many points for the combined command; fill and outline separately.
            passes = ((fill_index, FILL_POLYGON), (outline_index, DRAW_LINE_LOOP))
            for color_index, cmd in passes:
                writer.command(cmd)
                writer.varuint(len(points) - 1)
                if cmd == FILL_POLYGON:
                    writer.fill_style(color_index)
                else:
                    writer.line_style(color_index, op.width)
                for pt in points:
                    writer.point(pt)
        elif is_stroke:
            cmd = DRAW_LINE_STRIP if isinstance(shape, Polyline) else DRAW_LINE_LOOP
            writer.command(cmd)
            writer.varuint(len(points) - 1)
            writer.line_style(fill_index, op.width)
            for pt in points:
                writer.point(pt)
        elif is_outline_fill:
            writer.command(OUTLINE_FILL_POLYGON)
            writer.byte(len(points) - 1)  # count (u6) | secondary style kind (u2)
            writer.fill_style(fill_index)
            writer.line_style(outline_index, op.width)
            for pt in points:
                writer.point(pt)
        else:
            writer.command(FILL_POLYGON)
            writer.varuint(len(points) - 1)
            writer.fill_style(fill_index)
            for pt in points:
                writer.point(pt)

    writer.byte(END_OF_DOCUMENT)
    return bytes(writer.buf)
