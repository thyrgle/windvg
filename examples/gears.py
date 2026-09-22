"""A gear built with tangent-aligned repetition.

Run from the project root: uv run python examples/gears.py
"""

from pathlib import Path

import windvg as wv
from windvg.ext import along

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

body = wv.Circle((120, 120), 70)
teeth_track = wv.Circle((120, 120), 74)
tooth = wv.Polygon([(-16, -12), (16, -12), (11, 12), (-11, 12)])  # +x = along the rim

scene = wv.Scene(240, 240)
paint = wv.LinearGradient(
    (40, 40), (200, 200), wv.rgb(0.3, 0.55, 0.95), wv.rgb(0.15, 0.2, 0.45)
)
for placed in [body, *along(teeth_track, [tooth], 12, align="tangent")]:
    scene.fill(placed, paint)

# axle hole punched through body and hub
hub = wv.Circle((120, 120), 18)
scene.fill(wv.Compound([wv.Circle((120, 120), 40), hub]), wv.rgb(0.12, 0.14, 0.3))
scene.fill(hub, wv.rgb(0.95, 0.8, 0.2))

# bolt circle: 6 dots around the hub, phase-shifted 15 degrees
for placed in wv.ext.polar((120, 120), [wv.Circle((0, 0), 6)], 6, radius=68, start_deg=15):
    scene.fill(placed, wv.rgb(0.95, 0.8, 0.2))

scene.write_tinyvg(out / "gears.tvg")
scene.write_svg(out / "gears.svg")
print(f"wrote {out / 'gears.tvg'} and {out / 'gears.svg'}")
