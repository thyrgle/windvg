# windvg

Parametric perimeter drawing in pure Python. Every shape is a **1D track**:
place **anchors** on its boundary by traveling a percentage of the perimeter
from a start point in a chosen winding direction, connect anchors across
shapes, and export to [TinyVG](https://tinyvg.tech) (compact binary vector
graphics) or SVG.

```python
import windvg as wv

circle = wv.Circle((100, 100), 70)

# a pentagram: 5 anchors evenly around the circle, connected every 2nd one
pentagram = wv.star_polygon(circle, 5, 2)

scene = wv.Scene(200, 200)
scene.fill(pentagram, wv.rgb(0.95, 0.8, 0.2))
scene.stroke(circle, wv.rgb(0.2, 0.2, 0.25), width=1.5)
scene.write_tinyvg("star.tvg")
scene.write_svg("star.svg")
```

Draw directly with scenes, or edit parametric {doc}`documents
<documents>` that round-trip to readable Python — the layer editors are
built on.

## Installation

windvg has no runtime dependencies and requires Python 3.12+.

```bash
uv add path/to/windvg      # from another uv project
uv sync                    # or develop inside this repository
```

## A tour

```{toctree}
:maxdepth: 2
:caption: Guide

concepts
documents
ext
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
language
format-review
```

## Where things live

| Piece | Purpose |
| --- | --- |
| `windvg` | shapes, anchors, paints, builders, scenes, document classes |
| `windvg.ext` | transforms, repetition, rounded corners |
| `windvg.document` | the `Document`/`Node` model and its specs |
| `examples/` | runnable tour: stars, gears, donuts, orbits, gradients |
