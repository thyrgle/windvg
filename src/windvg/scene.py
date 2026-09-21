"""A scene: an ordered list of draw operations plus a canvas size."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .color import Color
from .shapes import Shape


@dataclass(frozen=True, slots=True)
class FillOp:
    shape: Shape
    color: Color


@dataclass(frozen=True, slots=True)
class StrokeOp:
    shape: Shape
    color: Color
    width: float


@dataclass(frozen=True, slots=True)
class OutlineFillOp:
    shape: Shape
    color: Color
    outline_color: Color
    width: float


Op = FillOp | StrokeOp | OutlineFillOp


class Scene:
    """An ordered sequence of fill/stroke operations on a fixed-size canvas."""

    def __init__(self, width: float, height: float):
        if width <= 0 or height <= 0:
            raise ValueError("scene dimensions must be positive")
        self.width = float(width)
        self.height = float(height)
        self.ops: list[Op] = []

    def fill(self, shape: Shape, color: Color) -> None:
        if not shape.fillable:
            raise ValueError(f"{type(shape).__name__} cannot be filled")
        self.ops.append(FillOp(shape, color))

    def stroke(self, shape: Shape, color: Color, width: float = 1.0) -> None:
        if width < 0:
            raise ValueError("stroke width must be non-negative")
        self.ops.append(StrokeOp(shape, color, float(width)))

    def outline_fill(
        self, shape: Shape, color: Color, outline_color: Color, width: float = 1.0
    ) -> None:
        if not shape.fillable:
            raise ValueError(f"{type(shape).__name__} cannot be filled")
        if width < 0:
            raise ValueError("outline width must be non-negative")
        self.ops.append(OutlineFillOp(shape, color, outline_color, float(width)))

    def to_tinyvg(self, scale: int = 4) -> bytes:
        from .tinyvg import encode

        return encode(self, scale=scale)

    def write_tinyvg(self, path: str, scale: int = 4) -> None:
        Path(path).write_bytes(self.to_tinyvg(scale=scale))

    def to_svg(self) -> str:
        from .svg import encode

        return encode(self)

    def write_svg(self, path: str) -> None:
        Path(path).write_text(self.to_svg(), encoding="utf-8")

    def to_tvgt(self) -> str:
        from .tvgt import encode

        return encode(self)
