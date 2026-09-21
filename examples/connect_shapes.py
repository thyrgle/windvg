"""Connecting anchors across two different shapes.

Run from the project root: uv run python examples/connect_shapes.py
Outputs connect.tvg and connect.svg in examples/out/.
"""

from pathlib import Path

import windvg as wv

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

square = wv.regular_polygon((70, 100), 50, 4)
circle = wv.Circle((160, 100), 35)

top_a = square.anchor((70, 50), wv.CW)
top_b = circle.anchor((160, 135), wv.CCW)

scene = wv.Scene(230, 200)
scene.fill(square, wv.rgb(0.25, 0.45, 0.8))
scene.outline_fill(circle, wv.rgb(0.95, 0.6, 0.2), wv.rgb(0.2, 0.2, 0.25), width=1.5)

# a chord from square@25% to circle@60%, plus mark both endpoints
for anchor, pct in ((top_a, 25), (top_b, 60)):
    scene.fill(wv.Circle(anchor.point(pct), 3), wv.rgb(0.85, 0.2, 0.25))

scene.stroke(wv.connect((top_a, 25), (top_b, 60)), wv.rgb(0.3, 0.3, 0.3), width=2.0)

scene.write_tinyvg(out / "connect.tvg")
scene.write_svg(out / "connect.svg")
print(f"wrote {out / 'connect.tvg'} and {out / 'connect.svg'}")
