# Documents: the editable layer

{class}`Scene <windvg.scene.Scene>` is a flat list of draw ops.
{class}`Document <windvg.document.Document>` is the parametric, editable
form: named nodes in a chosen order, each an operation over a shape spec
with a paint. It is the layer editors round-trip through.

```python
import windvg as wv
from windvg import document as wvd
from windvg.document import Document

doc = Document(240, 240)
doc.grid("grid", origin=(0, 0), cols=6, rows=6, dx=40.0, dy=40.0)
doc.fill("body", wv.Circle((120, 120), 70), wv.rgb(0.3, 0.55, 0.95))
doc.fill(
    "box",
    wvd.PolySpec(True, [doc.grid_cell("grid", 2, 1), doc.grid_cell("grid", 4, 1),
                        doc.grid_cell("grid", 4, 3), doc.grid_cell("grid", 2, 3)]),
    wv.rgb(0.95, 0.8, 0.2),
)
doc.fill(
    "sat",
    wvd.CircleSpec(doc.anchor("body", pct=12.5), 6),
    wv.rgb(0.1, 0.1, 0.2),
)

print(doc.generate_code())   # readable Python — edit it and parse it back
scene = doc.resolve()        # render like any Scene
scene.write_svg("drawing.svg")
```

## Point references keep drawings parametric

A point inside a shape spec can be a literal `[x, y]` or a **reference**:

- {meth}`doc.anchor(node, pct, direction) <windvg.document.Document.anchor>`
  resolves against another node's track,
- {meth}`doc.grid_cell(grid, col, row) <windvg.document.Document.grid_cell>`
  resolves against a grid guide's lattice.

Nothing hardcodes the resolved pixel: move the track or retune the grid,
and everything referencing them follows. Use the `wvd.*Spec` forms
(`CircleSpec`, `PolySpec`, ...) wherever a point may be a reference;
concrete shapes like `wv.Circle` expect literal points.

## Grid guides

{meth}`doc.grid(name, origin=..., cols=..., rows=..., dx=..., dy=...)
<windvg.document.Document.grid>` adds an invisible **grid guide**: a lattice
that renders and exports nothing, used for snapping and cell references.
`grid_cell` points may carry a literal `offset` to preserve exact placement
while staying expressed in cell coordinates.

## Bounding boxes

{meth}`shape.bbox() <windvg.shapes.Shape.bbox>` returns the axis-aligned
bounding box as two corners — exact for circles, ellipses, and arcs;
flattened bounds for paths; the union for compounds. Resolved document ops
carry one too.

## Rendering and inspection

- {meth}`doc.resolve() <windvg.document.Document.resolve>` renders to a
  `Scene` — all exporters work as usual.
- {meth}`doc.resolve_to_json() <windvg.document.Document.resolve_to_json>`
  returns resolved draw ops with node identity and bboxes — what editor
  canvases draw and hit-test against.
- {meth}`doc.generate_code() <windvg.document.Document.generate_code>` /
  {meth}`Document.from_code(source)
  <windvg.document.Document.from_code>` round-trip the whole drawing
  through readable Python, preserving every reference: hand-edit the code,
  re-execute it, and the document is rebuilt.
