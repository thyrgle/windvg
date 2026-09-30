#!/usr/bin/env python3
"""Reproduce the comparison tables in README.md.

Usage (from this directory):
    python3 count.py            # prints the LoC and character-count tables

Metrics, matching the README's methodology:
- LoC: non-empty lines, comments included, per source file.
- Characters: raw file size, plus a whitespace-normalized size (runs of
  whitespace collapsed to single spaces — close to what a minifier gets
  you). TikZ is also counted body-only: the LaTeX preamble lines
  (documentclass, library, begin/end document) are not about the drawing.
"""

import pathlib
import re

DRAWINGS = ["donut", "wheel", "connectors", "labels"]
LANGS = [("wvg", "wvg"), ("tikz", "tex"), ("svg", "svg")]

PREAMBLE = re.compile(
    r"^(\\documentclass|\\usetikzlibrary|\\begin\{document\}|\\end\{document\})"
)


def loc(path: pathlib.Path) -> int:
    return sum(1 for ln in path.read_text().splitlines() if ln.strip())


def chars(path: pathlib.Path, body_only: bool = False) -> tuple[int, int]:
    """(raw, normalized) character counts; body_only strips TikZ preamble."""
    text = path.read_text()
    if body_only:
        kept = [
            ln
            for ln in text.splitlines()
            if ln.strip() and not PREAMBLE.match(ln.strip())
        ]
        text = "\n".join(kept)
    return len(text), len(" ".join(text.split()))


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent
    loc_rows, char_rows = [], []
    loc_sums = {label: 0 for label, _ in LANGS}
    raw_sums = {label: 0 for label, _ in LANGS}
    norm_sums = {label: 0 for label, _ in LANGS}
    body_sums = {"tikz": 0}
    for name in DRAWINGS:
        lrow = {"drawing": name}
        crow = {"drawing": name}
        for label, ext in LANGS:
            path = root / name / f"{name}.{ext}"
            lrow[label] = loc(path)
            loc_sums[label] += lrow[label]
            raw, norm = chars(path, body_only=(label == "tikz"))
            crow[label] = raw
            crow[label + "_norm"] = norm
            raw_sums[label] += raw
            norm_sums[label] += norm
            if label == "tikz":
                body_sums["tikz"] += norm
        loc_rows.append(lrow)
        char_rows.append(crow)
    n = len(DRAWINGS)

    print("### Lines of code\n")
    print("| drawing | wvg | TikZ | SVG |")
    print("|---|---|---|---|")
    for r in loc_rows:
        print(
            f"| {r['drawing']} | {r['wvg']} | {r['tikz']} | {r['svg']} |"
        )
    print(
        f"| **average** | **{loc_sums['wvg']/n:.1f}** "
        f"| **{loc_sums['tikz']/n:.1f}** | **{loc_sums['svg']/n:.1f}** |"
    )

    print("\n### Characters\n")
    print("| drawing | wvg | TikZ | TikZ body | SVG | SVG normalized |")
    print("|---|---|---|---|---|---|")
    for r in char_rows:
        print(
            f"| {r['drawing']} | {r['wvg']} | {r['tikz']} "
            f"| {r['tikz_norm']} | {r['svg']} | {r['svg_norm']} |"
        )
    print(
        f"| **average** | **{raw_sums['wvg']//n}** "
        f"| **{raw_sums['tikz']//n}** | **{body_sums['tikz']//n}** "
        f"| **{raw_sums['svg']//n}** | **{norm_sums['svg']//n}** |"
    )
    return 0


if __name__ == "__main__":
    sys_exit = __import__("sys").exit
    sys_exit(main())
