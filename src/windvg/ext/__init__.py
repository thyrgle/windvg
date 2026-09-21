"""Optional extensions on top of the windvg core.

Everything here is importable from the main package namespace of your own
code, e.g.::

    from windvg.ext import Transform, transformed, along
"""

from .repeat import along, grid, polar, sample
from .transform import (
    Transform,
    mirrored_x,
    mirrored_y,
    rotated,
    scaled,
    transformed,
    translated,
)

__all__ = [
    "Transform",
    "along",
    "grid",
    "mirrored_x",
    "mirrored_y",
    "polar",
    "rotated",
    "sample",
    "scaled",
    "transformed",
    "translated",
]
