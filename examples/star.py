"""A pentagram drawn with the anchor system itself.

Run from the project root: uv run python examples/star.py
Outputs star.tvg and star.svg in examples/out/.
"""

from pathlib import Path

import windvg as wv

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

circle = wv.Circle((100, 100), 70)

# the pentagram: place 5 anchors around the circle, connect every 2nd
pentagram = wv.star_polygon(circle, 5, 2)

scene = wv.Scene(200, 200)
scene.fill(pentagram, wv.rgb(0.95, 0.8, 0.2))
# the circle is guide geometry: visible=False keeps it out of the exports,
# so the output contains just the star (flip to True to see it)
scene.stroke(circle, wv.rgb(0.2, 0.2, 0.25), width=1.5, visible=False)

# mark where the anchors landed using the anchor API directly
anchor = circle.anchor(circle.point_at_distance(0.0), wv.CW)
for i in range(5):
    pt = anchor.point(100.0 * i / 5)
    scene.fill(wv.Circle(pt, 3), wv.rgb(0.85, 0.25, 0.2))

scene.write_tinyvg(out / "star.tvg")
scene.write_svg(out / "star.svg")
print(scene.to_tvgt())
print(f"wrote {out / 'star.tvg'} and {out / 'star.svg'}")
