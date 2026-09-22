# Shapes and anchors

## Every shape is a track

Each shape's boundary has a total length ({meth}`perimeter()
<windvg.shapes.Shape.perimeter>`), an **origin**, and a **positive
direction** — visually clockwise on screen, matching TinyVG and SVG (both
have y pointing down).

- **`Circle(center, radius)`** — origin at the rightmost point.
- **`Polygon(points)`** — origin at the first vertex; the positive direction
  comes from the shape's *winding*, not the order you listed the vertices,
  so CW anchors always travel clockwise on screen.
- **`Polyline(points)`** — an open, stroke-only chain; CW means forward
  along it.
- **`Ellipse`**, **`Arc`**, **`Path`**, **`Compound`** — same contract;
  ellipses measure arc length with a dense chordal table, paths flatten
  adaptively for queries while exporting exactly.

## Anchors travel by percentage

An anchor fixes a start location plus a direction:

```python
anchor = circle.anchor(start=(160, 100), direction=wv.CW)
pt = anchor.point(25)    # 25% of the perimeter, clockwise from start
pt = anchor.point(150)   # >100% wraps around via modulo
pt = anchor.point(-20)   # negative travels backwards
```

The start point can be *any* (x, y) — it is projected to the nearest
location on the boundary. Since direction and winding are separated from
vertex order, `anchor.point(25)` means the same thing on a circle and on
any polygon: travel a quarter of the perimeter, clockwise, from where you
started.

Anchors also know where they are heading:

- {meth}`anchor.tangent(pct) <windvg.anchor.Anchor.tangent>` — the unit
  travel direction,
- {meth}`anchor.offset(pct, d) <windvg.anchor.Anchor.offset>` — displacement
  perpendicular to it (positive `d` is left of travel — outward for
  clockwise tracks).

## Anchors across shapes

This is where the model pays off: geometry tied to other geometry.

```python
a = square.anchor((70, 50), wv.CW)
b = circle.anchor((160, 135), wv.CCW)
chord = wv.connect((a, 25), (b, 60))   # square@25% to circle@60%
scene.stroke(chord, wv.BLACK, width=2.0)
polygon = wv.polygon_from_anchors([(a, 0), (b, 30), (a, 60), (b, 90)])
```

Any point of any shape can be defined relative to any other shape's
perimeter — {doc}`documents <documents>` build directly on this.
