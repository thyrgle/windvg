"""Ellipses, arcs, and tangent-aware anchors.

Run from the project root: uv run python examples/orbits.py
Outputs orbits.tvg and orbits.svg in examples/out/.
"""

from pathlib import Path

import windvg as wv

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

orbit = wv.Ellipse((110, 110), 70, 40, rotation_deg=30)
moon_arc = wv.Arc((110, 110), 95, 200, 280)

scene = wv.Scene(220, 220)
scene.fill(orbit, wv.rgb(0.95, 0.8, 0.2))
scene.stroke(moon_arc, wv.rgb(0.2, 0.5, 0.9), width=2.0)

# sample the elliptical orbit: dots on the track, ticks along the outward normals
anchor = orbit.anchor(orbit.point_at_param(0.0), wv.CW)
for i in range(8):
    pct = 12.5 * i
    dot = wv.Circle(anchor.point(pct), 2.5)
    tip = anchor.offset(pct, 9)
    scene.fill(dot, wv.rgb(0.85, 0.25, 0.2))
    scene.stroke(wv.connect(anchor.point(pct), tip), wv.rgb(0.85, 0.25, 0.2), width=1.2)

scene.write_tinyvg(out / "orbits.tvg")
scene.write_svg(out / "orbits.svg")
print(f"wrote {out / 'orbits.tvg'} and {out / 'orbits.svg'}")
