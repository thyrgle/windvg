"""A star with rounded corners, filled with a gradient.

Run from the project root: uv run python examples/rounded_star.py
"""

from pathlib import Path

import windvg as wv
from windvg.ext import Transform, rounded, transformed

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

soft = rounded(wv.star((130, 90), 70, 30, points=5), 8)

scene = wv.Scene(260, 200)

# a smaller mirrored twin to the left
twin_op = (
    Transform.mirror_x(95)
    @ Transform.scale(0.7, about=(130, 90))
    @ Transform.rotate(36, about=(130, 90))
)
twin = transformed(soft, twin_op)
ocean = wv.LinearGradient((60, 20), (200, 160), wv.rgb(0.3, 0.6, 1), wv.rgb(0.2, 0.25, 0.5))
scene.fill(twin, ocean)

sunset = wv.LinearGradient(
    (60, 20), (200, 160), wv.rgb(1, 0.85, 0.3), wv.rgb(0.9, 0.3, 0.5)
)
scene.fill(soft, sunset)

scene.write_tinyvg(out / "rounded_star.tvg")
scene.write_svg(out / "rounded_star.svg")
print(f"wrote {out / 'rounded_star.tvg'} and {out / 'rounded_star.svg'}")
