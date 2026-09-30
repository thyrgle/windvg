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
from .gradient import Color, LinearGradient, Paint, RadialGradient, paint_colors
from .path import ArcCircle, ArcEllipse, Close, Cubic, Line, Path, Quad
from .scene import OutlineFillOp, StrokeOp, TextOp
from .shapes import Arc, Circle, Compound, Ellipse, Polyline

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
STYLE_LINEAR = 1
STYLE_RADIAL = 2

INSTR_LINE = 0
INSTR_ARC_CIRCLE = 4
INSTR_ARC_ELLIPSE = 5
INSTR_CLOSE_PATH = 6
INSTR_CUBIC = 3
INSTR_QUAD = 7

MAX_OUTLINE_SEGMENTS = 64


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

    def paint_style(self, paint: Paint, index: dict) -> int:
        """Write one style record; returns its style kind for the command byte."""
        if isinstance(paint, Color):
            self.varuint(index[paint])
            return STYLE_FLAT
        if isinstance(paint, LinearGradient):
            self.point(paint.start)
            self.point(paint.end)
            self.varuint(index[paint.start_color])
            self.varuint(index[paint.end_color])
            return STYLE_LINEAR
        if isinstance(paint, RadialGradient):
            self.point(paint.center)
            self.point(paint.edge)
            self.varuint(index[paint.center_color])
            self.varuint(index[paint.edge_color])
            return STYLE_RADIAL
        raise TypeError(f"unknown paint {type(paint).__name__}")

    def paint_line_style(self, paint: Paint, index: dict, width: float) -> int:
        kind = self.paint_style(paint, index)
        self.unit(width)
        return kind


def _collect_colors(ops: list[Op]) -> list[Color]:
    colors: list[Color] = []
    for op in ops:
        for paint in (getattr(op, "color", None), getattr(op, "outline_color", None)):
            if paint is None:
                continue
            for color in paint_colors(paint):
                if color not in colors:
                    colors.append(color)
    return colors


def _units_needed(ops: list[Op]) -> tuple[float, float]:
    """Smallest and largest unit values any encoded coordinate or width needs."""
    units: list[float] = []
    for op in ops:
        _collect_shape_units(op.shape, units)
        for paint in (getattr(op, "color", None), getattr(op, "outline_color", None)):
            if isinstance(paint, LinearGradient):
                units += [paint.start.x, paint.start.y, paint.end.x, paint.end.y]
            elif isinstance(paint, RadialGradient):
                units += [paint.center.x, paint.center.y, paint.edge.x, paint.edge.y]
        width = getattr(op, "width", None)
        if width is not None:
            units += [width]
    if not units:
        return 0.0, 0.0
    return min(units), max(units)


def _collect_shape_units(shape, units: list[float]) -> None:
    if isinstance(shape, Compound):
        for sub in shape.shapes:
            _collect_shape_units(sub, units)
    elif isinstance(shape, Path):
        points = [p for sub in shape._subs for p in sub.chain]
        pad = shape.tolerance
        units += [
            min(p.x for p in points) - pad,
            min(p.y for p in points) - pad,
            max(p.x for p in points) + pad,
            max(p.y for p in points) + pad,
        ]
    elif isinstance(shape, Circle):
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
            shape.center.x - ex,
            shape.center.y - ey,
            shape.center.x + ex,
            shape.center.y + ey,
        ]
    elif isinstance(shape, Arc):
        for i in range(65):
            p = shape.point_at_deg(shape.start_deg + shape.sweep_deg * i / 64)
            units += [p.x, p.y]
    else:
        for pt in shape.points:
            units += [pt.x, pt.y]


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


