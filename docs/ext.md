# Extensions (`windvg.ext`)

The core stays small; richer tools live in `windvg.ext`.

## Transforms

{class}`Transform <windvg.ext.transform.Transform>` is an immutable affine
matrix. {func}`transformed(shape, t) <windvg.ext.transform.transformed>`
bakes one into a new shape; `translated` / `rotated` / `scaled` /
`mirrored_x` / `mirrored_y` are shorthands.

Transforms respect the shape model: circles under uniform transforms stay
circles; under non-uniform scaling they become exact ellipses; warped arcs
become exact elliptical-arc paths.

```python
from windvg.ext import Transform

gear = gear.transformed(Transform.rotate(15, about=center))
```

## Repetition

- {func}`sample(shape, n, offset) <windvg.ext.repeat.sample>` — n evenly
  spaced points along any track,
- {func}`along(track, motifs, n, align="tangent")
  <windvg.ext.repeat.along>` — place motifs around a track, optionally
  rotated to follow it: petals, gear teeth, rosettes,
- {func}`polar(center, motifs, n, radius) <windvg.ext.repeat.polar>` —
  motifs on a circle,
- {func}`grid(motifs, cols, rows, dx, dy) <windvg.ext.repeat.grid>` — a
  lattice of motifs.

```python
from windvg.ext import along

petal = wv.Ellipse((0, -20), 12, 20)   # built pointing up from the origin
for placed in along(circle, [petal], 8, align="tangent"):
    scene.fill(placed, wv.rgb(0.95, 0.8, 0.2))
```

## Rounded corners

{func}`rounded(polygon, radius) <windvg.ext.rounded.rounded>` replaces every
corner with an exact arc fillet — a fillable `Path`, not a polyline
approximation.

```python
from windvg.ext import rounded

badge = rounded(wv.regular_polygon(center, 80, 6), 12)
scene.fill(badge, wv.rgb(0.3, 0.55, 0.95))
```

## API

```{automodule} windvg.ext
:members:
:show-inheritance:
```
