"""Bundled-font text baking (spec §7.19).

The resolver maps a text node's string through the bundled Noto Sans
Regular font (OFL 1.1) into filled paths: cmap lookup, per-character
advances from ``hmtx``, TrueType outlines (quadratics) flipped into
y-down canvas space, scaled by ``size / unitsPerEm``. Kerning is off in
v1. ``anchor`` shifts the pen origin by the measured advance width.
"""

from pathlib import Path as FsPath

from .geometry import Point
from .path import Close, Line, Path, Quad, SubPath

_FONT_FILE = FsPath(__file__).resolve().parent / "fonts" / "NotoSans-Regular.ttf"
_cache: dict = {}

ANCHOR_OFFSET = {"start": 0.0, "middle": 0.5, "end": 1.0}


def supported_fonts() -> list[str]:
    return ["sans"]


def _load():
    if "font" not in _cache:
        try:
            from fontTools.ttLib import TTFont
        except ImportError as e:  # pragma: no cover
            raise ValueError(
                "text requires the fonttools package (pip install fonttools)"
            ) from e
        if not _FONT_FILE.exists():
            raise ValueError(f"bundled font missing at {_FONT_FILE}")
        font = TTFont(str(_FONT_FILE), lazy=True)
        _cache["font"] = font
        _cache["cmap"] = font.getBestCmap()
        _cache["hmtx"] = font["hmtx"]
        _cache["glyf"] = font["glyf"]
        _cache["upem"] = font["head"].unitsPerEm
    return _cache


def measure(content: str, size: float, font: str = "sans") -> float:
    """Total advance width of [content] at [size] in [font]."""
    if font != "sans":
        raise ValueError(f"unknown font {font!r} (bundled: sans)")
    data = _load()
    cmap, hmtx, upem = data["cmap"], data["hmtx"], data["upem"]
    scale = size / upem
    return sum(hmtx[cmap.get(ord(ch), ".notdef")][0] for ch in content) * scale


def bake(
    at: Point, content: str, size: float, font: str = "sans", anchor: str = "start"
) -> list[Path]:
    """Bake [content] into filled paths with the baseline start (after
    [anchor] adjustment) at [at]. Returns one Path per glyph contour
    group; contours rely on even-odd for counters (holes)."""
    if font != "sans":
        raise ValueError(f"unknown font {font!r} (bundled: sans)")
    data = _load()
    cmap, hmtx, glyf = data["cmap"], data["hmtx"], data["glyf"]
    upem = data["upem"]
    scale = size / upem

    width = measure(content, size, font)
    pen_x0 = at.x - width * ANCHOR_OFFSET.get(anchor, 0.0)
    pen_y = at.y

    shapes: list[Path] = []
    pen_x = pen_x0
    for ch in content:
        gname = cmap.get(ord(ch), ".notdef")
        gobj = glyf[gname]
        adv = hmtx[gname][0] * scale
        if gobj.numberOfContours != 0:
            rec = _record(gobj, glyf)
            subpaths = _contours_to_subpaths(rec, pen_x, pen_y, scale)
            if subpaths:
                shapes.append(Path(subpaths))
        pen_x += adv
    return shapes


def _record(gobj, glyf):
    from fontTools.pens.recordingPen import RecordingPen

    pen = RecordingPen()
    gobj.draw(pen, glyf)
    return pen.value


def _contours_to_subpaths(rec_value, ox, oy, s):
    """Convert recorded glyph contours (font units, y-up) into SubPaths
    (canvas coords, y-down, quads kept exact)."""
    subpaths: list[SubPath] = []
    cur_start = None
    cur_instrs: list = []

    def emit_close(last_pt):
        if cur_instrs:
            subpaths.append(SubPath(cur_start, tuple(cur_instrs)))

    def fx(x):
        return ox + x * s

    def fy(y):
        return oy - y * s  # flip y-down

    for op, args in rec_value:
        if op == "moveTo":
            if cur_instrs:
                emit_close(cur_start)
            (x, y), = args
            cur_start = Point(fx(x), fy(y))
            cur_instrs = []
        elif op == "lineTo":
            (x, y), = args
            cur_instrs.append(Line(Point(fx(x), fy(y))))
        elif op == "qCurveTo":
            pts = list(args)
            # TrueType: implied on-curves at midpoints between consecutive
            # off-curves; last point is on-curve.
            if len(pts) == 1:
                # degenerate all-off-curve close: treat as line to it
                (x, y), = pts
                cur_instrs.append(Line(Point(fx(x), fy(y))))
                continue
            for i in range(len(pts) - 2):
                cx, cy = pts[i]
                nx, ny = pts[i + 1]
                mx, my = (cx + nx) / 2.0, (cy + ny) / 2.0
                cur_instrs.append(
                    Quad(Point(fx(cx), fy(cy)), Point(fx(mx), fy(my)))
                )
            cx, cy = pts[-2]
            tx, ty = pts[-1]
            cur_instrs.append(
                Quad(Point(fx(cx), fy(cy)), Point(fx(tx), fy(ty)))
            )
        elif op == "closePath":
            if cur_instrs:
                cur_instrs.append(Close())
                emit_close(cur_start)
                cur_start = None
                cur_instrs = []
        # curveTo (cubic) cannot occur in TrueType glyf outlines

    if cur_instrs:
        subpaths.append(SubPath(cur_start, tuple(cur_instrs)))
    return subpaths
