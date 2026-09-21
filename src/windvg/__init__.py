"""windvg: parametric perimeter drawing.

Draw polygons and circles, place anchors on their boundaries by traveling a
percentage of the perimeter from a start point in a chosen winding direction,
and export scenes to TinyVG or SVG.

    import windvg as wv

    circle = wv.Circle((100, 100), 60)
    scene = wv.Scene(200, 200)
    scene.fill(wv.star_polygon(circle, 5, 2), wv.rgb(0.95, 0.8, 0.2))
    scene.write_tinyvg("star.tvg")
    scene.write_svg("star.svg")
"""

from .anchor import Anchor
from .builders import connect, polygon_from_anchors, regular_polygon, star, star_polygon
from .color import (
    BLACK,
    BLUE,
    CYAN,
    GRAY,
    GREEN,
    MAGENTA,
    RED,
    WHITE,
    YELLOW,
    Color,
    rgb,
    rgba,
)
from .geometry import Point
from .scene import Scene
from .shapes import CCW, CW, Circle, Orientation, Polygon, Polyline, Shape

__version__ = "0.1.0"

__all__ = [
    "Anchor",
    "BLACK",
    "BLUE",
    "CCW",
    "CW",
    "CYAN",
    "Circle",
    "Color",
    "GRAY",
    "GREEN",
    "MAGENTA",
    "Orientation",
    "Point",
    "Polygon",
    "Polyline",
    "RED",
    "Scene",
    "Shape",
    "WHITE",
    "YELLOW",
    "__version__",
    "connect",
    "polygon_from_anchors",
    "regular_polygon",
    "rgb",
    "rgba",
    "star",
    "star_polygon",
]
