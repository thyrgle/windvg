"""Serializable, parametric scene documents.

A Document is the persistent form of a drawing: an ordered list of named,
visible-or-hidden nodes, each an operation (fill/stroke/outline_fill) over a
parametric shape spec with a paint. Documents convert to and from plain JSON
dicts, resolve to a renderable Scene, and translate to and from readable
Python source — the round trip editors need:

    code ──Document.from_code──▶ document ──resolve──▶ Scene ──▶ TinyVG/SVG
      ▲                            │
      └──────generate_code─────────┘

Points inside specs may be literal [x, y] pairs or parametric references:
{"anchor": {"node": "gear", "pct": 25, "direction": "cw"}} — resolved against
another node's shape — or {"grid_cell": {"node": "grid1", "col": 1, "row": 0}}
— resolved against a grid guide's lattice. References keep visual edits
parametric: the generated code never hardcodes resolved pixel positions.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass, field

from .color import BLACK, Color
from .geometry import Point
from .gradient import LinearGradient, RadialGradient
from .path import (
    ArcCircle,
    Close,
    Line as LineInstr,
    Path,
    SubPath,
    instruction_from_dict,
)
from .scene import Scene
from .shapes import Arc, Circle, Ellipse, Orientation, Polygon, Polyline, Shape

__all__ = [
    "AlongSpec",
    "AnchorPoint",
    "ArcSpec",
    "BetweenPoint",
    "CircleSpec",
    "CompoundSpec",
    "Document",
    "EllipseSpec",
    "GridCellPoint",
    "GridGuideSpec",
    "GridSpec",
    "Node",
    "PathSpec",
    "PieSpec",
    "PointSpec",
    "PolarSpec",
    "PolySpec",
    "RectSpec",
    "RoundedSpec",
    "TransformSpec",
]

PointSpec = "Point | AnchorPoint | list[float] | dict"
ShapeSpec = "Shape | spec | dict"

_ORIENT = {Orientation.CW: "cw", Orientation.CCW: "ccw"}
_ORIENT_BACK = {v: k for k, v in _ORIENT.items()}


@dataclass(frozen=True, slots=True)
class AnchorPoint:
    """A point parametrically tied to another node's shape.

    Resolves to the point reached by traveling ``pct`` percent of the
    referenced shape's perimeter from ``start`` (its origin when omitted) in
    ``direction``.
    """

    node: str
    pct: float = 0.0
    start: Point | None = None
    direction: Orientation = Orientation.CW

    def to_dict(self) -> dict:
        payload: dict = {"node": self.node, "pct": self.pct}
        if self.start is not None:
            payload["start"] = [self.start.x, self.start.y]
        if self.direction is not Orientation.CW:
            payload["direction"] = _ORIENT[self.direction]
        return {"anchor": payload}

    @staticmethod
    def from_dict(d: dict) -> AnchorPoint:
        payload = d["anchor"]
        start = payload.get("start")
        return AnchorPoint(
            node=payload["node"],
            pct=payload.get("pct", 0.0),
            start=None if start is None else Point(start[0], start[1]),
            direction=_ORIENT_BACK[payload.get("direction", "cw")],
        )


@dataclass(frozen=True, slots=True)
class GridCellPoint:
    """A point expressed in another node's grid-guide cell coordinates.

    Resolves to the referenced grid's ``origin + (col * dx, row * dy)``, plus
    ``offset`` when given, so a shape can snap to cell (1, 0) while staying
    parametric — the generated code never hardcodes the pixel position.
    """

    node: str
    col: int
    row: int
    offset: Point | None = None

    def to_dict(self) -> dict:
        payload: dict = {"node": self.node, "col": self.col, "row": self.row}
        if self.offset is not None:
            payload["offset"] = [self.offset.x, self.offset.y]
        return {"grid_cell": payload}

    @staticmethod
    def from_dict(d: dict) -> "GridCellPoint":
        payload = d["grid_cell"]
        offset = payload.get("offset")
        return GridCellPoint(
            node=payload["node"],
            col=int(payload["col"]),
            row=int(payload["row"]),
            offset=None if offset is None else Point(offset[0], offset[1]),
        )


@dataclass(frozen=True, slots=True)
class BetweenPoint:
    """The linear blend of two resolved points: ``a + (b - a) * pct / 100``.

    ``pct`` is unrestricted — values outside ``[0, 100]`` extrapolate along
    the a–b line. Operands resolve recursively and may themselves be
    anchors, grid cells, or further ``between`` blends.
    """

    a: object
    b: object
    pct: float

    def to_dict(self) -> dict:
        return {
            "between": {
                "a": _point_to_dict(self.a),
                "b": _point_to_dict(self.b),
                "pct": self.pct,
            }
        }

    @staticmethod
    def from_dict(d: dict) -> "BetweenPoint":
        payload = d["between"]
        return BetweenPoint(
            a=_point_from_dict(payload["a"]),
            b=_point_from_dict(payload["b"]),
            pct=float(payload["pct"]),
        )


def _point_to_dict(pt) -> list | dict:
    if isinstance(pt, (AnchorPoint, GridCellPoint, BetweenPoint)):
        return pt.to_dict()
    if isinstance(pt, Point):
        return [pt.x, pt.y]
    if isinstance(pt, (list, tuple)):
        return [pt[0], pt[1]]
    if isinstance(pt, dict):
        return pt
    raise TypeError(f"cannot serialize point {pt!r}")


def _point_from_dict(d: list | dict):
    if isinstance(d, dict):
        if "anchor" in d:
            return AnchorPoint.from_dict(d)
        if "grid_cell" in d:
            return GridCellPoint.from_dict(d)
        if "between" in d:
            return BetweenPoint.from_dict(d)
        raise ValueError(f"unknown point reference {sorted(d)!r}")
    return Point(d[0], d[1])


def _color_to_dict(c: Color) -> dict:
    return {"kind": "color", "rgba": [c.r, c.g, c.b, c.a]}


def _paint_to_dict(paint) -> dict:
    if isinstance(paint, Color):
        return _color_to_dict(paint)
    if isinstance(paint, LinearGradient):
        return {
            "kind": "linear",
            "start": [paint.start.x, paint.start.y],
            "end": [paint.end.x, paint.end.y],
            "start_color": _color_to_dict(paint.start_color)["rgba"],
            "end_color": _color_to_dict(paint.end_color)["rgba"],
        }
    if isinstance(paint, RadialGradient):
        return {
            "kind": "radial",
            "center": [paint.center.x, paint.center.y],
            "edge": [paint.edge.x, paint.edge.y],
            "center_color": _color_to_dict(paint.center_color)["rgba"],
            "edge_color": _color_to_dict(paint.edge_color)["rgba"],
        }
    raise TypeError(f"cannot serialize paint {type(paint).__name__}")


def _paint_from_dict(d: dict):
    if d["kind"] == "color":
        r, g, b, a = d["rgba"]
        return Color(r, g, b, a)
    if d["kind"] == "linear":
        start, end = d["start"], d["end"]
    elif d["kind"] == "radial":
        start, end = d["center"], d["edge"]
    else:
        raise ValueError(f"unknown paint kind {d['kind']}")
    if d["kind"] == "linear":
        c0, c1 = Color(*d["start_color"]), Color(*d["end_color"])
        return LinearGradient(Point(start[0], start[1]), Point(end[0], end[1]), c0, c1)
    c0, c1 = Color(*d["center_color"]), Color(*d["edge_color"])
    return RadialGradient(Point(start[0], start[1]), Point(end[0], end[1]), c0, c1)


def _shape_to_dict(shape) -> dict:
    if isinstance(shape, Circle):
        return {
            "kind": "circle",
            "center": [shape.center.x, shape.center.y],
            "radius": shape.radius,
        }
    if isinstance(shape, Ellipse):
        return {
            "kind": "ellipse",
            "center": [shape.center.x, shape.center.y],
            "rx": shape.rx,
            "ry": shape.ry,
            "rotation_deg": shape.rotation_deg,
        }
    if isinstance(shape, Arc):
        return {
            "kind": "arc",
            "center": [shape.center.x, shape.center.y],
            "radius": shape.radius,
            "start_deg": shape.start_deg,
            "sweep_deg": shape.sweep_deg,
        }
    if isinstance(shape, Path):
        return shape.to_dict()
    kind = "polygon" if not isinstance(shape, Polyline) else "polyline"
    return {"kind": kind, "points": [[p.x, p.y] for p in shape.points]}


def _shape_from_dict(d: dict):
    kind = d["kind"]
    if kind == "circle":
        return Circle(Point(d["center"][0], d["center"][1]), d["radius"])
    if kind == "ellipse":
        return Ellipse(
            Point(d["center"][0], d["center"][1]),
            d["rx"],
            d["ry"],
            d.get("rotation_deg", 0.0),
        )
    if kind == "arc":
        return Arc(
            Point(d["center"][0], d["center"][1]),
            d["radius"],
            d["start_deg"],
            d["sweep_deg"],
        )
    if kind == "polygon":
        return Polygon([Point(p[0], p[1]) for p in d["points"]])
    if kind == "polyline":
        return Polyline([Point(p[0], p[1]) for p in d["points"]])
    if kind == "path":
        return Path.from_dict(d)
    raise ValueError(f"unknown shape kind {kind}")


@dataclass(frozen=True, slots=True)
class CircleSpec:
    center: object
    radius: float


@dataclass(frozen=True, slots=True)
class EllipseSpec:
    center: object
    rx: float
    ry: float
    rotation_deg: float = 0.0


@dataclass(frozen=True, slots=True)
class ArcSpec:
    center: object
    radius: float
    start_deg: float
    sweep_deg: float


@dataclass(frozen=True, slots=True)
class PolySpec:
    closed: bool
    points: tuple


@dataclass(frozen=True, slots=True)
class PathSpec:
    subpaths: tuple  # of (start_point_spec, [instruction dicts])


@dataclass(frozen=True, slots=True)
class CompoundSpec:
    shapes: tuple


@dataclass(frozen=True, slots=True)
class AlongSpec:
    track: object
    motifs: tuple
    n: int
    offset_pct: float = 0.0
    align: str | None = "tangent"
    direction: Orientation = Orientation.CW


@dataclass(frozen=True, slots=True)
class PolarSpec:
    center: object
    motifs: tuple
    n: int
    radius: float
    start_deg: float = 0.0
    align: str | None = None


@dataclass(frozen=True, slots=True)
class GridSpec:
    motifs: tuple
    cols: int
    rows: int
    dx: float
    dy: float
    origin: object = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class GridGuideSpec:
    """A non-drawing lattice used for snapping and grid-cell references.

    Expands to no shapes, so a grid-guide node renders and exports nothing;
    ``grid_cell`` point references resolve against its origin and spacing.
    """

    origin: object = (0.0, 0.0)
    cols: int = 8
    rows: int = 6
    dx: float = 40.0
    dy: float = 40.0


@dataclass(frozen=True, slots=True)
class RoundedSpec:
    shape: object
    radius: float


@dataclass(frozen=True, slots=True)
class RectSpec:
    """An axis-aligned rectangle (parametric center), resolving to a
    clockwise-on-screen polygon: top-left, top-right, bottom-right,
    bottom-left."""

    center: object
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class PieSpec:
    """A closed wedge (`chord=False`: start, arc, line to center, close) or
    chord (`chord=True`: start, arc, close) built from an arc."""

    center: object
    radius: float
    start_deg: float
    sweep_deg: float
    chord: bool = False


@dataclass(frozen=True, slots=True)
class TransformSpec:
    """A shape with an affine transform baked at resolve time. The matrix is
    six coefficients ``(a, b, c, d, e, f)`` with
    ``x' = a*x + c*y + e; y' = b*x + d*y + f``."""

    t: tuple  # (a, b, c, d, e, f)
    shape: object


_GENERATOR_KINDS = {"along", "polar", "grid", "rounded"}


class _Resolver:
    def __init__(self, document: Document):
        self.document = document

    def first_shape_of(self, ref: str) -> Shape:
        node = self.document.get(ref)
        shapes = self.expand(node.shape)
        if not shapes:
            raise ValueError(f"node {ref!r} expands to no shapes")
        return shapes[0]

    def resolve_point(self, pt) -> Point:
        if isinstance(pt, dict):
            pt = _point_from_dict(pt)
        if isinstance(pt, AnchorPoint):
            shape = self.first_shape_of(pt.node)
            hint = pt.start if pt.start is not None else shape.point_at_distance(0.0)
            return shape.anchor(hint, pt.direction).point(pt.pct)
        if isinstance(pt, BetweenPoint):
            pa = self.resolve_point(pt.a)
            pb = self.resolve_point(pt.b)
            t = pt.pct / 100.0
            return Point(pa.x + (pb.x - pa.x) * t, pa.y + (pb.y - pa.y) * t)
        if isinstance(pt, GridCellPoint):
            node = self.document.get(pt.node)
            grid = (
                _spec_from_dict(node.shape) if isinstance(node.shape, dict) else node.shape
            )
            if not isinstance(grid, GridGuideSpec):
                raise ValueError(f"node {pt.node!r} is not a grid guide")
            origin = grid.origin
            if not isinstance(origin, Point):
                origin = Point(origin[0], origin[1])
            p = Point(origin.x + pt.col * grid.dx, origin.y + pt.row * grid.dy)
            if pt.offset is not None:
                p = p + pt.offset
            return p
        if isinstance(pt, Point):
            return pt
        if isinstance(pt, (list, tuple)):
            return Point(pt[0], pt[1])
        raise TypeError(f"cannot resolve point {pt!r}")

    def expand(self, spec) -> list[Shape]:
        if spec is None:
            raise ValueError("missing shape spec")
        if isinstance(spec, Shape):
            return [spec]
        if isinstance(spec, dict):
            spec = _spec_from_dict(spec)
        if isinstance(spec, GridGuideSpec):
            return []
        if isinstance(spec, (CircleSpec, EllipseSpec, ArcSpec, RectSpec, PieSpec)):
            return [self._atomic_shape(spec)]
        if isinstance(spec, TransformSpec):
            from .ext.transform import Transform, transformed

            t = Transform(*spec.t)
            return [
                transformed(s, t) for s in self.expand(spec.shape)
            ]
        if isinstance(spec, PolySpec):
            points = [self.resolve_point(p) for p in spec.points]
            if spec.closed:
                return [Polygon(points)]
            return [Polyline(points)]
        if isinstance(spec, PathSpec):
            subs = []
            for start, instrs in spec.subpaths:
                start_pt = self.resolve_point(start)
                resolved = []
                for d in instrs:
                    instr = dict(d)
                    for key in ("to", "ctrl", "c1", "c2"):
                        if key in instr:
                            instr[key] = list(self.resolve_point(instr[key]))
                    resolved.append(instruction_from_dict(instr))
                subs.append(SubPath(start_pt, tuple(resolved)))
            return [Path(subs)]
        if isinstance(spec, CompoundSpec):
            shapes: list[Shape] = []
            for child in spec.shapes:
                shapes.extend(self.expand(child))
            from .shapes import Compound

            return [Compound(shapes)]
        if isinstance(spec, (AlongSpec, PolarSpec, GridSpec)):
            return self._expand_generator(spec)
        if isinstance(spec, RoundedSpec):
            from .ext.rounded import rounded

            inner = self.expand(spec.shape)
            if len(inner) != 1:
                raise ValueError("rounded() needs exactly one shape")
            return [rounded(inner[0], spec.radius)]
        raise TypeError(f"cannot resolve shape spec {type(spec).__name__}")

    def _atomic_shape(self, spec) -> Shape:
        if isinstance(spec, CircleSpec):
            return Circle(self.resolve_point(spec.center), spec.radius)
        if isinstance(spec, EllipseSpec):
            return Ellipse(
                self.resolve_point(spec.center), spec.rx, spec.ry, spec.rotation_deg
            )
        if isinstance(spec, RectSpec):
            c = self.resolve_point(spec.center)
            hw, hh = spec.width / 2.0, spec.height / 2.0
            return Polygon(
                [
                    Point(c.x - hw, c.y - hh),
                    Point(c.x + hw, c.y - hh),
                    Point(c.x + hw, c.y + hh),
                    Point(c.x - hw, c.y + hh),
                ]
            )
        if isinstance(spec, PieSpec):
            import math

            c = self.resolve_point(spec.center)
            r = spec.radius
            rad0 = math.radians(spec.start_deg)
            rad1 = math.radians(spec.start_deg + spec.sweep_deg)
            start = Point(c.x + r * math.cos(rad0), c.y + r * math.sin(rad0))
            end = Point(c.x + r * math.cos(rad1), c.y + r * math.sin(rad1))
            instructions: list = [
                ArcCircle(
                    r,
                    large=abs(spec.sweep_deg) > 180.0,
                    sweep_cw=spec.sweep_deg > 0.0,
                    to=end,
                )
            ]
            if not spec.chord:
                instructions.append(LineInstr(c))
            instructions.append(Close())
            return Path([SubPath(start, tuple(instructions))])
        return Arc(
            self.resolve_point(spec.center), spec.radius, spec.start_deg, spec.sweep_deg
        )

    def _expand_generator(self, spec):
        from .ext.repeat import along, grid, polar

        motifs = []
        for motif in spec.motifs:
            motifs.extend(self.expand(motif))
        if isinstance(spec, AlongSpec):
            track = self.expand(spec.track)
            if len(track) != 1:
                raise ValueError("along() track must expand to exactly one shape")
            return along(
                track[0], motifs, spec.n, spec.offset_pct, spec.align, spec.direction
            )
        if isinstance(spec, PolarSpec):
            return polar(
                self.resolve_point(spec.center),
                motifs,
                spec.n,
                spec.radius,
                spec.start_deg,
                spec.align,
            )
        return grid(
            motifs, spec.cols, spec.rows, spec.dx, spec.dy, self.resolve_point(spec.origin)
        )


@dataclass
class Node:
    id: str
    name: str
    op: str
    shape: object
    paint: object
    visible: bool = True
    stroke_width: float = 1.0
    outline_paint: object = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "op": self.op,
            "visible": self.visible,
            "shape": _spec_to_dict(self.shape),
            "paint": _paint_to_dict(self.paint),
            "stroke_width": self.stroke_width,
        }
        if self.outline_paint is not None:
            d["outline_paint"] = _paint_to_dict(self.outline_paint)
        return d

    @staticmethod
    def from_dict(d: dict) -> Node:
        return Node(
            id=d["id"],
            name=d["name"],
            op=d["op"],
            shape=_spec_from_dict(d["shape"]),
            paint=_paint_from_dict(d["paint"]),
            visible=d.get("visible", True),
            stroke_width=d.get("stroke_width", 1.0),
            outline_paint=_paint_from_dict(d["outline_paint"])
            if "outline_paint" in d
            else None,
        )


def _spec_to_dict(spec) -> dict:
    if isinstance(spec, Shape):
        return _shape_to_dict(spec)
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, CircleSpec):
        return {
            "kind": "circle",
            "center": _point_to_dict(spec.center),
            "radius": spec.radius,
        }
    if isinstance(spec, EllipseSpec):
        return {
            "kind": "ellipse",
            "center": _point_to_dict(spec.center),
            "rx": spec.rx,
            "ry": spec.ry,
            "rotation_deg": spec.rotation_deg,
        }
    if isinstance(spec, ArcSpec):
        return {
            "kind": "arc",
            "center": _point_to_dict(spec.center),
            "radius": spec.radius,
            "start_deg": spec.start_deg,
            "sweep_deg": spec.sweep_deg,
        }
    if isinstance(spec, PolySpec):
        return {
            "kind": "polygon" if spec.closed else "polyline",
            "points": [_point_to_dict(p) for p in spec.points],
        }
    if isinstance(spec, PathSpec):
        return {
            "kind": "path",
            "subpaths": [
                {
                    "start": _point_to_dict(start),
                    "instructions": list(instrs),
                }
                for start, instrs in spec.subpaths
            ],
        }
    if isinstance(spec, CompoundSpec):
        return {"kind": "compound", "shapes": [_spec_to_dict(s) for s in spec.shapes]}
    if isinstance(spec, AlongSpec):
        return {
            "kind": "along",
            "track": _spec_to_dict(spec.track),
            "motifs": [_spec_to_dict(m) for m in spec.motifs],
            "n": spec.n,
            "offset_pct": spec.offset_pct,
            "align": spec.align,
            "direction": _ORIENT[spec.direction],
        }
    if isinstance(spec, PolarSpec):
        return {
            "kind": "polar",
            "center": _point_to_dict(spec.center),
            "motifs": [_spec_to_dict(m) for m in spec.motifs],
            "n": spec.n,
            "radius": spec.radius,
            "start_deg": spec.start_deg,
            "align": spec.align,
        }
    if isinstance(spec, GridSpec):
        return {
            "kind": "grid",
            "motifs": [_spec_to_dict(m) for m in spec.motifs],
            "cols": spec.cols,
            "rows": spec.rows,
            "dx": spec.dx,
            "dy": spec.dy,
            "origin": _point_to_dict(spec.origin),
        }
    if isinstance(spec, GridGuideSpec):
        return {
            "kind": "grid_guide",
            "origin": _point_to_dict(spec.origin),
            "cols": spec.cols,
            "rows": spec.rows,
            "dx": spec.dx,
            "dy": spec.dy,
        }
    if isinstance(spec, RoundedSpec):
        return {
            "kind": "rounded",
            "shape": _spec_to_dict(spec.shape),
            "radius": spec.radius,
        }
    if isinstance(spec, RectSpec):
        return {
            "kind": "rect",
            "center": _point_to_dict(spec.center),
            "size": [spec.width, spec.height],
        }
    if isinstance(spec, PieSpec):
        return {
            "kind": "pie",
            "center": _point_to_dict(spec.center),
            "radius": spec.radius,
            "start_deg": spec.start_deg,
            "sweep_deg": spec.sweep_deg,
            "chord": spec.chord,
        }
    if isinstance(spec, TransformSpec):
        return {
            "kind": "transform",
            "t": list(spec.t),
            "shape": _spec_to_dict(spec.shape),
        }
    raise TypeError(f"cannot serialize shape spec {type(spec).__name__}")


def _spec_from_dict(d: dict):
    kind = d["kind"]
    if kind in ("circle", "ellipse", "arc", "polygon", "polyline", "path"):
        if kind == "circle":
            return CircleSpec(_point_from_dict(d["center"]), d["radius"])
        if kind == "ellipse":
            return EllipseSpec(
                _point_from_dict(d["center"]), d["rx"], d["ry"], d.get("rotation_deg", 0.0)
            )
        if kind == "arc":
            return ArcSpec(
                _point_from_dict(d["center"]), d["radius"], d["start_deg"], d["sweep_deg"]
            )
        if kind == "path":
            return PathSpec(
                tuple(
                    (
                        _point_from_dict(sub["start"]),
                        list(sub["instructions"]),
                    )
                    for sub in d["subpaths"]
                )
            )
        return PolySpec(kind == "polygon", tuple(_point_from_dict(p) for p in d["points"]))
    if kind == "compound":
        return CompoundSpec(tuple(_spec_from_dict(s) for s in d["shapes"]))
    if kind == "along":
        return AlongSpec(
            track=_spec_from_dict(d["track"]),
            motifs=tuple(_spec_from_dict(m) for m in d["motifs"]),
            n=d["n"],
            offset_pct=d.get("offset_pct", 0.0),
            align=d.get("align", "tangent"),
            direction=_ORIENT_BACK[d.get("direction", "cw")],
        )
    if kind == "polar":
        return PolarSpec(
            center=_point_from_dict(d["center"]),
            motifs=tuple(_spec_from_dict(m) for m in d["motifs"]),
            n=d["n"],
            radius=d["radius"],
            start_deg=d.get("start_deg", 0.0),
            align=d.get("align"),
        )
    if kind == "grid":
        return GridSpec(
            motifs=tuple(_spec_from_dict(m) for m in d["motifs"]),
            cols=d["cols"],
            rows=d["rows"],
            dx=d["dx"],
            dy=d["dy"],
            origin=_point_from_dict(d.get("origin", [0.0, 0.0])),
        )
    if kind == "grid_guide":
        return GridGuideSpec(
            origin=_point_from_dict(d.get("origin", [0.0, 0.0])),
            cols=int(d.get("cols", 8)),
            rows=int(d.get("rows", 6)),
            dx=d.get("dx", 40.0),
            dy=d.get("dy", 40.0),
        )
    if kind == "rounded":
        return RoundedSpec(_spec_from_dict(d["shape"]), d["radius"])
    if kind == "rect":
        return RectSpec(
            _point_from_dict(d["center"]), float(d["size"][0]), float(d["size"][1])
        )
    if kind == "pie":
        return PieSpec(
            _point_from_dict(d["center"]),
            d["radius"],
            d["start_deg"],
            d["sweep_deg"],
            chord=bool(d.get("chord", False)),
        )
    if kind == "transform":
        return TransformSpec(tuple(float(v) for v in d["t"]), _spec_from_dict(d["shape"]))
    raise ValueError(f"unknown shape spec kind {kind}")


@dataclass
class Document:
    """An ordered, named, editable drawing: the editor's source of truth."""

    width: float
    height: float
    nodes: list[Node] = field(default_factory=list)
    _counter: Iterator[int] = field(
        default_factory=lambda: itertools.count(1), repr=False, compare=False
    )

    def get(self, ref: str) -> Node:
        for node in self.nodes:
            if node.id == ref or node.name == ref:
                return node
        raise KeyError(f"no node {ref!r}")

    def _unique_name(self, name: str) -> str:
        if any(node.name == name for node in self.nodes):
            raise ValueError(f"duplicate node name {name!r}")
        return name

    def _new_id(self) -> str:
        return f"n{next(self._counter)}"

    def _add(self, node: Node) -> Node:
        self._unique_name(node.name)
        self.nodes.append(node)
        return node

    def fill(self, name: str, shape, paint, *, visible: bool = True) -> Node:
        return self._add(
            Node(self._new_id(), self._unique_name(name), "fill", shape, paint, visible)
        )

    def stroke(
        self, name: str, shape, paint, width: float = 1.0, *, visible: bool = True
    ) -> Node:
        return self._add(
            Node(
                self._new_id(),
                self._unique_name(name),
                "stroke",
                shape,
                paint,
                visible,
                width,
            )
        )

    def outline_fill(
        self,
        name: str,
        shape,
        paint,
        outline_paint,
        width: float = 1.0,
        *,
        visible: bool = True,
    ) -> Node:
        return self._add(
            Node(
                self._new_id(),
                self._unique_name(name),
                "outline_fill",
                shape,
                paint,
                visible,
                width,
                outline_paint,
            )
        )

    def anchor(
        self,
        node_ref: str,
        *,
        pct: float = 0.0,
        start=None,
        direction: Orientation = Orientation.CW,
    ) -> AnchorPoint:
        return AnchorPoint(
            node=node_ref,
            pct=pct,
            start=None if start is None else _as_point_value(start),
            direction=direction,
        )

    def grid(
        self,
        name: str,
        *,
        origin=(0.0, 0.0),
        cols: int = 8,
        rows: int = 6,
        dx: float = 40.0,
        dy: float = 40.0,
    ) -> Node:
        """Add a non-drawing grid guide: a lattice for snapping and
        ``grid_cell`` point references. Guides are invisible and export as
        nothing.
        """
        node = Node(
            self._new_id(),
            self._unique_name(name),
            "fill",
            GridGuideSpec(
                origin=_as_point_value(origin), cols=cols, rows=rows, dx=dx, dy=dy
            ),
            BLACK,
            visible=False,
        )
        return self._add(node)

    def grid_cell(self, node_ref: str, col: int, row: int, offset=None) -> GridCellPoint:
        """A point reference to a grid guide's cell ``(col, row)``, with an
        optional literal pixel ``offset`` preserving exact placement."""
        return GridCellPoint(
            node=node_ref,
            col=col,
            row=row,
            offset=None if offset is None else _as_point_value(offset),
        )

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "canvas": [self.width, self.height],
            "nodes": [node.to_dict() for node in self.nodes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Document:
        doc = cls(d["canvas"][0], d["canvas"][1])
        doc._counter = itertools.count(1)
        for node_dict in d["nodes"]:
            node = Node.from_dict(node_dict)
            doc._unique_name(node.name)
            doc.nodes.append(node)
            for _ in range(
                int(node.id[1:]) if node.id.startswith("n") and node.id[1:].isdigit() else 0
            ):
                next(doc._counter)
        return doc

    def resolve(self) -> Scene:
        scene = Scene(self.width, self.height)
        resolver = _Resolver(self)
        for node in self.nodes:
            if not node.visible:
                continue
            for shape in resolver.expand(node.shape):
                if node.op == "fill":
                    scene.fill(shape, node.paint)
                elif node.op == "stroke":
                    scene.stroke(shape, node.paint, node.stroke_width)
                elif node.op == "outline_fill":
                    scene.outline_fill(
                        shape, node.paint, node.outline_paint, node.stroke_width
                    )
                else:
                    raise ValueError(f"unknown op {node.op!r}")
        return scene

    def resolve_to_json(self) -> list[dict]:
        """Resolved draw ops with node identity, for editor canvases."""
        resolver = _Resolver(self)
        out = []
        for node in self.nodes:
            if not node.visible:
                continue
            for shape in resolver.expand(node.shape):
                lo, hi = shape.bbox()
                out.append(
                    {
                        "id": node.id,
                        "op": node.op,
                        "shape": _shape_to_dict(shape),
                        "paint": _paint_to_dict(node.paint),
                        "stroke_width": node.stroke_width,
                        "outline_paint": (
                            None
                            if node.outline_paint is None
                            else _paint_to_dict(node.outline_paint)
                        ),
                        "bbox": [lo.x, lo.y, hi.x, hi.y],
                    }
                )
        return out

    def generate_code(self) -> str:
        return _generate_code(self)

    @classmethod
    def from_code(cls, source: str) -> Document:
        """Execute editor-generated code (it must define a ``doc`` Document)."""
        namespace: dict = {}
        exec(compile(source, "<windstudio>", "exec"), namespace)
        doc = namespace.get("doc")
        if not isinstance(doc, Document):
            raise ValueError("code must define a `doc` windvg.document.Document")
        return doc

    @classmethod
    def from_scene_code(cls, source: str) -> Document:
        """Best-effort import of free-form Scene code; params bake, names auto-assign."""
        import windvg as wv_module

        captured: list[Scene] = []

        class RecordingScene(Scene):
            def __init__(self, width: float, height: float):
                super().__init__(width, height)
                captured.append(self)

            def fill(self, shape, paint, visible: bool = True) -> None:
                super().fill(shape, paint, visible)
                self._record("fill", shape, paint, None, 1.0, visible)

            def stroke(
                self, shape, paint, width: float = 1.0, visible: bool = True
            ) -> None:
                super().stroke(shape, paint, width, visible)
                self._record("stroke", shape, paint, None, width, visible)

            def outline_fill(
                self, shape, paint, outline_paint, width: float = 1.0, visible: bool = True
            ) -> None:
                super().outline_fill(shape, paint, outline_paint, width, visible)
                self._record("outline_fill", shape, paint, outline_paint, width, visible)

            def _record(self, op, shape, paint, outline_paint, width, visible):
                doc = captured_doc["doc"]
                name = f"shape_{len(doc.nodes) + 1}"
                doc._add(
                    Node(
                        doc._new_id(), name, op, shape, paint, visible, width, outline_paint
                    )
                )

        captured_doc = {"doc": cls(0, 0)}
        original_scene = wv_module.Scene
        captured_doc["doc"] = cls(0, 0)
        wv_module.Scene = RecordingScene
        try:
            exec(compile(source, "<windvg-import>", "exec"), {})
        finally:
            wv_module.Scene = original_scene

        scenes = [s for s in captured if s.ops]
        if not scenes:
            raise ValueError("code produced no draw operations")
        scene = scenes[-1]
        doc = cls(scene.width, scene.height)
        for i, op in enumerate(scene.ops, start=1):
            doc._add(
                Node(
                    doc._new_id(),
                    f"shape_{i}",
                    {
                        "FillOp": "fill",
                        "StrokeOp": "stroke",
                        "OutlineFillOp": "outline_fill",
                    }[op.__class__.__name__],
                    op.shape,
                    op.color,
                    op.visible,
                    getattr(op, "width", 1.0),
                    getattr(op, "outline_paint", None),
                )
            )
        return doc


def _as_point_value(pt) -> Point:
    return pt if isinstance(pt, Point) else Point(pt[0], pt[1])


def _fmt(value: float) -> str:
    # repr round-trips floats exactly; rounding here would break dict equality
    return repr(float(value))


def _point_expr(pt) -> str:
    if not isinstance(pt, Point):
        return f"({_fmt(pt[0])}, {_fmt(pt[1])})"
    return f"({_fmt(pt.x)}, {_fmt(pt.y)})"


def _dict_has_anchor(obj) -> bool:
    if isinstance(obj, dict):
        return (
            "anchor" in obj
            or "grid_cell" in obj
            or any(_dict_has_anchor(v) for v in obj.values())
        )
    if isinstance(obj, (list, tuple)):
        return any(_dict_has_anchor(v) for v in obj)
    return False


def _spec_has_anchor(spec) -> bool:
    if isinstance(spec, (AnchorPoint, GridCellPoint, BetweenPoint)):
        return True
    if isinstance(spec, (CircleSpec, EllipseSpec, ArcSpec, RectSpec, PieSpec)):
        return isinstance(spec.center, (AnchorPoint, GridCellPoint, BetweenPoint))
    if isinstance(spec, TransformSpec):
        return _spec_has_anchor(spec.shape)
    if isinstance(spec, PolySpec):
        return any(isinstance(p, (AnchorPoint, GridCellPoint)) for p in spec.points)
    if isinstance(spec, PathSpec):
        return any(
            isinstance(start, (AnchorPoint, GridCellPoint))
            or _dict_has_anchor(start)
            or any(_dict_has_anchor(i) for i in instrs)
            for start, instrs in spec.subpaths
        )
    if isinstance(spec, CompoundSpec):
        return any(_spec_has_anchor(child) for child in spec.shapes)
    if isinstance(spec, AlongSpec):
        return _spec_has_anchor(spec.track) or any(_spec_has_anchor(m) for m in spec.motifs)
    if isinstance(spec, PolarSpec):
        return _spec_has_anchor(spec.center) or any(
            _spec_has_anchor(m) for m in spec.motifs
        )
    if isinstance(spec, GridSpec):
        return _spec_has_anchor(spec.origin) or any(
            _spec_has_anchor(m) for m in spec.motifs
        )
    if isinstance(spec, GridGuideSpec):
        return False
    if isinstance(spec, RoundedSpec):
        return _spec_has_anchor(spec.shape)
    return False


def _spec_expr(spec) -> str:
    """Spec-constructor form: every point stays a resolvable PointSpec."""
    if isinstance(spec, Shape):
        return _shape_expr(spec)
    if isinstance(spec, CircleSpec):
        center = _point_spec_expr(spec.center)
        return f"wvd.CircleSpec(center={center}, radius={_fmt(spec.radius)})"
    if isinstance(spec, EllipseSpec):
        return (
            f"wvd.EllipseSpec(center={_point_spec_expr(spec.center)}, rx={_fmt(spec.rx)},"
            f" ry={_fmt(spec.ry)}, rotation_deg={_fmt(spec.rotation_deg)})"
        )
    if isinstance(spec, ArcSpec):
        center = _point_spec_expr(spec.center)
        radius = _fmt(spec.radius)
        return (
            f"wvd.ArcSpec(center={center}, radius={radius},"
            f" start_deg={_fmt(spec.start_deg)}, sweep_deg={_fmt(spec.sweep_deg)})"
        )
    if isinstance(spec, PolySpec):
        pts = ", ".join(_point_spec_expr(p) for p in spec.points)
        return f"wvd.PolySpec(closed={spec.closed!r}, points=({pts},))"
    if isinstance(spec, PathSpec):
        return f"wvd.PathSpec(subpaths={_pathspec_subpaths(spec)!r})"
    if isinstance(spec, CompoundSpec):
        inner = ", ".join(_spec_expr(child) for child in spec.shapes)
        return f"wvd.CompoundSpec(shapes=({inner},))"
    if isinstance(spec, (AlongSpec, PolarSpec, GridSpec, RoundedSpec)):
        return _generator_expr(spec)
    if isinstance(spec, RectSpec):
        center = _point_spec_expr(spec.center)
        return (
            f"wvd.RectSpec(center={center},"
            f" width={_fmt(spec.width)}, height={_fmt(spec.height)})"
        )
    if isinstance(spec, PieSpec):
        return (
            f"wvd.PieSpec(center={_point_spec_expr(spec.center)},"
            f" radius={_fmt(spec.radius)}, start_deg={_fmt(spec.start_deg)},"
            f" sweep_deg={_fmt(spec.sweep_deg)}, chord={spec.chord!r})"
        )
    if isinstance(spec, TransformSpec):
        t = ", ".join(_fmt(v) for v in spec.t)
        return f"wvd.TransformSpec(t=({t}), shape={_spec_expr(spec.shape)})"
    raise TypeError(f"cannot generate code for spec {type(spec).__name__}")


def _pathspec_subpaths(spec: PathSpec) -> list:
    return [
        {"start": _point_to_dict(start), "instructions": list(instrs)}
        for start, instrs in spec.subpaths
    ]


def _generator_expr(spec) -> str:
    if isinstance(spec, AlongSpec):
        track = _shape_expr(spec.track)
        motifs = ", ".join(
            _spec_expr(m) if _spec_has_anchor(m) else _shape_expr(m) for m in spec.motifs
        )
        return (
            f"wvd.AlongSpec(track={track}, motifs=({motifs},), n={spec.n},"
            f" offset_pct={_fmt(spec.offset_pct)}, align={spec.align!r},"
            f" direction=wv.{spec.direction.name})"
        )
    if isinstance(spec, PolarSpec):
        motifs = ", ".join(
            _spec_expr(m) if _spec_has_anchor(m) else _shape_expr(m) for m in spec.motifs
        )
        return (
            f"wvd.PolarSpec(center={_point_spec_expr(spec.center)}, motifs=({motifs},),"
            f" n={spec.n}, radius={_fmt(spec.radius)}, start_deg={_fmt(spec.start_deg)},"
            f" align={spec.align!r})"
        )
    if isinstance(spec, GridSpec):
        motifs = ", ".join(
            _spec_expr(m) if _spec_has_anchor(m) else _shape_expr(m) for m in spec.motifs
        )
        return (
            f"wvd.GridSpec(motifs=({motifs},), cols={spec.cols}, rows={spec.rows},"
            f" dx={_fmt(spec.dx)}, dy={_fmt(spec.dy)},"
            f" origin={_point_spec_expr(spec.origin)})"
        )
    return f"wvd.RoundedSpec(shape={_spec_expr(spec.shape)}, radius={_fmt(spec.radius)})"


def _point_spec_expr(pt) -> str:
    if isinstance(pt, BetweenPoint):
        return (
            f"wvd.BetweenPoint(a={_point_spec_expr(pt.a)},"
            f" b={_point_spec_expr(pt.b)}, pct={_fmt(pt.pct)})"
        )
    if isinstance(pt, AnchorPoint):
        args = f"{pt.node!r}, pct={_fmt(pt.pct)}"
        if pt.start is not None:
            args += f", start={_point_expr(pt.start)}"
        args += f", direction=wv.{pt.direction.name}"
        return f"doc.anchor({args})"
    if isinstance(pt, GridCellPoint):
        args = f"{pt.node!r}, {pt.col}, {pt.row}"
        if pt.offset is not None:
            args += f", offset={_point_expr(pt.offset)}"
        return f"doc.grid_cell({args})"
    return _point_expr(pt)


def _color_expr(c: Color) -> str:
    if c.a >= 1.0:
        return f"wv.rgb({_fmt(c.r)}, {_fmt(c.g)}, {_fmt(c.b)})"
    return f"wv.rgba({_fmt(c.r)}, {_fmt(c.g)}, {_fmt(c.b)}, {_fmt(c.a)})"


def _paint_expr(paint) -> str:
    if isinstance(paint, Color):
        return _color_expr(paint)
    if isinstance(paint, LinearGradient):
        return (
            f"wv.LinearGradient({_point_expr(paint.start)}, {_point_expr(paint.end)},"
            f" {_color_expr(paint.start_color)}, {_color_expr(paint.end_color)})"
        )
    if isinstance(paint, RadialGradient):
        return (
            f"wv.RadialGradient({_point_expr(paint.center)}, {_point_expr(paint.edge)},"
            f" {_color_expr(paint.center_color)}, {_color_expr(paint.edge_color)})"
        )
    raise TypeError(f"cannot generate code for paint {type(paint).__name__}")


def _shape_expr(spec) -> str:
    if _spec_has_anchor(spec):
        return _spec_expr(spec)
    if isinstance(spec, Shape):
        if isinstance(spec, Circle):
            return f"wv.Circle({_point_expr(spec.center)}, {_fmt(spec.radius)})"
        if isinstance(spec, Ellipse):
            return (
                f"wv.Ellipse({_point_expr(spec.center)}, {_fmt(spec.rx)}, {_fmt(spec.ry)},"
                f" rotation_deg={_fmt(spec.rotation_deg)})"
            )
        if isinstance(spec, Arc):
            return (
                f"wv.Arc({_point_expr(spec.center)}, {_fmt(spec.radius)},"
                f" {_fmt(spec.start_deg)}, {_fmt(spec.sweep_deg)})"
            )
        if isinstance(spec, (Polygon, Polyline)):
            fn = "Polygon" if isinstance(spec, Polygon) else "Polyline"
            pts = ", ".join(_point_expr(p) for p in spec.points)
            return f"wv.{fn}([{pts}])"
        if isinstance(spec, Path):
            return f"wv.Path.from_dict({spec.to_dict()!r})"
        raise TypeError(f"cannot generate code for shape {type(spec).__name__}")
    if isinstance(spec, CircleSpec):
        return f"wv.Circle({_point_spec_expr(spec.center)}, {_fmt(spec.radius)})"
    if isinstance(spec, EllipseSpec):
        return (
            f"wv.Ellipse({_point_spec_expr(spec.center)}, {_fmt(spec.rx)}, {_fmt(spec.ry)},"
            f" rotation_deg={_fmt(spec.rotation_deg)})"
        )
    if isinstance(spec, ArcSpec):
        return (
            f"wv.Arc({_point_spec_expr(spec.center)}, {_fmt(spec.radius)},"
            f" {_fmt(spec.start_deg)}, {_fmt(spec.sweep_deg)})"
        )
    if isinstance(spec, PolySpec):
        fn = "Polygon" if spec.closed else "Polyline"
        pts = ", ".join(_point_spec_expr(p) for p in spec.points)
        return f"wv.{fn}([{pts}])"
    if isinstance(spec, PathSpec):
        return f"wv.Path.from_dict({spec_to_codegen_dict(spec)!r})"
    if isinstance(spec, CompoundSpec):
        inner = ", ".join(_shape_expr(child) for child in spec.shapes)
        return f"wv.Compound([{inner}])"
    if isinstance(spec, AlongSpec):
        track = _shape_expr(spec.track)
        motifs = ", ".join(_shape_expr(m) for m in spec.motifs)
        return (
            f"wvd.AlongSpec(track={track}, motifs=({motifs},), n={spec.n},"
            f" offset_pct={_fmt(spec.offset_pct)}, align={spec.align!r},"
            f" direction=wv.{spec.direction.name})"
        )
    if isinstance(spec, PolarSpec):
        motifs = ", ".join(_shape_expr(m) for m in spec.motifs)
        return (
            f"wvd.PolarSpec(center={_point_spec_expr(spec.center)}, motifs=({motifs},),"
            f" n={spec.n}, radius={_fmt(spec.radius)}, start_deg={_fmt(spec.start_deg)},"
            f" align={spec.align!r})"
        )
    if isinstance(spec, GridSpec):
        motifs = ", ".join(_shape_expr(m) for m in spec.motifs)
        return (
            f"wvd.GridSpec(motifs=({motifs},), cols={spec.cols}, rows={spec.rows},"
            f" dx={_fmt(spec.dx)}, dy={_fmt(spec.dy)},"
            f" origin={_point_spec_expr(spec.origin)})"
        )
    if isinstance(spec, RoundedSpec):
        return (
            f"wvd.RoundedSpec(shape={_shape_expr(spec.shape)}, radius={_fmt(spec.radius)})"
        )
    if isinstance(spec, (RectSpec, PieSpec, TransformSpec)):
        return _spec_expr(spec)
    raise TypeError(f"cannot generate code for spec {type(spec).__name__}")


def spec_to_codegen_dict(spec) -> dict:
    return _spec_to_dict(spec)


def _spec_has_generator(spec) -> bool:
    if isinstance(spec, (AlongSpec, PolarSpec, GridSpec, RoundedSpec)):
        return True
    if isinstance(spec, CompoundSpec):
        return any(_spec_has_generator(child) for child in spec.shapes)
    return False


def _generate_code(doc: Document) -> str:
    lines = [
        "import windvg as wv",
        "from windvg import document as wvd",
        "from windvg.document import Document",
    ]
    lines += ["", f"doc = Document({_fmt(doc.width)}, {_fmt(doc.height)})"]
    for node in doc.nodes:
        lines.append("")
        lines.append(f"# {node.name}")
        shape = node.shape
        if isinstance(shape, dict):
            shape = _spec_from_dict(shape)
        if isinstance(shape, GridGuideSpec):
            origin = shape.origin
            if not isinstance(origin, Point):
                origin = Point(origin[0], origin[1])
            lines.append(
                f"doc.grid({node.name!r}, origin=({_fmt(origin.x)}, {_fmt(origin.y)}),"
                f" cols={shape.cols}, rows={shape.rows},"
                f" dx={_fmt(shape.dx)}, dy={_fmt(shape.dy)})"
            )
            continue
        call_args = [repr(node.name), _shape_expr(node.shape), _paint_expr(node.paint)]
        method = node.op
        if method == "outline_fill":
            call_args.append(_paint_expr(node.outline_paint))
        if method in ("stroke", "outline_fill"):
            call_args.append(f"width={_fmt(node.stroke_width)}")
        if not node.visible:
            call_args.append("visible=False")
        lines.append(f"doc.{method}({', '.join(call_args)})")
    return "\n".join(lines) + "\n"