def _emit_instruction(writer: _Writer, instr) -> None:
    if isinstance(instr, Line):
        writer.byte(INSTR_LINE)
        writer.point(instr.to)
    elif isinstance(instr, Quad):
        writer.byte(INSTR_QUAD)
        writer.point(instr.ctrl)
        writer.point(instr.to)
    elif isinstance(instr, Cubic):
        writer.byte(INSTR_CUBIC)
        writer.point(instr.c1)
        writer.point(instr.c2)
        writer.point(instr.to)
    elif isinstance(instr, ArcCircle):
        writer.byte(INSTR_ARC_CIRCLE)
        _emit_arc_instruction(writer, instr.large, instr.sweep_cw)
        writer.unit(instr.radius)
        writer.point(instr.to)
    elif isinstance(instr, ArcEllipse):
        writer.byte(INSTR_ARC_ELLIPSE)
        _emit_arc_instruction(writer, instr.large, instr.sweep_cw)
        writer.unit(instr.rx)
        writer.unit(instr.ry)
        writer.unit(-instr.rotation_deg)  # TinyVG negates rotation
        writer.point(instr.to)
    elif isinstance(instr, Close):
        writer.byte(INSTR_CLOSE_PATH)
    else:
        raise TypeError(f"unknown path instruction {type(instr).__name__}")


def _emit_polygon_segment_body(writer: _Writer, polygon) -> None:
    points = list(polygon.points)
    writer.point(points[0])
    for pt in points[1:]:
        writer.byte(INSTR_LINE)
        writer.point(pt)
    writer.byte(INSTR_CLOSE_PATH)


def _segment_count(shape) -> int:
    if isinstance(shape, Compound):
        return sum(_segment_count(sub) for sub in shape.shapes)
    if isinstance(shape, Path):
        return len(shape.subpaths)
    return 1


def _emit_segment_lengths(writer: _Writer, shape) -> None:
    """All segment command counts come first, before any segment bodies."""
    if isinstance(shape, Compound):
        for sub in shape.shapes:
            _emit_segment_lengths(writer, sub)
    elif isinstance(shape, Path):
        for sub in shape.subpaths:
            writer.varuint(len(sub.instructions) - 1)
    elif isinstance(shape, (Circle, Ellipse)):
        writer.varuint(2)  # two arcs + close
    else:
        writer.varuint(len(shape.points) - 1)  # lines + close


def _emit_segment_bodies(writer: _Writer, shape) -> None:
    if isinstance(shape, Compound):
        for sub in shape.shapes:
            _emit_segment_bodies(writer, sub)
    elif isinstance(shape, Path):
        for sub in shape.subpaths:
            writer.point(sub.start)
            for instr in sub.instructions:
                _emit_instruction(writer, instr)
    elif isinstance(shape, (Circle, Ellipse)):
        _emit_closed_curve_path(writer, shape)
    else:
        _emit_polygon_segment_body(writer, shape)


def _emit_shape_segments(writer: _Writer, shape) -> None:
    """Emit the closed path segment(s) that encode one fillable shape."""
    _emit_segment_lengths(writer, shape)
    _emit_segment_bodies(writer, shape)


def _kind_of(paint: Paint) -> int:
    if isinstance(paint, Color):
        return STYLE_FLAT
    if isinstance(paint, LinearGradient):
        return STYLE_LINEAR
    return STYLE_RADIAL


