"""RGBA colors in the 0..1 range per channel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Color:
    """An RGBA color. Channels are floats in 0..1; alpha 1 is fully opaque."""

    r: float
    g: float
    b: float
    a: float = 1.0

    def rgba8(self) -> tuple[int, int, int, int]:
        """Quantize to 8-bit channels, as stored in a TinyVG RGBA8888 color table."""

        def q(v: float) -> int:
            return max(0, min(255, round(v * 255)))

        return q(self.r), q(self.g), q(self.b), q(self.a)

    def hex_rgb(self) -> str:
        r, g, b, _ = self.rgba8()
        return f"#{r:02X}{g:02X}{b:02X}"


def rgb(r: float, g: float, b: float) -> Color:
    return Color(r, g, b, 1.0)


def rgba(r: float, g: float, b: float, a: float) -> Color:
    return Color(r, g, b, a)


BLACK = rgb(0, 0, 0)
WHITE = rgb(1, 1, 1)
RED = rgb(1, 0, 0)
GREEN = rgb(0, 1, 0)
BLUE = rgb(0, 0, 1)
YELLOW = rgb(1, 1, 0)
CYAN = rgb(0, 1, 1)
MAGENTA = rgb(1, 0, 1)
GRAY = rgb(0.5, 0.5, 0.5)
