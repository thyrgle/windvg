"""Gradient paints: linear and radial fills.

Run from the project root: uv run python examples/gradient_demo.py
"""

from pathlib import Path

import windvg as wv
from windvg.ext import rounded

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)

scene = wv.Scene(320, 160)

# sky-to-sunset linear gradient ball
scene.fill(
    wv.Circle((80, 80), 60),
    wv.LinearGradient((20, 20), (140, 140), wv.rgb(0.15, 0.4, 0.95), wv.rgb(1, 0.75, 0.25)),
)

# radial glow on a rounded square, with a translucent outline
scene.outline_fill(
    rounded(wv.regular_polygon((240, 80), 62, 4), 18),
    wv.RadialGradient((240, 80), (240, 18), wv.rgb(1, 0.9, 0.3), wv.rgb(0.75, 0.15, 0.35)),
    wv.rgba(0.1, 0.1, 0.15, 0.8),
    width=2.0,
)

scene.write_tinyvg(out / "gradient_demo.tvg")
scene.write_svg(out / "gradient_demo.svg")
print(f"wrote {out / 'gradient_demo.tvg'} and {out / 'gradient_demo.svg'}")
