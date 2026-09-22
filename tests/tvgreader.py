"""Minimal TinyVG 1.0 reader, written directly from the spec.

Exists purely for round-trip tests of windvg's writer; not part of the public
API and deliberately not shipped in the package.
"""

from __future__ import annotations


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def byte(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def take(self, n: int) -> bytes:
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def varuint(self) -> int:
        result, shift = 0, 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7

    def unit(self, bits: int, scale: int) -> float:
        raw = int.from_bytes(self.take(bits // 8), "little", signed=True)
        return raw / 2**scale

    def point(self, bits: int, scale: int) -> tuple[float, float]:
        return (self.unit(bits, scale), self.unit(bits, scale))


def _read_path(reader: Reader, bits: int, scale: int, segments: int) -> list[dict]:
    # all segment lengths come first, then the segments themselves
    lengths = [reader.varuint() + 1 for _ in range(segments)]
    paths = []
    for length in lengths:
        start = reader.point(bits, scale)
        commands = []
        for _ in range(length):
            tag = reader.byte()
            instruction = tag & 0b111
            if tag & 0b10000:
                reader.unit(bits, scale)  # per-command line width
            if instruction == 0:  # line
                commands.append({"cmd": "line", "target": reader.point(bits, scale)})
            elif instruction == 3:  # cubic bezier
                c1 = reader.point(bits, scale)
                c2 = reader.point(bits, scale)
                commands.append(
                    {"cmd": "cubic", "c1": c1, "c2": c2, "to": reader.point(bits, scale)}
                )
            elif instruction == 4:  # arc circle
                flags = reader.byte()
                commands.append(
                    {
                        "cmd": "arc",
                        "large_arc": flags & 1,
                        "sweep": (flags >> 1) & 1,
                        "radius": reader.unit(bits, scale),
                        "target": reader.point(bits, scale),
                    }
                )
            elif instruction == 5:  # arc ellipse
                flags = reader.byte()
                commands.append(
                    {
                        "cmd": "arc_ellipse",
                        "large_arc": flags & 1,
                        "sweep": (flags >> 1) & 1,
                        "rx": reader.unit(bits, scale),
                        "ry": reader.unit(bits, scale),
                        "rotation": reader.unit(bits, scale),
                        "target": reader.point(bits, scale),
                    }
                )
            elif instruction == 6:  # close path
                commands.append({"cmd": "close"})
            elif instruction == 7:  # quadratic bezier
                ctrl = reader.point(bits, scale)
                commands.append(
                    {"cmd": "quad", "ctrl": ctrl, "to": reader.point(bits, scale)}
                )

            else:
                raise ValueError(f"unsupported path instruction {instruction}")
        paths.append({"start": start, "commands": commands})
    return paths


def parse(data: bytes) -> dict:
    """Parse a TinyVG file into a plain dict structure for assertions."""
    reader = Reader(data)
    if reader.take(2) != b"\x72\x56":
        raise ValueError("bad magic")
    version = reader.byte()
    if version != 1:
        raise ValueError(f"unsupported version {version}")
    packed = reader.byte()
    scale = packed & 0x0F
    color_encoding = (packed >> 4) & 0b11
    coord_range = packed >> 6
    bits = {0: 16, 1: 8, 2: 32}[coord_range]

    width = int.from_bytes(reader.take(bits // 8), "little")
    height = int.from_bytes(reader.take(bits // 8), "little")
    color_count = reader.varuint()
    if color_encoding != 0:
        raise ValueError("tests only cover RGBA8888")
    colors = [tuple(reader.take(4)) for _ in range(color_count)]

    shapes = []
    while True:
        raw = reader.byte()
        index, style_kind = raw & 0x3F, raw >> 6
        if index == 0:
            break
        if index == 1:  # fill polygon
            n = reader.varuint() + 1
            shapes.append(
                {
                    "op": "fill",
                    "style": reader.varuint(),
                    "points": [reader.point(bits, scale) for _ in range(n)],
                }
            )
        elif index == 3:  # fill path
            s = reader.varuint() + 1
            shapes.append(
                {
                    "op": "fill",
                    "style": reader.varuint(),
                    "paths": _read_path(reader, bits, scale, s),
                }
            )
        elif index == 5:  # draw line loop
            n = reader.varuint() + 1
            shapes.append(
                {
                    "op": "stroke",
                    "style": reader.varuint(),
                    "width": reader.unit(bits, scale),
                    "points": [reader.point(bits, scale) for _ in range(n)],
                }
            )
        elif index == 6:  # draw line strip
            n = reader.varuint() + 1
            shapes.append(
                {
                    "op": "stroke",
                    "style": reader.varuint(),
                    "width": reader.unit(bits, scale),
                    "points": [reader.point(bits, scale) for _ in range(n)],
                    "strip": True,
                }
            )
        elif index == 7:  # draw line path
            s = reader.varuint() + 1
            shapes.append(
                {
                    "op": "stroke",
                    "style": reader.varuint(),
                    "width": reader.unit(bits, scale),
                    "paths": _read_path(reader, bits, scale, s),
                }
            )
        elif index == 8:  # outline fill polygon
            b2 = reader.byte()
            n = (b2 & 0x3F) + 1
            shapes.append(
                {
                    "op": "outline_fill",
                    "style": reader.varuint(),
                    "outline_style": reader.varuint(),
                    "width": reader.unit(bits, scale),
                    "points": [reader.point(bits, scale) for _ in range(n)],
                }
            )
        elif index == 10:  # outline fill path
            b2 = reader.byte()
            s = (b2 & 0x3F) + 1
            shapes.append(
                {
                    "op": "outline_fill",
                    "style": reader.varuint(),
                    "outline_style": reader.varuint(),
                    "width": reader.unit(bits, scale),
                    "paths": _read_path(reader, bits, scale, s),
                }
            )
        else:
            raise ValueError(f"unsupported command index {index}")
        _ = style_kind

    return {
        "version": version,
        "scale": scale,
        "color_encoding": color_encoding,
        "coord_range": coord_range,
        "width": width,
        "height": height,
        "colors": colors,
        "shapes": shapes,
        "bytes_consumed": reader.pos,
        "total_bytes": len(data),
    }
