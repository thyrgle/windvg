# windvg

Parametric perimeter drawing in pure Python. Draw polygons and circles, place
**anchors** on their boundaries by traveling a percentage of the perimeter from a
start point in a chosen winding direction, and export scenes to
[TinyVG](https://tinyvg.tech) (compact binary vector graphics) or SVG.

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

## Concepts

Every shape is a 1D track: its boundary has a total length (`perimeter()`), an
origin, and a positive direction (visually clockwise on screen — TinyVG and SVG
both have y pointing down).

- **`Circle(center, radius)`** — origin at the rightmost point.
- **`Polygon(points)`** — origin at the first vertex; the positive direction is
  defined by the shape's *winding*, not the order you happened to list the
  vertices, so CW anchors always travel clockwise on screen.
- **`Polyline(points)`** — an open, stroke-only chain; CW means forward along it.

An anchor fixes a start location plus a direction:

```python
anchor = circle.anchor(start=(160, 100), direction=wv.CW)
pt = anchor.point(25)        # 25% of the perimeter, clockwise from start
pt = anchor.point(150)       # >100% wraps around via modulo
same = anchor.point(-20)     # negative travels backwards
```

The start point can be *any* (x, y) — it is projected to the nearest location on
the boundary. Since direction and winding are separated from vertex order,
`anchor.point(25)` on a circle and on any polygon mean the same thing: travel a
quarter of the perimeter, clockwise, from where you started.

Anchors work across shapes, which is where it gets fun:

```python
a = square.anchor((70, 50), wv.CW)
b = circle.anchor((160, 135), wv.CCW)
chord = wv.connect((a, 25), (b, 60))   # square@25% to circle@60%
scene.stroke(chord, wv.BLACK, width=2.0)
polygon = wv.polygon_from_anchors([(a, 0), (b, 30), (a, 60), (b, 90)])
```

Anchors also know where they are heading: `anchor.tangent(pct)` is the unit
travel direction, and `anchor.offset(pct, d)` displaces perpendicular to it
(positive `d` is left of travel — outward for clockwise tracks).

## Extensions (`windvg.ext`)

The core stays small; richer tools live in `windvg.ext`:

- **`Transform`** — immutable affine transforms. `transformed(shape, t)` bakes
  one into a new shape (`translated`/`rotated`/`scaled`/`mirrored_x`/
  `mirrored_y` are shorthands). Circles under uniform transforms stay circles;
  under non-uniform scaling they become exact ellipses; warped arcs become
  exact elliptical-arc paths.
- **`sample(shape, n, offset)` / `along(track, motifs, n, align="tangent")` /
  `polar(...)` / `grid(...)`** — repetition. Place motif shapes evenly around
  any track, optionally rotated to follow it: petals, gear teeth, rosettes.
- **`rounded(polygon, radius)`** — exact arc fillets on every corner
  (a fillable `Path`, not a polyline approximation).

## Paths and holes

`Path` chains line, quadratic, cubic, and arc instructions into one track —
and multiple subpaths into one shape. Fills use the even-odd rule, so an
inner subpath carves a hole; `Compound([outer, inner])` does the same for
whole shapes:

```python
ring = wv.Compound([wv.Circle((120, 120), 90), wv.Circle((120, 120), 55)])
scene.fill(ring, wv.rgb(0.9, 0.3, 0.2))
```

## Gradients

Use a gradient anywhere a color is welcome; its endpoint colors join the
file's palette automatically:

```python
scene.fill(
    circle,
    wv.LinearGradient((20, 20), (140, 140), wv.rgb(0.15, 0.4, 0.95), wv.rgb(1, 0.75, 0.25)),
)
scene.outline_fill(
    square,
    wv.RadialGradient(square_center, top_edge, wv.rgb(1, 0.9, 0.3), wv.rgb(0.75, 0.15, 0.35)),
    wv.BLACK,
)
```

## API overview

| Piece | Purpose |
| --- | --- |
| `Point`, `Color`, `rgb`/`rgba`, `LinearGradient`, `RadialGradient` | primitives and paints |
| `Circle`, `Ellipse`, `Arc`, `Polygon`, `Polyline`, `Path`, `Compound` | the shapes |
| `shape.anchor(start, direction)` | project a point onto the boundary |
| `anchor.point(pct)`, `anchor.at(pct)` | travel along the track |
| `anchor.tangent(pct)`, `anchor.offset(pct, d)` | direction of travel; perpendicular displacement (d > 0 = left of travel) |
| `regular_polygon`, `star`, `star_polygon`, `polygon_from_anchors`, `connect` | builders |
| `Scene.fill/stroke/outline_fill` | ordered draw operations (`visible=False` for guide geometry) |
| `scene.write_tinyvg(path)` | TinyVG 1.0 binary (`.tvg`) |
| `scene.write_svg(path)` | SVG with gradients for previews |
| `scene.to_tvgt()` | human-readable debug dump |
| `windvg.ext` | transforms, repetition, rounded corners |

## Examples

The `examples/` folder doubles as a tour: `star.py` (anchors), `gears.py`
(tangent-aligned repetition), `donut.py` (holes), `orbits.py` (ellipses,
arcs, normals), `rounded_star.py` (fillets + transforms),
`gradient_demo.py`, and `connect_shapes.py` (anchors across shapes).

## TinyVG notes

- Output is spec-conformant TinyVG 1.0: RGBA8888 palette, flat-colored styles,
  and exact circles built from two arc-circle instructions (no polygonal
  flattening).
- Coordinates are fixed-point (16-bit units by default, `scale=4` fraction bits
  → 1/16 precision); scenes that need more room automatically switch to 32-bit
  units.
- Polygons with more than 64 points fall back from `outline fill polygon` to a
  fill + line loop pair, per the spec's command limits.

## Development

```bash
uv sync              # install dev dependencies
uv run pytest        # run the test suite (includes a spec-based TVG reader)
uv run ruff check    # lint
uv run python examples/star.py            # generate example output
uv run python examples/connect_shapes.py
```

Rendered `.tvg` files can be previewed with the official tools from
[tinyvg.tech](https://tinyvg.tech) (`tinyvg render out.tvg out.png`), or just
open the `.svg` twin in a browser.
