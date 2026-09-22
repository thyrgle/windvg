"""Donuts, holes, and a small mandala: even-odd compound fills.

Run from the project root: uv run python examples/donut.py
"""

from pathlib import Path

import windvg as wv

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

scene = wv.Scene(240, 240)

# ring: outer square-ish circle with an inner hole
ring = wv.Compound([wv.Circle((120, 120), 90), wv.Circle((120, 120), 55)])
scene.fill(
    ring,
    wv.RadialGradient((120, 120), (120, 30), wv.rgb(1, 0.85, 0.3), wv.rgb(0.85, 0.25, 0.2)),
)

# beads evenly spaced on the ring's midline using anchors
midline = wv.Circle((120, 120), 72.5)
anchor = midline.anchor(midline.point_at_distance(0), wv.CW)
for i in range(16):
    scene.fill(wv.Circle(anchor.point(100 * i / 16), 6), wv.rgb(0.2, 0.3, 0.55))

# diamond window punched into the center plate
plate = wv.Compound([wv.Circle((120, 120), 52), wv.regular_polygon((120, 120), 24, 4)])
scene.fill(plate, wv.rgb(0.16, 0.2, 0.4))
scene.stroke(wv.regular_polygon((120, 120), 24, 4), wv.rgb(0.95, 0.8, 0.2), width=1.5)

scene.write_tinyvg(out / "donut.tvg")
scene.write_svg(out / "donut.svg")
print(f"wrote {out / 'donut.tvg'} and {out / 'donut.svg'}")
