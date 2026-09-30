# wvg vs TikZ vs SVG — same drawings, side by side

Four drawings, each written three times: once in **wvg**, once in
**TikZ/PGF**, once in **SVG**. The drawings are identical (same shapes,
colors, strokes, labels) up to the visual conventions each language
allows. Every `*.wvg` file resolves with the reference implementations;
every `*.tex` compiles with `pdflatex`; every `*.svg` is well-formed
hand-written markup (not generated from the other two).

| folder | wvg | TikZ | SVG |
| --- | --- | --- | --- |
| [`donut/`](donut/) — gradient ring + 9 sprinkles | [`donut.wvg`](donut/donut.wvg) | [`donut.tex`](donut/donut.tex) · [pdf](donut/donut.pdf) | [`donut.svg`](donut/donut.svg) |
| [`wheel/`](wheel/) — hub, rim, 12 tangent ticks | [`wheel.wvg`](wheel/wheel.wvg) | [`wheel.tex`](wheel/wheel.tex) · [pdf](wheel/wheel.pdf) | [`wheel.svg`](wheel/wheel.svg) |
| [`connectors/`](connectors/) — rail × hoop, crossing markers, 2 arc connectors | [`connectors.wvg`](connectors/connectors.wvg) | [`connectors.tex`](connectors/connectors.tex) · [pdf](connectors/connectors.pdf) | [`connectors.svg`](connectors/connectors.svg) |
| [`labels/`](labels/) — two shapes, a link, three labels | [`labels.wvg`](labels/labels.wvg) | [`labels.tex`](labels/labels.tex) · [pdf](labels/labels.pdf) | [`labels.svg`](labels/labels.svg) |

Each folder also contains `*.rendered.svg` — the wvg file exported
through the reference implementation, as proof the source resolves.

## Lines of code

Counted as **non-empty lines** (blank lines excluded, comments included
— comments are part of what an author writes). The wvg `wheel` example
includes its two blank lines around the `repeat` body, so nothing is
flattered.

| drawing | wvg | TikZ | SVG |
|---|---|---|---|
| donut | 4 | 10 | 21 |
| wheel | 7 | 9 | 18 |
| connectors | 7 | 17 | 10 |
| labels | 7 | 11 | 8 |
| **average** | **6.2** | **11.8** | **14.3** |

### Reading the numbers honestly

- **TikZ carries 3 lines of LaTeX preamble** (`documentclass`,
  `\begin{document}`, `\end{document}`) that aren't about the drawing.
  Counting drawing-only lines, TikZ averages **8.8** — still above wvg,
  but the loop-heavy `wheel` is a genuine tie, and TikZ's
  `\foreach … ([shift={(100,100)}] \a:56)` is excellent.
- **SVG's `connectors` score is borrowed.** Ten lines — because the two
  crossing coordinates (`67.868, 95.799` / `152.132, 64.201`) and the
  arc radii (`98.995`, `140`) were **precomputed by hand** (in this repo,
  with the reference implementation). SVG has no intersection semantics
  and no connector form; the lines are few but the math happened
  somewhere else. LoC rewards moving work off the page; wvg and TikZ
  keep it on the page where it stays correct when the geometry changes.
- **`donut` is wvg's best case**: the compound ring with even-odd fill
  is one line, and the 9 sprinkles are *parameters* (`along … n=9`),
  not nine elements. SVG needs all nine (plus the gradient def).

### What the numbers say

**wvg wins the average** (6.2 vs 11.8 vs 14.3) and, more importantly,
wins the *right* way: the savings come from semantics — tracks,
generators, parametric points, intersections — not from terser syntax.
The two places wvg doesn't beat TikZ on lines (preamble aside) are
drawings where TikZ's `\foreach` and polar coordinates do real work;
that is the gap v6's `repeat` and the v7 geometry closed in wvg's own
vocabulary. For pure static vector markup, SVG remains the universal
interchange format — but as an authoring language it repeats geometry a
calculator already solved.

## Reproducing

- wvg: resolve/export with the reference implementation, e.g.
  `windvg svg donut/donut.wvg` (writes the rendered SVG).
- TikZ: `cd donut && pdflatex donut.tex`.
- SVG: open in any browser.
