"""Paths: mixed line/curve segments as tracks, with holes via subpaths.

Instructions mirror the TinyVG/SVG toolset (line, quadratic/cubic Bezier,
circle and ellipse arcs, close) in SVG-style endpoint parameterization, so a
Path exports 1:1 to both formats. Flattening (used for arc-length queries)
is adaptive with a configurable tolerance; exact instructions are still what
gets written to files.

A Path may hold several subpaths; filled paths use the even-odd rule, so an
inner subpath carves a hole.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from .geometry import Point, cross
from .shapes import (
    Shape,
    _as_point,
    _point_on_chain,
    _project_on_chain,
    _tangent_on_chain,
)


@dataclass(frozen=True, slots=True)
class Line:
    to: Point


@dataclass(frozen=True, slots=True)
class Quad:
    ctrl: Point
    to: Point


@dataclass(frozen=True, slots=True)
class Cubic:
    c1: Point
    c2: Point
    to: Point


@dataclass(frozen=True, slots=True)
class ArcCircle:
    radius: float
    large: bool
    sweep_cw: bool
    to: Point


@dataclass(frozen=True, slots=True)
class ArcEllipse:
    rx: float
    ry: float
    rotation_deg: float
    large: bool
    sweep_cw: bool
    to: Point


@dataclass(frozen=True, slots=True)
class Close:
    pass


Instruction = Line | Quad | Cubic | ArcCircle | ArcEllipse | Close


def instruction_to_dict(instr: Instruction) -> dict:
    if isinstance(instr, Line):
        return {"cmd": "line", "to": [instr.to.x, instr.to.y]}
    if isinstance(instr, Quad):
        return {
            "cmd": "quad",
            "ctrl": [instr.ctrl.x, instr.ctrl.y],
            "to": [instr.to.x, instr.to.y],
        }
    if isinstance(instr, Cubic):
        return {
            "cmd": "cubic",
            "c1": [instr.c1.x, instr.c1.y],
            "c2": [instr.c2.x, instr.c2.y],
            "to": [instr.to.x, instr.to.y],
        }
    if isinstance(instr, ArcCircle):
        return {
            "cmd": "arc_circle",
            "radius": instr.radius,
            "large": instr.large,
            "sweep_cw": instr.sweep_cw,
            "to": [instr.to.x, instr.to.y],
        }
    if isinstance(instr, ArcEllipse):
        return {
            "cmd": "arc_ellipse",
            "rx": instr.rx,
            "ry": instr.ry,
            "rotation_deg": instr.rotation_deg,
            "large": instr.large,
            "sweep_cw": instr.sweep_cw,
            "to": [instr.to.x, instr.to.y],
        }
    if isinstance(instr, Close):
        return {"cmd": "close"}
    raise TypeError(f"cannot serialize instruction {type(instr).__name__}")


def instruction_from_dict(d: dict) -> Instruction:
    cmd = d["cmd"]
    if cmd == "line":
        return Line(Point(d["to"][0], d["to"][1]))
    if cmd == "quad":
        return Quad(Point(d["ctrl"][0], d["ctrl"][1]), Point(d["to"][0], d["to"][1]))
    if cmd == "cubic":
        return Cubic(
            Point(d["c1"][0], d["c1"][1]),
            Point(d["c2"][0], d["c2"][1]),
            Point(d["to"][0], d["to"][1]),
        )
    if cmd == "arc_circle":
        return ArcCircle(
            d["radius"], d["large"], d["sweep_cw"], Point(d["to"][0], d["to"][1])
        )
    if cmd == "arc_ellipse":
        return ArcEllipse(
            d["rx"],
            d["ry"],
            d["rotation_deg"],
            d["large"],
            d["sweep_cw"],
            Point(d["to"][0], d["to"][1]),
        )
    if cmd == "close":
        return Close()
    raise ValueError(f"unknown instruction {cmd}")


@dataclass(frozen=True, slots=True)
class SubPath:
    start: Point
    instructions: tuple[Instruction, ...]


def _line_dist(pt: Point, a: Point, b: Point) -> float:
    ab = b - a
    length = ab.length()
    if length == 0:
        return pt.distance_to(a)
    return abs(cross(pt - a, ab)) / length


def _flatten_bezier(
    out: list[Point], p0: Point, ctrls: list[Point], p1: Point, tol: float, depth: int = 0
):
    """Adaptive de Casteljau subdivision; appends everything after p0 to out."""
    flat = all(_line_dist(c, p0, p1) <= tol for c in ctrls)
    if depth >= 16 or flat:
        out.append(p1)
        return
    if len(ctrls) == 1:
        c = ctrls[0]
        left_c = p0 + (c - p0) * 0.5
        mid = (p0 + c * 2 + p1) * 0.25
        right_c = c + (p1 - c) * 0.5
        halves = ((p0, [left_c], mid), (mid, [right_c], p1))
    else:
        c1, c2 = ctrls
        p01, p12, p23 = p0.lerp(c1, 0.5), c1.lerp(c2, 0.5), c2.lerp(p1, 0.5)
        left_c = p01.lerp(p12, 0.5)
        right_c = p12.lerp(p23, 0.5)
        mid = left_c.lerp(right_c, 0.5)
        halves = ((p0, [p01, left_c], mid), (mid, [right_c, p23], p1))
    for start, controls, end in halves:
        _flatten_bezier(out, start, controls, end, tol, depth + 1)


def _flatten_arc(
    out: list[Point],
    rx: float,
    ry: float,
    rotation_deg: float,
    large: bool,
    sweep_cw: bool,
    p0: Point,
    p1: Point,
    tol: float,
) -> None:
    """Sample an endpoint-parameterized elliptical arc (SVG spec F.6.5)."""
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rotation_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx2, dy2 = (p0.x - p1.x) / 2.0, (p0.y - p1.y) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        scale = math.sqrt(lam)
        rx, ry = rx * scale, ry * scale

    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    root = math.sqrt(max(0.0, num / den)) if den > 0 else 0.0
    sign = -1.0 if large == sweep_cw else 1.0
    cxp = sign * root * rx * y1p / ry
    cyp = sign * -root * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (p0.x + p1.x) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (p0.y + p1.y) / 2.0

    def angle(ux: float, uy: float) -> float:
        return math.atan2(uy, ux)

    theta1 = angle((x1p - cxp) / rx, (y1p - cyp) / ry)
    theta2 = angle((-x1p - cxp) / rx, (-y1p - cyp) / ry)
    delta = theta2 - theta1
    if not sweep_cw and delta > 0:
        delta -= 2.0 * math.pi
    elif sweep_cw and delta < 0:
        delta += 2.0 * math.pi

    max_angle = 2.0 * math.acos(max(-1.0, min(1.0, 1.0 - tol / max(rx, ry))))
    steps = max(4, math.ceil(abs(delta) / max_angle))
    for i in range(1, steps + 1):
        u = theta1 + delta * i / steps
        ux, uy = rx * math.cos(u), ry * math.sin(u)
        out.append(Point(cx + ux * cos_p - uy * sin_p, cy + ux * sin_p + uy * cos_p))


def _flatten_subpath(sub: SubPath, tol: float) -> list[Point]:
    """The full chain of a subpath including its start point."""
    chain = [sub.start]
    current = sub.start
    for instr in sub.instructions:
        if isinstance(instr, Line):
            chain.append(instr.to)
            current = instr.to
        elif isinstance(instr, Quad):
            _flatten_bezier(chain, current, [instr.ctrl], instr.to, tol)
            current = instr.to
        elif isinstance(instr, Cubic):
            _flatten_bezier(chain, current, [instr.c1, instr.c2], instr.to, tol)
            current = instr.to
        elif isinstance(instr, ArcCircle):
            _flatten_arc(
                chain,
                instr.radius,
                instr.radius,
                0.0,
                instr.large,
                instr.sweep_cw,
                current,
                instr.to,
                tol,
            )
            current = instr.to
        elif isinstance(instr, ArcEllipse):
            _flatten_arc(
                chain,
                instr.rx,
                instr.ry,
                instr.rotation_deg,
                instr.large,
                instr.sweep_cw,
                current,
                instr.to,
                tol,
            )
            current = instr.to
        elif isinstance(instr, Close):
            chain.append(sub.start)
            current = sub.start
    return chain


@dataclass(frozen=True, slots=True)
class _SubGeom:
    chain: list[Point]
    length: float
    closed: bool


def _shoelace(chain: list[Point]) -> float:
    total = 0.0
    for a, b in zip(chain, chain[1:], strict=False):
        total += cross(a, b)
    return total / 2.0


@dataclass(frozen=True, slots=True)
class Path(Shape):
    """One or more subpaths of mixed line/curve instructions.

    Track queries run on a flattened approximation with the given tolerance;
    export stays exact. Filled paths apply the even-odd rule across subpaths.
    """

    subpaths: tuple[SubPath, ...]
    tolerance: float = 0.1
    _subs: list = field(init=False, repr=False, compare=False, default_factory=list)

    def __init__(self, subpaths: Sequence[SubPath], tolerance: float = 0.1):
        def normalize(s):
            if isinstance(s, SubPath):
                return s
            return SubPath(_as_point(s.start), tuple(s.instructions))

        subs = tuple(normalize(s) for s in subpaths)
        if not subs:
            raise ValueError("a path needs at least one subpath")
        for sub in subs:
            if not sub.instructions:
                raise ValueError("every subpath needs at least one instruction")
        object.__setattr__(self, "subpaths", subs)
        object.__setattr__(self, "tolerance", float(tolerance))
        geoms = []
        for sub in subs:
            chain = _flatten_subpath(sub, tolerance)
            length = sum(a.distance_to(b) for a, b in zip(chain, chain[1:], strict=False))
            geoms.append(_SubGeom(chain, length, chain[0].distance_to(chain[-1]) < 1e-9))
        object.__setattr__(self, "_subs", geoms)

    @property
    def _offsets(self) -> list[float]:
        offsets, acc = [], 0.0
        for sub in self._subs:
            offsets.append(acc)
            acc += sub.length
        return offsets

    def perimeter(self) -> float:
        return sum(sub.length for sub in self._subs)

    def _locate(self, d: float) -> tuple[int, float]:
        for i, offset in enumerate(self._offsets):
            if d <= offset + self._subs[i].length or i == len(self._subs) - 1:
                return i, max(0.0, min(self._subs[i].length, d - offset))
        return 0, 0.0

    def point_at_distance(self, d: float) -> Point:
        if self.closed:
            d %= self.perimeter()
        else:
            d = max(0.0, min(self.perimeter(), d))
        i, local = self._locate(d)
        chain = self._subs[i].chain
        return _point_on_chain(chain, zip(chain, chain[1:], strict=False), local)

    def tangent_at_distance(self, d: float) -> Point:
        if self.closed:
            d %= self.perimeter()
        else:
            d = max(0.0, min(self.perimeter(), d))
        i, local = self._locate(d)
        chain = self._subs[i].chain
        return _tangent_on_chain(chain, zip(chain, chain[1:], strict=False), local)

    def project(self, pt: Point) -> float:
        best, best_d = math.inf, 0.0
        for i, sub in enumerate(self._subs):
            pos = _project_on_chain(zip(sub.chain, sub.chain[1:], strict=False), pt)
            total = self._offsets[i] + pos
            dist = self.point_at_distance(total).distance_to(pt)
            if dist < best:
                best, best_d = dist, total
        return best_d

    @property
    def closed(self) -> bool:
        return all(sub.closed for sub in self._subs)

    @property
    def fillable(self) -> bool:
        return self.closed

    @property
    def winding_sign(self) -> int:
        total = sum(_shoelace(sub.chain) for sub in self._subs if sub.closed)
        return 1 if total >= 0 else -1

    def segment_count(self) -> int:
        """How many TinyVG path segments the path encodes as."""
        return len(self.subpaths)

    def to_dict(self) -> dict:
        return {
            "kind": "path",
            "subpaths": [
                {
                    "start": [sub.start.x, sub.start.y],
                    "instructions": [instruction_to_dict(i) for i in sub.instructions],
                }
                for sub in self.subpaths
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Path:
        subs = tuple(
            SubPath(
                Point(sub["start"][0], sub["start"][1]),
                tuple(instruction_from_dict(i) for i in sub["instructions"]),
            )
            for sub in d["subpaths"]
        )
        return cls(subs)


def _coerce_point(pt: tuple[float, float] | Point) -> Point:
    return _as_point(pt)


class PathBuilder:
    """Fluent constructor for Paths, one subpath at a time.

    path = (
        PathBuilder((10, 10))
        .line_to((90, 10))
        .arc_circle_to(20, (90, 50), sweep_cw=True)
        .close()
        .build()
    )
    """

    def __init__(self, start: tuple[float, float] | Point):
        self._subs: list[SubPath] = []
        self._start = _coerce_point(start)
        self._current = self._start
        self._instructions: list[Instruction] = []

    def _push(self, instr: Instruction, to: Point) -> PathBuilder:
        self._instructions.append(instr)
        self._current = to
        return self

    def move_to(self, pt: tuple[float, float] | Point) -> PathBuilder:
        """Finish the current subpath and start a new one at `pt`."""
        self._subs.append(SubPath(self._start, tuple(self._instructions)))
        self._start = self._current = _coerce_point(pt)
        self._instructions = []
        return self

    def line_to(self, to: tuple[float, float] | Point) -> PathBuilder:
        return self._push(Line(_coerce_point(to)), _coerce_point(to))

    def quad_to(
        self, ctrl: tuple[float, float] | Point, to: tuple[float, float] | Point
    ) -> PathBuilder:
        return self._push(Quad(_coerce_point(ctrl), _coerce_point(to)), _coerce_point(to))

    def cubic_to(
        self,
        c1: tuple[float, float] | Point,
        c2: tuple[float, float] | Point,
        to: tuple[float, float] | Point,
    ) -> PathBuilder:
        target = _coerce_point(to)
        return self._push(Cubic(_coerce_point(c1), _coerce_point(c2), target), target)

    def arc_circle_to(
        self,
        radius: float,
        to: tuple[float, float] | Point,
        large: bool = False,
        sweep_cw: bool = True,
    ) -> PathBuilder:
        target = _coerce_point(to)
        return self._push(ArcCircle(radius, large, sweep_cw, target), target)

    def arc_ellipse_to(
        self,
        rx: float,
        ry: float,
        rotation_deg: float,
        to: tuple[float, float] | Point,
        large: bool = False,
        sweep_cw: bool = True,
    ) -> PathBuilder:
        return self._push(
            ArcEllipse(rx, ry, rotation_deg, large, sweep_cw, _coerce_point(to)),
            _coerce_point(to),
        )

    def close(self) -> PathBuilder:
        self._instructions.append(Close())
        self._current = self._start
        return self

    def build(self) -> Path:
        if self._instructions or not self._subs:
            self._subs.append(SubPath(self._start, tuple(self._instructions)))
        return Path(self._subs)