def _emit_op(writer: _Writer, op: Op, index: dict) -> None:
    shape = op.shape
    is_outline_fill = isinstance(op, OutlineFillOp)
    is_stroke = isinstance(op, StrokeOp)
    fill_kind = _kind_of(op.color)
    outline_kind = _kind_of(getattr(op, "outline_color", op.color))

    if isinstance(shape, Compound):
        if is_outline_fill:
            raise ValueError("compound shapes cannot be outline-filled; fill each part")
        if is_stroke:
            for sub in shape.shapes:
                _emit_op(writer, StrokeOp(sub, op.color, op.width), index)
        else:
            writer.command(FILL_PATH, fill_kind)
            writer.varuint(_segment_count(shape) - 1)
            writer.paint_style(op.color, index)
            _emit_shape_segments(writer, shape)
        return

    if isinstance(shape, Path):
        segments = _segment_count(shape)
        if is_stroke:
            writer.command(DRAW_LINE_PATH, fill_kind)
            writer.varuint(segments - 1)
            writer.paint_line_style(op.color, index, op.width)
            _emit_shape_segments(writer, shape)
        elif is_outline_fill and segments <= MAX_OUTLINE_SEGMENTS:
            writer.command(OUTLINE_FILL_PATH, fill_kind)
            writer.byte((segments - 1) | (outline_kind << 6))
            writer.paint_style(op.color, index)
            writer.paint_style(op.outline_color, index)
            writer.unit(op.width)
            _emit_shape_segments(writer, shape)
        elif is_outline_fill:
            # too many segments for the combined command; fill and outline apart
            writer.command(FILL_PATH, fill_kind)
            writer.varuint(segments - 1)
            writer.paint_style(op.color, index)
            _emit_shape_segments(writer, shape)
            writer.command(DRAW_LINE_PATH, outline_kind)
            writer.varuint(segments - 1)
            writer.paint_line_style(op.outline_color, index, op.width)
            _emit_shape_segments(writer, shape)
        else:
            writer.command(FILL_PATH, fill_kind)
            writer.varuint(segments - 1)
            writer.paint_style(op.color, index)
            _emit_shape_segments(writer, shape)
        return

    if isinstance(shape, (Circle, Ellipse)):
        if is_stroke:
            writer.command(DRAW_LINE_PATH, fill_kind)
            writer.varuint(0)  # 1 segment (off by one)
            writer.paint_line_style(op.color, index, op.width)
            _emit_shape_segments(writer, shape)
        elif is_outline_fill:
            writer.command(OUTLINE_FILL_PATH, fill_kind)
            writer.byte(outline_kind << 6)  # 1 segment (u6, off by one) | sec kind (u2)
            writer.paint_style(op.color, index)
            writer.paint_style(op.outline_color, index)
            writer.unit(op.width)
            _emit_shape_segments(writer, shape)
        else:
            writer.command(FILL_PATH, fill_kind)
            writer.varuint(0)  # 1 segment (off by one)
            writer.paint_style(op.color, index)
            _emit_shape_segments(writer, shape)
        return

    if isinstance(shape, Arc):
        if not is_stroke:
            raise ValueError("arcs can only be stroked; fill a pie or chord instead")
        writer.command(DRAW_LINE_PATH, fill_kind)
        writer.varuint(0)
        writer.paint_line_style(op.color, index, op.width)
        _emit_arc_path(writer, shape)
        return

    points = list(shape.points)
    if is_outline_fill and len(points) > MAX_OUTLINE_SEGMENTS:
        # Too many points for the combined command; fill and outline separately.
        writer.command(FILL_POLYGON, fill_kind)
        writer.varuint(len(points) - 1)
        writer.paint_style(op.color, index)
        for pt in points:
            writer.point(pt)
        writer.command(DRAW_LINE_LOOP, outline_kind)
        writer.varuint(len(points) - 1)
        writer.paint_line_style(op.outline_color, index, op.width)
        for pt in points:
            writer.point(pt)
    elif is_stroke:
        cmd = DRAW_LINE_STRIP if isinstance(shape, Polyline) else DRAW_LINE_LOOP
        writer.command(cmd, fill_kind)
        writer.varuint(len(points) - 1)
        writer.paint_line_style(op.color, index, op.width)
        for pt in points:
            writer.point(pt)
    elif is_outline_fill:
        writer.command(OUTLINE_FILL_POLYGON, fill_kind)
        writer.byte((len(points) - 1) | (outline_kind << 6))
        writer.paint_style(op.color, index)
        writer.paint_style(op.outline_color, index)
        writer.unit(op.width)
        for pt in points:
            writer.point(pt)
    else:
        writer.command(FILL_POLYGON, fill_kind)
        writer.varuint(len(points) - 1)
        writer.paint_style(op.color, index)
        for pt in points:
            writer.point(pt)


def encode(scene: Scene, scale: int = 4, drop_text: bool = False) -> bytes:
    """Encode a scene as a TinyVG 1.0 binary file.

    Operations with ``visible=False`` are skipped entirely, as if they were
    never added. Text ops (§7.19) are refused by default — TinyVG cannot
    encode text; pass ``drop_text=True`` to omit them (§11 fidelity tiers).
    """
    if not 0 <= scale <= 15:
        raise ValueError("scale must fit in 4 bits (0..15)")

    ops = [op for op in scene.ops if op.visible]
    if not drop_text and any(isinstance(op, TextOp) for op in ops):
        raise ValueError(
            "cannot encode text as TinyVG (fidelity tier B); "
            "pass drop_text=True to omit text nodes"
        )
    ops = [op for op in ops if not isinstance(op, TextOp)]
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
        _emit_op(writer, op, index)

    writer.byte(END_OF_DOCUMENT)
    return bytes(writer.buf)
