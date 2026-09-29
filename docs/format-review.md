# The `.wvg` format in context: SVG and TikZ

Honest comparison — strengths, weaknesses, and how the format should
evolve.

`.wvg` is a small, declarative, safe document language with one genuinely
novel feature: **parametric perimeter anchors** (points placed by traveling
a percentage of a shape's boundary). This review measures it against the
two formats people actually reach for — **SVG** (the universal web vector
format) and **TikZ/PGF** (the LaTeX diagram language) — decides where it
stands, catalogs its weaknesses, and proposes how the format should grow.

The short version:

- `.wvg` **wins** on parametric anchors — nothing in SVG or TikZ expresses
  `fill moon = circle center=@p1 25%` without hand-computed coordinates or
  scripts.
- It **ties** on declarative repetition (`along` vs TikZ `\foreach` vs
  SVG's manual `<use>` stacking).
- It **loses** on the features that make the rivals general-purpose:
  text, transforms, groups, dashes, arrows, clip paths, expressions.
- The losses split into three tiers by *remedy*: things we can bake at
  compile time (fixable now), things that can only live above the TinyVG
  binary target (need a fidelity-tier decision), and things that would
  require TinyVG itself to change.

--------------------------------------------------------------------------------

## 1. Method

We compare on four criteria, in the context of the intended use: small,
hand-or-editor-authored vector drawings that round-trip through editors
and compile to TinyVG.

1. **Hand-authoring** — how much must a human hold in their head?
2. **Machine/editor authoring** — how well does a tool generate and
   re-generate the file?
3. **Editability** — when the drawing changes, what must be touched?
4. **Fidelity ceiling** — what can the format express at all?

Caveat: TikZ is a full programming language embedded in LaTeX, so it wins
any raw-expressiveness comparison by construction. The interesting
questions are *at what cost* (compilation, macro sprawl, security) and
*whether a declarative format can close most of the gap anyway*.

--------------------------------------------------------------------------------

## 2. Worked comparisons

### 2.1 Donut with a radial gradient — a tie

**`.wvg`** (from `examples/donut.wvg`, condensed):

```text
paint glaze = radial center=(90,90) edge=(140,110)
  center_color=#ff9aa2 edge_color=#c2404d

fill donut = compound shapes=[
  circle center=(100,100) radius=80,
  circle center=(100,100) radius=35
] color=glaze
```

**SVG** — gradients live in `<defs>`, the hole needs a path or a mask:

```xml
<defs>
  <radialGradient id="g" gradientUnits="userSpaceOnUse" cx="90" cy="90" r="53.85">
    <stop offset="0" stop-color="#ff9aa2"/>
    <stop offset="1" stop-color="#c2404d"/>
  </radialGradient>
</defs>
<path fill="url(#g)" fill-rule="evenodd" d="M180,100 A80,80 0 1,0 20,100
  A80,80 0 1,0 180,100 M135,100 A35,35 0 1,0 65,100 A35,35 0 1,0 135,100"/>
```

**TikZ** — the hole is beautifully concise; the *exact* two-point radial
gradient is not:

```latex
\shade[inner color=red!30, outer color=red!70] (0,0) circle (2);
\fill[white] (0,0) circle (0.875);   % punch the hole back
```

Verdict: `.wvg` holds its own. The gradient is inline where it is used,
the hole is data (`compound`), and nothing needs indirection (`defs`) or
paint-over tricks. Counting lines undersells SVG's real cost: the reader
must know the defs/`url(#)` protocol and hand-build arc path data.

### 2.2 Fourteen teeth around a circle — a win on declarativeness

**`.wvg`** (from `examples/gears.wvg`):

```text
fill teeth = along
  track=circle center=(110,110) radius=62
  motifs=[polygon points=[(-6,-2), (6,-2), (9,-15), (-9,-15)]]
  n=14 offset_pct=1% align=tangent direction=cw
  color=#31465e
```

**SVG** — there is no repetition primitive. The author writes fourteen
`<use>` elements with hand-composed transforms (or scripts the file):

```xml
<g fill="#31465e">
  <use href="#tooth" transform="rotate(  0 110 110) translate(0,-62)"/>
  <use href="#tooth" transform="rotate(25.7 110 110) translate(0,-62)"/>
  <!-- ...twelve more... -->
</g>
```

**TikZ** — compact, if you read LaTeX loops:

```latex
\foreach \i in {0,...,13}
  \fill[teal, shift={(110,110)}, rotate=\i*360/14]
    (-6,-2) -- (6,-2) -- (9,-15) -- (-9,-15) -- cycle;
```

Verdict: TikZ matches the brevity but pays in programming concepts — the
author writes a loop over angles and does the tangent math themselves.
SVG has nothing at all. `.wvg` states the *intent* (a motif, a track, a
count) and the compiler owns the trigonometry. One real loss: SVG's
`<use>` is a *reference* — edit the definition and every instance updates.
`along` **bakes** copies; edit the motif and only future documents change.
That gap is revisit-with-use semantics, catalogued as W7 below.

### 2.3 The parametric tie — an outright win

**`.wvg`** (from `examples/orbit.wvg`):

```text
fill p1 = circle center=@orbit2 0% radius=7 color=#7fd1c0
fill moon = circle center=@p1 25% radius=2.5 color=#e0e6f0
stroke comet = line p1=@orbit1 37.5% p2=@orbit2 40% color=#ffd25a width=1.5
```

A planet pinned to an orbit, a moon pinned to the *planet*, and a tie
between two perimeters. Move an orbit; everything follows.

**SVG** — there is no mechanism. The author hand-computes and freezes:

```xml
<circle cx="160"   cy="110" r="7"   fill="#7fd1c0"/>
<circle cx="160"   cy="117" r="2.5" fill="#e0e6f0"/>
<line   x1="53.4" y1="166.6" x2="69.5" y2="139.4"
        stroke="#ffd25a" stroke-width="1.5"/>
```

Every number is a coffin for a relationship. Move the orbit radius and
all four coordinates are wrong.

**TikZ** — the closest competitor, but the author supplies the math:
percent-of-perimeter becomes angles on circles, `pos=` works only on
drawn segments, and the moon chained to the planet needs nested `calc`
expressions that re-derive on every edit:

```latex
\fill[teal]  ($(O)+(0:5)$)        circle (0.35);
\fill[white] ($(O)+(0:5)+(0,-.35)$) circle (0.125);
\draw[yellow] ($(O1)+(135:8)$) -- ($(O2)+(144:5)$);
```

Verdict: the anchor model is the format's identity and it is real. No
rival expresses *travel 25% of a perimeter from a start point, then chain
another shape to the result* declaratively.

### 2.4 A labeled, annotated diagram — the honest loss

The case that motivates the rest of this review: a box, a label, and a
dashed feedback arrow.

**TikZ** — the canonical case, nearly prose:

```latex
\node[draw] (in) {input};
\draw[->, dashed] (in.east) -- ++(1.5,0)
      node[near end, above] {feedback} |- (in.south);
```

**SVG** — fully expressive:

```xml
<text x="60" y="45" text-anchor="middle" font-size="12">input</text>
<path d="M100,40 H160 V80 H60" fill="none" stroke="#000"
      stroke-dasharray="4 3" marker-end="url(#arrow)"/>
```

**`.wvg`** — the label **cannot be expressed at all** (no text), the dash
**cannot be expressed** (no stroke properties), and the arrowhead must be
hand-built as a polygon at hand-computed coordinates. The format loses
this case by forfeit.

This is not a corner case: labels and annotations are most of what people
draw. Any plan to position `.wvg` as a vector *graphics* format has to
deal with this row directly — which is what sections 5 and 6 do.

--------------------------------------------------------------------------------

## 3. Feature matrix

| Feature | `.wvg` v1 | SVG 1.1 | TikZ/PGF |
| --- | --- | --- | --- |
| Text | — | ✓ (rich) | ✓ (excellent) |
| Per-node transforms | — | ✓ | ✓ (scopes) |
| Grouping | — (`compound` is a fill op, not a group) | ✓ (`g`) | ✓ |
| Reuse / symbols | — | ✓ (`defs`+`use`) | ✓ (macros, `pics`) |
| Declarative repetition | ✓ (`along`/`polar`/`grid`, baked) | — (manual `use` stack) | ✓ (`\foreach`, computed) |
| Expressions | — | — | ✓ (full math) |
| Relative / polar coordinates | — | — | ✓ (`++(1,0)`, `(30:2)`) |
| **Perimeter anchors (pct travel + chaining)** | **✓ (unique)** | — | △ (`pos=` on segments; angle math on circles) |
| Dash patterns | — | ✓ | ✓ |
| Arrowheads / markers | — | ✓ (markers) | ✓ (best in class) |
| Clip paths | — | ✓ | ✓ |
| Masks / opacity groups | — (alpha per color only) | ✓ | △ |
| Filters (blur, shadow) | — | ✓ | — |
| Fill rules | △ (even-odd only) | ✓ (both) | ✓ (both) |
| Gradients | ✓ (two-point linear/radial, inline) | ✓ (richer) | △ (pgf shadings) |
| Units / physical size | — (pixels) | ✓ | ✓ |
| Metadata (title, author) | — | ✓ | △ (comments) |
| Safety (no code execution) | ✓ | ✓ (script optional) | ✗ (LaTeX macros) |
| Compactness / diff-friendliness | ✓ | △ | △ |
| Tooling ecosystem | ✗ (this project) | ✓✓ | ✓ (LaTeX) |

--------------------------------------------------------------------------------

## 4. Weakness catalogue

Each weakness is tagged with a **remedy tier**:

- **Tier A** — can be added to the language and *baked at compile time*,
  so `.tvg` fidelity is unaffected (the same way `along` and `rounded`
  already compile to plain shapes).
- **Tier B** — can live in `.wvg` but **cannot** encode in TinyVG 1.0;
  SVG export would keep them, `.tvg` export would drop them with a
  warning. Requires a documented *fidelity-tier* policy.
- **Tier C** — impossible without changes to TinyVG itself.

### Blocking

**W1 — No text.** *Tier B (now), Tier A-hard (later).* Labels are most of
diagram-drawing. Short term, text can only exist above the binary target
(§5.4). Long term, text-as-outlines at compile time keeps `.tvg` pure but
needs a font pipeline in every compiler. This is the single largest gap.

**W2 — No transforms, no groups.** *Tier A.* Everything is absolute
coordinates in one flat namespace; `compound` is an even-odd fill op, not
a group. Moving a conceptual "subgroup" means editing every number by
hand. Fully fixable in-language: a `transform=` property and a `group`
construct can bake at resolve time — the engine already bakes transforms
for generators, and all three implementations contain the same
`transformed()` machinery.

### Major

**W3 — No helper geometry or expressions.** *Tier A (narrow), deliberate
(general).* Midpoints, "shape centered between two anchors", simple
offsets: all require hand-computed literals today. Narrow, declarative
remedies (a `between` point form, a `mid` helper) fix most of the pain
without becoming a programming language; see §6 "what we will not do".

**W4 — No dash patterns.** *Tier B.* Dashes are strokes — TinyVG has no
dash encoding. Also the classic look of "sketch" and "feedback" styling.

**W5 — No arrowheads or markers.** *Tier A — FIXED in v3.* `stroke`
nodes accept `marker = start|end|both triangle|bar size [paint]`, baked
at resolve into ordinary polygon ops via the track protocol.

**W6 — No clip paths or masks.** *Tier B (mask), Tier A-hard (clip).*
Masks/compositing cannot encode in TinyVG. Clipping is geometrically
bakeable (path intersection) but that is a serious computational feature;
defer.

**W7 — No reuse semantics.** *Tier A — FIXED in v3.* `def name = shape`
plus `use name` gives symbols a canonical spelling with source-level
propagation (defs survive in the IR; editors re-expand). Live-reference
propagation remains a documented caveat.

**W8 — Ecosystem is zero.** *Not a language property — a campaign.* An
SVG→`.wvg` importer (lossy, documented) and a web playground would do
more for adoption than any syntax feature.

### Minor

**W9 — Even-odd only.** *Tier A.* A `rule=nonzero` flag per fill; also
flag a follow-up: verify TinyVG renderers' fill-rule behavior for our
even-odd compound holes with the same rigor we verified ellipse rotation.

**W10 — No pie/wedge shape.** *Tier A.* `arc` is stroke-only; `pie`/
`chord` desugar to closed paths exactly the way `rounded` already does.

**W11 — No units, no metadata.** *Tier A.* Pixels-only is fine for the
current targets; a `meta` statement (title/author/license) is trivial.

### Spec traps (documentation/clarification, not features)

- Anchor travel **wraps** on closed tracks but **clamps** on open ones —
  correct but surprising; deserves callouts in both docs.
- Segment references address **vertex order** and ignore winding — the
  opposite of anchor references. Justified, but a cognitive trap.
- `polar` defaults `align=none` while `along` defaults `align=tangent` —
  historically motivated, endlessly confusing.
- Paints must be declared before use; nodes may be referenced before
  declaration. Pragmatic, asymmetric.

--------------------------------------------------------------------------------

## 5. How the format could grow

Three architectures, argued honestly.

### 5.1 Curated v2 (recommended)

Ship a **v2 draft** that is strictly additive — every v1 file is a valid
v2 file — containing exactly the Tier A set:

| Addition | Form | Desugars to |
| --- | --- | --- |
| `transform=` on any node | translate/rotate/scale/mirror properties | bake via the existing transform machinery |
| `group` construct | named child nodes sharing a transform | bake into each child |
| `rect` shape | center + size (or corners) | polygon |
| `pie` / `chord` shapes | center/radius/angles | closed paths (like `rounded`) |
| `between` point form | `between p q 30%` (lerp of two resolved points) | literal point at resolve |
| `rule=nonzero` flag | per fill/outline_fill node | documented flag, no baking needed |
| `marker` on strokes | motif + placement (`end`/`both`) | `along`-style baked placement |

Why now: **there are zero external `.wvg` files**, so the cost of a v2 is
one spec revision and a parser update in two implementations — the
window for painless format evolution closes the day the first third-party
file exists. Why curated: every construct maps onto machinery that
already exists in Python, Rust, and Kotlin; nothing needs new theory.

### 5.2 An extension registry (defer)

The alternative is a mechanism: `extension dash` declarations in the file
header, a registry of known extensions, strict rejection by unaware
parsers. This buys experimentation without core churn, at the cost of
capability negotiation ("which viewer supports which extensions") —
terrain SVG's ecosystem knows and suffers. Recommendation: **defer**
until third parties actually ask to experiment; do not build the
bureaucracy before there is anything to register.

### 5.3 Text and the fidelity boundary

Text (W1) is the forcing function for a policy the format has avoided so
far: **features that cannot reach `.tvg`**. Options:

1. **Editor-owned text** — a `text` construct lives in `.wvg` (Tier B);
   `.tvg` export drops it with a warning; SVG export keeps it. Cheapest,
   unblocks diagrams, but creates two fidelity classes of documents.
2. **Text-as-outlines at compile** — keeps `.tvg` pure; requires font
   selection, shaping, and outline extraction in every compiler. A
   project, not a feature.
3. **Author-time conversion** — the editor converts text to paths on
   insert. Zero pipeline cost; text stops being editable as text.

Recommendation: decide *after* the Tier A v2 ships. Option 1 with a loud
fidelity marker is the pragmatic next step if diagrams matter to the
product; option 2 is the principled endgame if `.tvg` purity matters
more.

### 5.4 The TinyVG ceiling

Dash, clip, masks, and filters are Tier B/C **because TinyVG 1.0 has no
encoding for them** — no amount of `.wvg` design changes that. If those
features become product-critical, the honest paths are an out-of-band
sidecar document, a TinyVG 2.0 proposal, or accepting SVG as the
rich-export format and TinyVG as the compact one. Treat this as a
product decision, not a language decision.

--------------------------------------------------------------------------------

## 6. Roadmap

Ordered by value ÷ effort; nothing here breaks v1 files.

1. **v2 additive draft** — SHIPPED: transforms, groups, `rect`/`pie`/
   `chord`, `between`, and the Tier A remainder (markers, defs/use) in
   v3, spec + Python + Rust + Kotlin, with golden vectors each.
2. **Trap documentation** — callouts for wrap/clamp, segment-vs-winding,
   and the align defaults in `language.md` (spec-side only).
3. **SVG→`.wvg` importer** (lossy, documented mapping) — addresses W8 and
   doubles as a test generator.
4. **Fidelity-tier policy** — a short spec section defining what happens
   when Tier B constructs are present at `.tvg` export (required before
   any Tier B feature ships).
5. **Text decision** (§5.3) — the biggest open product question.
6. **`use`/symbols and dash** — after 4.

### What we will *not* do

- **No expressions, loops, or scripting.** TikZ can out-compute `.wvg`
  forever; competing there surrenders the declarative identity that makes
  editors, sandboxes, and the three-implementation port possible.
- **No CSS, no external references, no namespaces.** The format's
  readability *is* the feature.
- **No breaking v1 syntax.** Growth is additive; the anchor model and the
  track protocol are frozen by conformance tests in three languages.

--------------------------------------------------------------------------------

## 7. Summary

`.wvg` is not a TikZ replacement or an SVG replacement — it is a small,
safe, editor-round-trippable drawing language with a genuinely novel
parametric model, currently missing the everyday features (text, groups,
transforms, dashes) that its rivals treat as table stakes. Most of those
features are reachable **without betraying the design**: the Tier A set
bakes into the existing compile pipeline and slots into a strictly
additive v2. The right time to commit to that v2 is now, while the
format's installed base is still zero.
