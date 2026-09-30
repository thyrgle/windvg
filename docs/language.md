# The `.wvg` language specification

**Version 5**

`.wvg` is the canonical, human-readable document format for windvg. It is a
purely declarative language: a `.wvg` file names shapes, ties points to other
shapes' perimeters with anchors, arranges repetitions, and styles the results
with fills and strokes. It contains no arithmetic, no variables, and no code
execution — opening a `.wvg` file can never run a program.

Version 5 is strictly additive over versions 1–4: every older file is a
valid v5 file with identical meaning. Loaders accept 1–5 and reject
anything newer. Version 2 added node `transform=` (baked at resolve),
`group` statements, the `rect`, `pie`, and `chord` shapes, the `between`
point form, and the `matrix` transform expression. Version 3 added
**point offsets**, the **polar point form**, **symbol defs and use**, and
**stroke markers**. Version 4 added the **text node** (§7.19) and the
**fidelity-tier policy** (§11): text survives in `.wvg` and SVG export;
TinyVG export of text requires a font-baking host or fails by default.
Version 5 adds **tangent offsets** (§7.20) — local-frame vector offsets
on track-based point references. See §12.

The language is the textual surface of the existing windvg document model.
Every construct compiles 1:1 to a serializable spec
(`windvg.document.Document.to_dict`), which resolves to a `Scene` and encodes
to TinyVG:

```text
source.wvg ──parse──▶ Document IR ──resolve──▶ Scene ops ──encode──▶ .tvg
              (JSON)                (draw ops)
```

Editors (windstudio) load and emit the *Document IR* so guides, anchors, and
references survive round trips. TinyVG is static and cannot represent them;
it is an export target, not the compile target.

- File extension: `.wvg` (unclaimed; no known conflicting format)
- Media type (suggested): `application/x-windvg`
- Encoding: UTF-8, no byte-order mark
- Reference semantics: the Python implementation in `windvg.document`,
  `windvg.shapes`, `windvg.anchor`, `windvg.path`, `windvg.ext`, and
  `windvg.tinyvg`

--------------------------------------------------------------------------------

## 1. Design goals

1. **Declarative, not programmable.** No expressions or computation. Shapes
   that need math at build time (regular polygons, stars) are builtin
   *desugarings* with exactly specified formulas (§7.7).
2. **IR-faithful.** Keywords match the document JSON keys. Parsing is a
   mechanical translation; there is exactly one mapping per construct (§6).
3. **Editor-round-trippable.** `format(parse(file)) == file` for canonically
   formatted files, and parse ∘ emit ∘ parse is the identity on the IR.
4. **Implementable.** The grammar is small and LL-friendly, properties have a
   fixed order, and every numeric behavior that reaches the output is pinned
   in §7–§8 so independent implementations produce identical bytes.

Out of scope for v1 (deliberate exclusions, see §10): affine transforms,
arithmetic on numbers, star polygons via skip traversal, path tolerance
configuration.

--------------------------------------------------------------------------------

## 2. Example

```text
// gear.wvg — a compound body plus teeth repeated around a track
wvg 1
scene 200 200

paint steel = linear start=(40,40) end=(40,160) start_color=#8fa7c4 end_color=#31465e

guide body = circle center=(100,100) radius=60

fill gear = compound shapes=[
  circle center=(100,100) radius=55,
  circle center=(100,100) radius=18
] color=steel

fill teeth = along track=circle center=(100,100) radius=60
  motifs=[line p1=(-7,-6) p2=(7,-6)] n=12 offset_pct=0% align=tangent direction=cw
  color=#31465e

// a parametric tie bar: 25% cw around the body, 60% ccw around the body
// starting from the projected point (100, 140)
stroke tie = line p1=@body 25% p2=@body 60% ccw from (100,140) color=#222222 width=2
```

`@body 25%` means: project onto `body`'s boundary, travel 25% of its perimeter
clockwise on screen. References stay parametric — move the circle, the tie
bar follows. (Anchoring to `gear` itself would be a compile error: a compound
has no single track, §7.11.)

--------------------------------------------------------------------------------

## 3. Lexical structure

### 3.1 Source encoding

UTF-8, no BOM. Keywords and identifiers are ASCII.

### 3.2 Comments

`//` starts a comment that runs to the end of the line. There are no block
comments. (`#` is not a comment character; it begins hex colors.)

### 3.3 Whitespace

Spaces, tabs, and newlines separate tokens and are otherwise insignificant.
Statements are self-delimiting; a file may use any line layout.

### 3.4 Identifiers

```text
IDENT ::= [A-Za-z_][A-Za-z0-9_]*
```

Identifiers name nodes and paints. They must not be reserved words
(Appendix A). Names are case-sensitive.

### 3.5 Numbers

```text
NUMBER  ::= SIGN? ( DIGIT+ ("." DIGIT*)? | "." DIGIT+ ) EXP?
SIGN    ::= "+" | "-"
EXP     ::= ("e" | "E") SIGN? DIGIT+
DIGIT   ::= [0-9]
```

All numbers are IEEE-754 binary64 values. `NaN`, infinities, and out-of-range
exponents are compile errors. An **integer** is a NUMBER whose value is
mathematically integral; a non-integral value where an integer is required is
a compile error. Implementations must parse numbers by the usual
correctly-rounded decimal-to-binary64 conversion.

### 3.6 Hex colors

```text
HEX ::= "#" [0-9a-fA-F]{3} | "#" [0-9a-fA-F]{6} | "#" [0-9a-fA-F]{8}
```

`#rgb` expands to `#rrggbb` by duplicating each digit. Channels convert to the
0..1 range by dividing the byte value by 255.0 (e.g. `#4073cc` gives r =
64/255.0). An 8-digit form supplies alpha as the fourth byte.

--------------------------------------------------------------------------------

## 4. Grammar

EBNF: `x y` sequence, `x | y` alternation, `[ x ]` optional (0–1),
`{ x }` repetition (0+), `"..."` literal token.

Properties of every construct appear in **exactly the order listed** below;
optional properties may be omitted but not reordered. This keeps the grammar
deterministic and canonical formatting trivial.

```ebnf
file         = "wvg" , INTEGER , scene , { top } ;
scene        = "scene" , NUMBER , NUMBER ;

top          = paint_decl | def_stmt | fill | stroke | outline_fill | guide | group | text_stmt ;
def_stmt     = "def" , IDENT , "=" , shape ;
text_stmt    = "text" , IDENT , "=" , "at" , "=" , point , "content" , "=" , STRING ,
               "size" , "=" , NUMBER , [ "font" , "=" , IDENT ] ,
               [ "anchor" , "=" , align_h ] , [ "color" , "=" , paint ] , [ "hidden" ] ;
align_h      = "start" | "middle" | "end" ;

paint_decl   = "paint" , IDENT , "=" , paint ;

fill         = "fill" , IDENT , "=" , shape ,
               [ "transform" , "=" , transform_expr ] ,
               "color" , "=" , paint , [ "hidden" ] ;
stroke       = "stroke" , IDENT , "=" , shape ,
               [ "transform" , "=" , transform_expr ] ,
               "color" , "=" , paint , [ "width" , "=" , NUMBER ] ,
               [ "marker" , "=" , placement , kind , NUMBER , [ paint ] ] ,
               [ "hidden" ] ;
placement    = "start" | "end" | "both" ;
kind         = "triangle" | "bar" ;
outline_fill = "outline_fill" , IDENT , "=" , shape ,
               [ "transform" , "=" , transform_expr ] ,
               "color" , "=" , paint , "outline" , "=" , paint ,
               [ "width" , "=" , NUMBER ] , [ "hidden" ] ;
guide        = "guide" , IDENT , "=" , guide_shape ;
group        = "group" , [ transform_expr ] , "{" , { top } , "}" ;
guide_shape  = "grid" , grid_props | shape ;
grid_props   = [ "origin" , "=" , point ] , [ "cols" , "=" , INTEGER ] ,
               [ "rows" , "=" , INTEGER ] , [ "dx" , "=" , NUMBER ] ,
               [ "dy" , "=" , NUMBER ] ;

paint        = color
             | "linear" , "start" , "=" , literal , "end" , "=" , literal ,
               "start_color" , "=" , color , "end_color" , "=" , color
             | "radial" , "center" , "=" , literal , "edge" , "=" , literal ,
               "center_color" , "=" , color , "edge_color" , "=" , color
             | IDENT ;   (* a paint declared by an earlier paint_decl *)

color        = HEX
             | named_color
             | "rgb" , "(" , NUMBER , "," , NUMBER , "," , NUMBER , ")"
             | "rgba" , "(" , NUMBER , "," , NUMBER , "," , NUMBER , "," , NUMBER , ")" ;

named_color  = "black" | "white" | "red" | "green" | "blue" | "yellow"
             | "cyan" | "magenta" | "gray" ;

shape        = "circle" , "center" , "=" , point , "radius" , "=" , NUMBER
             | "ellipse" , "center" , "=" , point , "rx" , "=" , NUMBER ,
               "ry" , "=" , NUMBER , [ "rotation_deg" , "=" , NUMBER ]
             | "arc" , "center" , "=" , point , "radius" , "=" , NUMBER ,
               "start_deg" , "=" , NUMBER , "sweep_deg" , "=" , NUMBER
             | "rect" , "center" , "=" , point , "size" , "=" , literal
             | "pie" , "center" , "=" , point , "radius" , "=" , NUMBER ,
               "start_deg" , "=" , NUMBER , "sweep_deg" , "=" , NUMBER
             | "chord" , "center" , "=" , point , "radius" , "=" , NUMBER ,
               "start_deg" , "=" , NUMBER , "sweep_deg" , "=" , NUMBER
             | "polygon" , "points" , "=" , point_list
             | "polyline" , "points" , "=" , point_list
             | "line" , "p1" , "=" , point , "p2" , "=" , point
             | "path" , "subpaths" , "=" , subpath_list
             | "compound" , "shapes" , "=" , shape_list
             | "along" , "track" , "=" , shape , "motifs" , "=" , shape_list ,
               "n" , "=" , INTEGER ,
               [ "offset_pct" , "=" , NUMBER , "%" ] ,
               [ "align" , "=" , align_mode ] ,
               [ "direction" , "=" , orientation ]
             | "polar" , "center" , "=" , point , "motifs" , "=" , shape_list ,
               "n" , "=" , INTEGER , "radius" , "=" , NUMBER ,
               [ "start_deg" , "=" , NUMBER ] , [ "align" , "=" , align_mode ]
             | "grid" , "motifs" , "=" , shape_list , "cols" , "=" , INTEGER ,
               "rows" , "=" , INTEGER , "dx" , "=" , NUMBER , "dy" , "=" , NUMBER ,
               [ "origin" , "=" , point ]
             | "regular_polygon" , "center" , "=" , point , "radius" , "=" , NUMBER ,
               "sides" , "=" , INTEGER , [ "start_angle_deg" , "=" , NUMBER ]
             | "star" , "center" , "=" , point , "outer_radius" , "=" , NUMBER ,
               "inner_radius" , "=" , NUMBER , [ "points" , "=" , INTEGER ] ,
               [ "start_angle_deg" , "=" , NUMBER ]
             | "rounded" , "shape" , "=" , shape , "radius" , "=" , NUMBER
             | "use" , IDENT ;

align_mode   = "tangent" | "none" ;
orientation  = "cw" | "ccw" ;

point_list   = "[" , point , { "," , point } , "]" ;
shape_list   = "[" , shape , { "," , shape } , "]" ;

subpath_list = "[" , subpath , { "," , subpath } , "]" ;
subpath      = "{" , "start" , "=" , point , instruction , { "," , instruction } , "}" ;

instruction  = "line" , "to" , "=" , point
             | "quad" , "ctrl" , "=" , point , "to" , "=" , point
             | "cubic" , "c1" , "=" , point , "c2" , "=" , point , "to" , "=" , point
             | "arc_circle" , "radius" , "=" , NUMBER , [ "large" ] ,
               [ orientation ] , "to" , "=" , point
             | "arc_ellipse" , "rx" , "=" , NUMBER , "ry" , "=" , NUMBER ,
               "rotation_deg" , "=" , NUMBER , [ "large" ] , [ orientation ] ,
               "to" , "=" , point
             | "close" ;

point        = literal | anchor_ref | segment_ref | grid_ref | between_ref | polar_ref ;
literal      = "(" , NUMBER , "," , NUMBER , ")" ;
anchor_ref   = "@" , IDENT , [ orientation ] , [ percent ] , [ "from" , literal ] ,
               [ tangent_off ] , [ "+" , literal ] ;
percent      = NUMBER , "%" ;
segment_ref  = "@" , IDENT , "seg" , INTEGER , [ percent ] , [ tangent_off ] ,
               [ "+" , literal ] ;
grid_ref     = "@" , IDENT , "[" , INTEGER , "," , INTEGER , "]" , [ "+" , literal ] ;
between_ref  = "between" , point , point , percent , [ "+" , literal ] ;
polar_ref    = "polar" , "center" , "=" , point , "radius" , "=" , NUMBER ,
               "deg" , "=" , NUMBER ;
tangent_off  = "tangent" , NUMBER , [ "deg" , NUMBER ] ;

STRING        = '"' , { STRING_CHAR }, '"' ;   (* '"' escaped as \" , backslash as \\ *)
transform_expr = "translate" , NUMBER , NUMBER
               | "rotate" , NUMBER , [ "about" , literal ]
               | "scale" , NUMBER , [ NUMBER ] , [ "about" , literal ]
               | "mirror_x" , NUMBER
               | "mirror_y" , NUMBER
               | "matrix" , NUMBER , NUMBER , NUMBER , NUMBER , NUMBER , NUMBER ;
```

Notes:

- `"wvg"` and the version integer must be the first two tokens of the file.
  `scene` must follow immediately and appear exactly once.
- `anchor_ref`: all three parts (`orientation`, `percent`, `from`) are
  optional and default to `cw`, `0%`, and "the shape's origin". Bare `@name`
  is valid.
- `segment_ref`: `@hull seg 2 50%` selects one edge of a polygon or polyline
  and a position along it (§7.3); the percent defaults to `0%`.
- `between_ref`: `between p q t%` is the linear blend of two resolved
  points (§7.7); `t` may leave `[0, 100]` and extrapolates.
- `transform_expr`: see §7.8. `scale sx` means uniform scale; the `about`
  point defaults to the origin. `mirror_x a` reflects across the vertical
  line `x = a`; `mirror_y a` across the horizontal `y = a`. The `matrix`
  form states the six coefficients directly (§7.8) and is what emitters
  use for exact round-tripping.
- `grid_ref`'s `+` offset accepts a literal point only. The same trailing
  `+ (dx, dy)` on anchor, segment, and between references is the **point
  offset** form (§7.15): the offset applies after the base point resolves.
- `tangent_off`: the **tangent offset** — a vector in the local frame of
  the referenced track (§7.20). `tangent len` runs along the direction of
  travel; `tangent len deg a` rotates it `a` degrees clockwise on screen
  (`deg 90` is the normal, `deg 180` the reverse tangent). Negative
  lengths face backward. Valid on anchor and segment references only.
- `polar_ref`: `polar center=@g 0% radius=40 deg=30` is the point at
  distance 40 from the resolved center, at 30 degrees clockwise on screen
  from the +x axis (§7.16). The radius is unrestricted (negative values
  face the opposite direction).
- `def` declares a named shape at document scope; `use name` is a shape
  that expands to it at resolve time (§7.17).
- `marker` decorates a stroke with baked arrowheads or bars at the ends of
  the shape's track (§7.18).
- `text_stmt`: a text node (§7.19). `at` is a full point (parametric);
  `anchor` defaults to `start`. Strings are double-quoted with `\\"` and
  `\\` escapes; line breaks inside strings are not allowed.

--------------------------------------------------------------------------------

## 5. Program structure

A file is: the magic header, the scene declaration, then any number of paint
declarations, fill/stroke/outline-fill nodes, and grid guides.

### 5.1 Magic and version

`wvg 1` through `wvg 5` — the integer is the format version. Each
version is strictly additive (§12): every older file is a valid newer
file. Loaders accept 1–5 and reject anything else.

### 5.2 Scene

`scene 230 200` declares the canvas width and height (floats, both > 0).
These become `Document.width` / `Document.height`.

### 5.3 Names and declarations

- **Node names** (after `fill`/`stroke`/`outline_fill`/`guide`) must be
  unique across all nodes and must not collide with paint names.
- **Paint names** must be unique and disjoint from node names. A paint may
  only reference paints declared **earlier** in the file (single pass).
- **Node references** (`@name` inside anchor and grid refs) may point to
  nodes declared **later** in the file. Resolution is two-phase: the whole
  file parses first; references resolve afterwards (§7.5). This matches the
  runtime, where `_Resolver` runs only after all nodes exist.

### 5.4 Node ids

The text format does not carry node ids. On load, the loader assigns ids
`n1, n2, …` in declaration order. Two parse-and-emit cycles preserve ids.

### 5.5 Order of drawing (z-order)

Declaration order is draw order. The resolved scene contains each node's
operations in declaration order; a generator node contributes its placements
in expansion order (§7.8). Hidden nodes and grid guides contribute nothing.

--------------------------------------------------------------------------------

## 6. Mapping to the document IR

The IR is the JSON produced by `windvg.document.Document.to_dict` /
`Node.to_dict` / `_spec_to_dict`. Node objects carry: `id`, `name`, `op`
(`"fill"` | `"stroke"` | `"outline_fill"`), `visible`, `shape` (spec dict),
`paint`, `stroke_width`, and `outline_paint` for outline fills.

| Text construct | IR |
| --- | --- |
| `wvg 1` | `"version": 1` |
| `scene W H` | `"canvas": [W, H]` |
| `fill n = s color=p` | node `op="fill"`, `visible=true` |
| `… hidden` | `visible=false` |
| `stroke n = s color=p width=w` | node `op="stroke"`, `stroke_width=w` (default 1.0) |
| `outline_fill n = s color=p outline=q width=w` | node `op="outline_fill"`, `paint=p`, `outline_paint=q`, `stroke_width=w` |
| `guide n = grid …` | node `op="fill"`, `visible=false`, `paint=black`, shape `{"kind":"grid_guide", …}` |
| `guide n = <shape>` | node `op="fill"`, `visible=false`, `paint=black` — a hidden, referenceable shape (when `<shape>` begins with `grid` followed by `motifs`, it is a hidden grid *generator* node, not a grid guide) |
| `paint p = c` | inline expansion of the color (no IR artifact) |
| `circle center=(x,y) radius=r` | `{"kind":"circle","center":[x,y],"radius":r}` |
| `ellipse center=(x,y) rx=a ry=b rotation_deg=d` | `{"kind":"ellipse", …}` (`rotation_deg` defaults 0.0) |
| `arc center=(x,y) radius=r start_deg=a sweep_deg=s` | `{"kind":"arc", …}` |
| `polygon points=[…]` | `{"kind":"polygon","points":[…]}` |
| `polyline points=[…]` | `{"kind":"polyline","points":[…]}` |
| `line p1=a p2=b` | `{"kind":"polyline","points":[a,b]}` |
| `path subpaths=[…]` | `{"kind":"path","subpaths":[…]}` |
| `compound shapes=[…]` | `{"kind":"compound","shapes":[…]}` |
| `along …` | `{"kind":"along","track":…,"motifs":[…],"n":…,"offset_pct":…,"align":…,"direction":"cw"/"ccw"}` |
| `polar …` | `{"kind":"polar","center":…,"motifs":[…],"n":…,"radius":…,"start_deg":…,"align":…}` |
| `grid …` (shape) | `{"kind":"grid","motifs":[…],"cols":…,"rows":…,"dx":…,"dy":…,"origin":…}` |
| `grid` (guide) | `{"kind":"grid_guide","origin":…,"cols":…,"rows":…,"dx":…,"dy":…}` |
| `regular_polygon …`, `star …` | desugars to `{"kind":"polygon", …}` (§7.7) |
| `rounded shape=s radius=r` | `{"kind":"rounded","shape":s,"radius":r}` |
| `rect center=c size=(w,h)` | `{"kind":"rect","center":c,"size":[w,h]}` |
| `pie center=c radius=r start_deg=a sweep_deg=s` | `{"kind":"pie","center":c,"radius":r,"start_deg":a,"sweep_deg":s,"chord":false}` |
| `chord …` | as `pie`, with `"chord":true` |
| `transform = t` (node) | the node's shape becomes `{"kind":"transform","t":[a,b,c,d,e,f],"shape":s}` (§7.14) |
| `group [t] { … }` | syntax sugar: each contained node gets the group transform composed onto its own, then desugars as usual (§7.14) |
| `between p q t%` | `{"between":{"a":p,"b":q,"pct":t}}` |
| `polar center=c radius=r deg=d` | `{"polar":{"center":c,"radius":r,"deg":d}}` |
| `+ (dx,dy)` on anchor/segment/between | `"offset":[dx,dy]` on the reference dict |
| `def name = shape` | document-level `defs` entry `{"name": shape}` |
| `use name` (shape position) | `{"kind":"use","def":"name"}` |
| `marker = end triangle 10` | node `"markers":[{…}]` (§7.18) |
| `text label = at=p content="s" size=n [font=f] [anchor=a] [color=c] [hidden]` | node `op:"text"`, shape `{"kind":"text","at":p,"content":"s","size":n,"font":"sans","anchor":"start"}` (§7.19) |
| `@n cw p% from (x,y)` | `{"anchor":{"node":"n","pct":p,"start":[x,y],"direction":"cw"}}` (omit `start`/`direction` at defaults) |
| `@n seg k p%` | `{"segment":{"node":"n","index":k,"pct":p}}` |
| `@n[c,r] + (x,y)` | `{"grid_cell":{"node":"n","col":c,"row":r,"offset":[x,y]}}` (omit `offset` when absent) |
| `#rrggbb` / `rgb(r,g,b)` / named | `{"kind":"color","rgba":[r,g,b,a]}` |
| `linear start=a end=b start_color=c0 end_color=c1` | `{"kind":"linear", …}` |
| `radial center=c edge=e center_color=c0 edge_color=c1` | `{"kind":"radial", …}` |

Named colors (exact values, alpha 1.0): `black` (0,0,0), `white` (1,1,1),
`red` (1,0,0), `green` (0,1,0), `blue` (0,0,1), `yellow` (1,1,0),
`cyan` (0,1,1), `magenta` (1,0,1), `gray` (0.5,0.5,0.5).

In path instructions, `[ "large" ]` maps to the `large` boolean (default
false) and `[ "cw" | "ccw" ]` to `sweep_cw` (default `cw` = true).

--------------------------------------------------------------------------------

## 7. Semantics

### 7.1 Coordinate system

The canvas is in y-down screen space: **x** grows right, **y** grows down.
All angles are **degrees, measured clockwise on screen** from the local +x
axis. "Clockwise on screen" is the positive travel direction of every closed
track, matching TinyVG and SVG. Points are binary64 pairs; no rounding occurs
before TinyVG quantization (§8).

`cross(a, b) = a.x·b.y − a.y·b.x` is positive exactly when the turn
a→b is clockwise on screen. The **shoelace sum** of a closed point chain
`p₀…pₙ₋₁` is `Σ cross(pᵢ, pᵢ₊₁ mod n) / 2`; a polygon's `winding_sign` is +1
if its shoelace sum is > 0, else −1.

### 7.2 Paints

A color is four binary64 channels in 0..1. Channel values outside 0..1 are
compile errors at paint use. `rgb(r,g,b)` means alpha 1.0. Gradients carry
two points and two colors and are used anywhere a color is.

Paint declarations are a textual convenience: `paint p = …` binds the paint
expression, and every later use of `p` expands to a fresh copy at parse time
(the IR has no named paints).

### 7.3 Points

- **Literal** `(x, y)`.
- **Anchor reference** `@name [cw|ccw] [p%] [from (x,y)]` — §7.5.
- **Grid reference** `@name[col,row] [+ (x,y)]` — §7.6.

Anywhere a point is required (shape centers, polygon vertices, path
instructions), all three forms are allowed. Gradient positions are the
exception: they accept literals only.

**Segment references** — `@name seg k [p%]` addresses one edge of a polygon
or polyline as a miniature open track. The normative definition:

```text
shape = first resolved shape of node        // must be a polygon or polyline
k     = index of the edge                   // see bounds below
p     = clamp(pct, 0, 100) / 100            // open-track rule: clamps, never wraps
point = v[k] + (v[k+1] − v[k]) · p          // plain lerp
```

Edge bounds: a polygon with `n` vertices has edges `0 .. n−1`, where edge
`n−1` is the closing edge `v[n−1] → v[0]`; a polyline with `m` points has
edges `0 .. m−2`. Unlike anchor references, segment references address
**vertex order directly** and ignore `winding_sign`, `cw`/`ccw`, and any
`from` projection — there is no direction to choose on a single edge. A
zero-length edge yields its shared vertex for any `p` (plain lerp, no
special case). Segment references on paths (edge = k-th instruction) are a
candidate future addition, not part of v1.

### 7.4 Shapes as 1D tracks

Every shape exposes the track protocol used by anchors and repetition:

- `perimeter()` — total boundary length.
- `point_at_distance(d)` — boundary point at arc length `d` from the shape
  origin, measured in the positive direction. **Closed tracks wrap** `d`
  modulo the perimeter; **open tracks clamp** `d` to `[0, perimeter]`.
- `tangent_at_distance(d)` — unit tangent in the travel direction at `d`
  (after wrap/clamp).
- `project(pt)` — arc-length position (0..perimeter) of the boundary point
  nearest `pt`.
- `winding_sign` — +1 when the natural parameterization runs clockwise on
  screen, else −1.

Per shape:

| Shape | Origin (`d = 0`) | Positive direction | `winding_sign` | Closed | Fillable | Perimeter |
| --- | --- | --- | --- | --- | --- | --- |
| circle | rightmost point (angle 0) | increasing angle | +1 | yes | yes | `2πr` |
| ellipse | parameter 0 (local +x, then rotated) | increasing parameter | +1 | yes | yes | chordal table (below) |
| arc | angle `start_deg` | sign of `sweep_deg` | +1 if `sweep_deg > 0`, else −1 | no | no | `|sweep_deg|/360 · 2πr` |
| polygon | first vertex | vertex order | shoelace (§7.1) | yes | yes | closed chain length |
| polyline | first point | point order | +1 | no | no | open chain length |
| path | first subpath start | instruction order, subpaths concatenated | shoelace over closed subpaths; +1 if ≥ 0 | all subpaths closed | iff closed | sum of subpath lengths |
| compound | — (no single track) | — | +1 | yes | yes | sum of parts |

**Circle math.** `point_at_distance(d)`: `θ = (d / r) mod 2π`,
`(cx + r·cos θ, cy + r·sin θ)`. `project(pt)`: `atan2(pt−c) mod 2π`, times
`r`; the center projects to 0.

**Ellipse arc-length table.** Ellipse track queries go through a **chordal
arc-length table**: 1440 samples uniformly spaced over the parameter
`[0, 2π)`, cumulative chord lengths, and linear interpolation in both
directions (`param_to_distance`, `distance_to_param`) exactly as in
`windvg.arclength.ArcLengthTable`. The point at parameter `t` is

```text
u = rx·cos t ; v = ry·sin t ; φ = radians(rotation_deg)
point = center + (u·cos φ − v·sin φ, u·sin φ + v·cos φ)
```

`project(pt)`: find the sample index minimizing distance to `pt` (earliest
index wins ties); let `step = 2π/1439` and bracket `[params[i−1],
params[i+1]]` (clamped to the table, adjusted to width `step` when the best
sample is an endpoint); run **48 iterations** of ternary search on that
bracket minimizing Euclidean distance; take the midpoint `t`, reduce `t mod
2π`, and return `param_to_distance(t)`. Independent implementations must
reproduce this procedure, not just its intent — anchor results depend on it.

**Path flattening.** Path track queries (and perimeters) run on a flattened
approximation with tolerance **0.1** (not configurable in v1):

- Lines contribute their endpoint.
- Bézier curves flatten by adaptive de Casteljau subdivision: flat when every
  control point is within tolerance of the chord `p0→p1` (perpendicular
  distance), or at recursion depth 16. Subdivision midpoints follow the
  standard de Casteljau midpoints (`windvg.path._flatten_bezier`).
- Arc instructions flatten by the SVG endpoint-parameterization conversion
  (SVG 1.1 spec F.6.5, including the out-of-range radii scaling), stepped
  uniformly in angle with `steps = max(4, ceil(|Δθ| / max_angle))` and
  `max_angle = 2·acos(clamp(1 − tol / max(rx, ry), −1, 1))`.
- A subpath is *closed* when its chain endpoints lie within 1e-9; a path is
  closed when **all** subpaths are.

**Compound.** A compound has no single track: anchors may not reference it,
and the compile fails with "node has no single track" (§7.11).

### 7.5 Anchor references

`@name [dir] [p%] [from (x,y)]` resolves as follows (normative):

```text
node   = lookup(name)                       // error if no such node
shape  = first resolved shape of node.shape // error if none (grid guide, empty generator)
d0     = project(from_point  if given  else  point_at_distance(0))
signed = direction.mult × shape.winding_sign      // cw=+1, ccw=−1
delta  = (p / 100) × shape.perimeter() × signed
result = shape.point_at_distance(d0 + delta)       // wrap or clamp per §7.4
```

`p` may be any finite number; `p = 150` wraps to 50 on a closed track, and
negative values travel against the chosen direction. On open tracks the sum
`d0 + delta` clamps to the nearer endpoint (through `point_at_distance`).
The referenced node may be declared anywhere in the file, including after
the reference; a hidden node or non-grid guide is a perfectly good target.

### 7.6 Grid guides and grid references

`guide name = grid …` declares a lattice that draws nothing and exports
nothing. Defaults: `origin (0,0)`, `cols 8`, `rows 6`, `dx 40`, `dy 40`.

`@name[col,row]` resolves to `origin + (col·dx, row·dy)`; with
`+ (x,y)` the offset adds afterward. The referenced node must be a grid
guide; a compile error otherwise. Grid values are not required to be integers
(the IR stores them as numbers); only the reference indices are integers.

### 7.7 Desugaring builtin shapes

These constructs exist for hand-written files; the IR only ever sees their
polygon expansion. Computations use binary64 `sin`/`cos`/`tan`/`acos`.

- `regular_polygon center=(cx,cy) radius=r sides=k start_angle_deg=a`
  (k ≥ 3): vertices `i = 0..k−1` at
  `θᵢ = radians(a) + i·2π/k`,
  `(cx + r·cos θᵢ, cy + r·sin θᵢ)`.
- `star center=(cx,cy) outer_radius=ro inner_radius=ri points=k
  start_angle_deg=a` (k ≥ 2, default 5): `2k` vertices `i = 0..2k−1` at
  radius `ro` (even i) / `ri` (odd i),
  `θᵢ = radians(a) + i·π/k`.
- `line p1=a p2=b` — exactly a two-point polyline.

Both wind **clockwise on screen** (positive shoelace) for non-negative
angles and radii.

### 7.8 Generators: along, polar, grid

Generators expand to a list of concrete shapes at resolve time. A **motif
list** may contain any shape specs (including nested generators); each
placement emits every motif in order.

```text
spacing(track, n) = 100.0            if n < 2
                  = 100.0 / n        if track closed
                  = 100.0 / (n − 1)  otherwise   (endpoints included)
```

**along** (defaults `offset_pct 0`, `align tangent`, `direction cw`):

```text
anchor = track.anchor(point_at_distance(0), direction)
step   = spacing(track, n)
for i in 0 .. n−1:
    pct    = offset_pct + i·step
    origin = anchor.point(pct)
    t      = translate(origin)
    if align == tangent:
        u = anchor.tangent(pct)                    // signed unit tangent
        t = t ∘ rotate_degrees(atan2(u.y, u.x))
    emit each motif with t baked in
```

`anchor.tangent(p)` is `tangent_at_distance(distance_of(p)) × signed` where
`signed = direction.mult × winding_sign`. The rotation matrix for angle θ
(clockwise on screen) is `[cos θ, −sin θ; sin θ, cos θ]` applied as
`x' = a·x + c·y + e; y' = b·x + d·y + f`.

**polar** (defaults `start_deg 0`, `align none` — note the different default
than along): build `circle(center, radius)`; if `start_deg ≠ 0`, rotate it
about its center by `start_deg`; then run *along* with the given `align`
(passed through, so `align=none` is polar's default behavior).

**grid**: `for row in 0..rows−1: for col in 0..cols−1:` translate each motif
to `origin + (col·dx, row·dy)`. Row-major, row outer loop.

Baking a transform applies it per shape kind exactly as
`windvg.ext.transform.transformed` does (points transform; circles under
non-similarity maps become ellipses via the singular-value construction;
arc sweeps flip iff the determinant is negative; path instructions
transform pointwise). Motifs are built around the origin.

### 7.9 Rounded

`rounded shape=s radius=r` requires `s` to expand to exactly one shape which
must be a polygon. Each corner is replaced by a fillet arc:

```text
sweep_cw = (shoelace sum > 0)
for each corner v with neighbors prev, next:
    incoming = prev − v ; outgoing = next − v     // l1, l2 = their lengths
    α = acos(clamp(incoming·outgoing / (l1·l2), −1, 1))
    cut = r / tan(α/2) ; limit = 0.5·min(l1, l2)
    error if cut > limit
    if cut < 1e-9: straight through (no arc)
    arc from v + incoming·(cut/l1) to v + outgoing·(cut/l2),
    arc_circle_to(r, large=false, sweep_cw=sweep_cw)
close the path
```

The result is a `path` spec of exact line + arc instructions. Repeated
vertices are an error.

### 7.10 Operations

- **fill** — the shape must be fillable (polygon, circle, ellipse, closed
  path, compound, rect, pie, chord). Arcs and polylines cannot fill.
- **stroke** — any shape; `width` ≥ 0, default 1.0.
- **outline_fill** — fillable, **not** a compound; `width` ≥ 0, default 1.0.
- **hidden** — the node survives in the document but resolves to nothing.
  Grid guides are always hidden.
- A generator expanding to zero shapes (e.g. `n = 0`) contributes nothing
  and is not an error by itself.

### 7.11 Validation errors

A conforming implementation must reject (with a diagnostic identifying the
node or token):

| Category | Conditions |
| --- | --- |
| Syntax | any grammar violation; wrong version; missing/duplicate `scene` |
| Names | duplicate node, paint, or def name; name collision across kinds; reserved word used as name; unknown `@` reference; unknown `use` def; unknown text font; paint used before declaration |
| References | anchor target expands to no shapes (grid guide, `n = 0` generator) or to a compound; segment target is not a polygon/polyline or is out of edge bounds; grid-cell target is not a grid guide; cyclic reference chains; cyclic `def` chains |
| Shapes | circle/arc/pie/chord radius ≤ 0; arc/pie/chord sweep outside `0 < |sweep| < 360`; ellipse rx or ry ≤ 0; rect size components ≤ 0; polygon with < 3 points or zero shoelace; polyline with < 2 points; path with zero subpaths or an empty subpath; regular_polygon sides < 3; star points < 2 |
| Generators | along track expands to ≠ 1 shape; polar radius ≤ 0; grid cols or rows < 1 |
| Rounded | operand not a single polygon; radius ≤ 0; fillet does not fit a corner; repeated polygon points |
| Ops | fill of a non-fillable shape; outline_fill of a compound; negative width; marker on a non-stroke node; marker size ≤ 0 |
| Scene | width or height ≤ 0 |
| Encoding | (§8) coordinates/widths or canvas size out of range for the chosen coordinate units |

Percentages, angles, and offsets are unconstrained beyond finiteness; their
effects are defined by §7.4–§7.5.

### 7.12 rect, pie, chord

**rect** `center=c size=(w,h)` — an axis-aligned rectangle, stored as an IR
kind (the center may be parametric). Resolves to a closed polygon with the
four corners `c ± (w/2, h/2)` wound clockwise on screen:
`top-left, top-right, bottom-right, bottom-left`. Both `w` and `h` must be
positive.

**pie** and **chord** `center=c radius=r start_deg=a sweep_deg=s` — closed
fillable paths built from an `arc` exactly as `rounded` builds paths:

```text
p_start = c + r·(cos a, sin a)
p_end   = c + r·(cos (a+s), sin (a+s))
pie:   subpath { start = p_start, arc_circle r (large = |s| > 180)
                 sweep_cw = (s > 0) to p_end, line to = c, close }
chord: subpath { start = p_start, arc_circle r (large = |s| > 180)
                 sweep_cw = (s > 0) to p_end, close }
```

Constraints as for `arc`: `r > 0` and `0 < |s| < 360`. The center may be
parametric.

### 7.13 between points

`between p q t%` resolves both operands as full points (either may itself
be an anchor, segment, or grid reference, recursively) and returns the
linear blend

```text
result = p + (q − p) · (t / 100)
```

`t` is unrestricted: values outside `[0, 100]` extrapolate along the
p–q line. The **second operand always carries an explicit percentage**,
and the trailing percentage belongs to `between`: `between @a @b 0% 50%`
blends the 0%-positions of `a` and `b`; `between @a @b 30% 50%` blends
the 30%-position of `b`. Omitting the second operand's percentage is a
parse error. Cyclic `between` chains are impossible (points reference
shapes, not points), but a `between` operand referencing a node whose
shape contains the same `between` is a cycle like any other (§7.11).

### 7.14 Transforms and groups

A node-level `transform = t` wraps the node's shape in a transform spec
whose matrix is written to the IR as six coefficients `(a, b, c, d, e, f)`
with the windvg convention:

```text
x' = a·x + c·y + e
y' = b·x + d·y + f
```

The named forms map as follows (angles in degrees, clockwise on screen;
`about` defaults to the origin):

```text
translate tx ty        → e = tx, f = ty
rotate θ about c       → T(c) · R(θ) · T(−c),  R = [cos −sin; sin cos]
scale sx [sy] about c  → T(c) · S(sx, sy) · T(−c)   (sy defaults to sx)
mirror_x a             → a = −1, e = 2a            (reflect x = a)
mirror_y a             → d = −1, f = 2a            (reflect y = a)
matrix a b c d e f     → the coefficients themselves
```

At resolve time the transform is **baked** into concrete shapes exactly as
`windvg.ext.transform.transformed` does (points transform; circles under
non-similarity maps become ellipses; arc sweeps flip iff the determinant
is negative; path instructions transform pointwise).

A `group [t] { … }` is syntax sugar: the group's transform composes onto
each contained node's own transform (own first, then the group's —
`group_t ∘ node_t`), and the children desugar as ordinary nodes. Groups
may nest; nested group transforms accumulate outward-in. Paints declared
inside a group are hoisted to document scope in declaration order. Groups
themselves are not nodes: they are not referenceable and do not exist
after parsing.

### 7.15 Point offsets

An anchor, segment, grid, or between reference may carry a trailing
`+ (dx, dy)`. The offset is added **after** the base point resolves, so it
composes with every reference kind and nests cleanly: a `between` operand
applies its own offset during its resolution, and the blend's offset
applies to the blended result. Grid references already used this syntax
for their cell offset; the meaning is identical everywhere — *resolve,
then nudge*.

### 7.16 Polar points

`polar center=c radius=r deg=d` resolves to
`c + r·(cos d°, sin d°)` — degrees clockwise on screen from the +x axis,
the universal windvg angle convention. `r` is unrestricted: negative
values point the opposite way. The center is a full point and may itself
be an anchor, between, or another polar form.

### 7.17 Defs and use

`def name = shape` declares a named shape at document scope. A def is not
a node: it draws nothing and has no z-order. `use name` is a shape that
expands to the def's shape at resolve time, inheriting its track and fill
semantics completely.

- Def names are unique across nodes, paints, and defs, and are not
  reserved words.
- Defs may reference nodes with anchors and other defs with `use`;
  resolution is two-phase like everything else. **Cyclic chains are
  compile errors.**
- `use` of an unknown def is a compile error.
- A node whose shape is a `use` expands to the def's shapes; if the def
  expands to several shapes the node contributes several ops.

### 7.18 Markers

A stroke node may carry one `marker = placement kind size [paint]`:

```text
placement = start | end | both     (points of the shape's track)
kind      = triangle | bar
size      > 0
paint     optional; defaults to the node's stroke paint
```

The geometry uses the resolved shape's track protocol (§7.4):

```text
P = point_at_distance(d)        d = 0 for start, perimeter for end
t = tangent_at_distance(d)      n = (t.y, −t.x)   (left of travel)
triangle: polygon [ P,  P − t·s + n·(0.4·s),  P − t·s − n·(0.4·s) ]
bar:      polygon [ P + t·(s/2) + n·(s/10),  P + t·(s/2) − n·(s/10),
                    P − t·(s/2) − n·(s/10),  P − t·(s/2) + n·(s/10) ]
```

Marker polygons are ordinary fill ops appended after the stroke op — they
bake at resolve, so every encoder and renderer treats them like any other
polygon. Markers are only valid on stroke nodes. For open tracks the
tangent at `d = perimeter` points outward; on closed tracks the "end" is
the origin with the origin tangent — `end` markers are meant for open
tracks (lines, polylines, arcs, open paths).

### 7.19 Text (fidelity tier B)

`text label = at=p content="s" size=n [font=f] [anchor=a] [color=c]
[hidden]` declares a **text node**: the string `content`, positioned with
its baseline **start** at the resolved point `p` (a full point — anchors
and offsets compose), rendered at `size` in the font `f` (v1 bundles
`sans` only), horizontally aligned per `anchor` (`start`: baseline starts
at `p`; `middle`: centered on `p.x`; `end`: baseline ends at `p.x`), and
filled with `color` (default black).

**Fidelity tier.** TinyVG 1.0 cannot encode text, so text is the first
**tier B** construct: it survives in `.wvg` documents and SVG export
(live, editable `<text>`), and is **dropped at TinyVG export** — encoders
fail with a diagnostic unless an explicit drop-text option is set, and
the diagnostic lists the dropped nodes. Hosts MAY bake text to outline
paths at resolve time using a bundled font (recommended: Noto Sans
Regular, OFL 1.1); baked geometry is engine-local and exempt from
cross-host byte-exact conformance (§9).

Resolution: `p = resolve(at)`; the string's total advance width `W` is
measured in the resolved font at `size`; the pen origin is
`p.x − (W/2 | W | 0)` for `middle`/`end`/`start`; each character maps
through the font cmap (missing → `.notdef`), advances by its `hmtx`
width scaled by `size/unitsPerEm`, and its TrueType outline (y-up) is
emitted flipped into y-down at the pen position. Kerning is off in v1.
Font bundles are resolver components: the *syntax* is core, the *glyphs*
are pluggable with fallback (missing font → placeholder boxes + warning).

--------------------------------------------------------------------------------

## 8. TinyVG encoding contract

The back half of the pipeline (`Scene` → `.tvg`) is normative for
implementations. It is the TinyVG 1.0 specification
(https://tinyvg.tech/specification) with these pinned choices and quirks:

**Quantization.** A value `v` becomes `q = round(v · 2^scale)` using
**round-half-to-even** (banker's rounding — *not* half-away-from-zero).
`scale` defaults to 4 (1/16 unit) and is a compile option, not file content.
`q` is written as a little-endian signed integer of the active coordinate
width. Canvas dimensions in the header are `round(w)` / `round(h)` (also
half-to-even) and must satisfy `0 < round(dim) < 2^(bits−1)`.

**Coordinate range selection.** Compute the minimum and maximum *unit value*
over every visible op: shape geometry (polygons: their points; circles:
exact bounding box; ellipses: exact rotated bounds `hw = hypot(rx·cos φ,
ry·sin φ)`, `hh = hypot(rx·sin φ, ry·cos φ)`; arcs: 65 samples along the
sweep; paths: the flattened chain expanded by ± tolerance; compounds:
recursively), all gradient points, and **all stroke/outline widths**. With
`lo_q = round(lo·2^scale)`, `hi_q = round(hi·2^scale)`: if both fit in
16-bit signed range, use 16-bit units; else if both fit 32-bit, use 32-bit;
else it is an encoding error.

**Color table.** RGBA8888. Colors are collected from visible ops in order:
for each op, the paint's colors in ramp order (flat: 1; gradients: start→end
/ center→edge), then the outline paint's colors; duplicates are dropped
keeping the **first** occurrence, comparing all four channels by exact
binary64 equality. (Two textual spellings of the same byte — `#f00` and
`rgb(1,0,0)` — are the same entry; `rgb(1,0,0)` and `rgb(0.9999,0,0)` are
not.) Each color quantizes with `clamp(round(c·255), 0, 255)` per channel,
half-to-even.

**Commands.** For each visible op, in order:

| Shape | Op | Commands |
| --- | --- | --- |
| polygon | fill | `FILL_POLYGON` |
| polygon | stroke | `DRAW_LINE_LOOP` |
| polygon | outline_fill, ≤ 64 points | `OUTLINE_FILL_POLYGON` |
| polygon | outline_fill, > 64 points | `FILL_POLYGON` then `DRAW_LINE_LOOP` |
| polyline | stroke | `DRAW_LINE_STRIP` |
| arc | stroke | `DRAW_LINE_PATH` (one segment: start point, one `ARC_CIRCLE`, `large = |sweep| > 180`, `sweep_cw = sweep > 0`) |
| arc | fill / outline_fill | compile error |
| circle / ellipse | any | one path segment: origin point, two half arcs (`ARC_CIRCLE` / `ARC_ELLIPSE`, `large=false`, `sweep_cw=true`) to the opposite point and back, then `CLOSE_PATH` — as `FILL_PATH` / `DRAW_LINE_PATH` / `OUTLINE_FILL_PATH` |
| path | fill / stroke | `FILL_PATH` / `DRAW_LINE_PATH` with its subpaths |
| path | outline_fill, ≤ 64 segments | `OUTLINE_FILL_PATH` |
| path | outline_fill, > 64 segments | `FILL_PATH` then `DRAW_LINE_PATH` |
| compound | fill | `FILL_PATH`, all sub-shapes as segments |
| compound | stroke | one `DRAW_LINE_PATH` per sub-shape |
| compound | outline_fill | compile error |

Path commands emit, in order: `varuint(segment_count − 1)`, the paint
style(s), width (where applicable), then all segment command counts
(`varuint(instructions − 1)` each), then the segment bodies (start point +
instructions). Circles/ellipses encode as 1 segment (`varuint(0)`, segment
count 2 = two arcs + close).

**Styles.** Flat colors are palette indices (`varuint`); gradients inline
their two points and two palette indices (start/end or center/edge). Style
kind occupies bits 6–7 of the command byte (0 flat, 1 linear, 2 radial); for
outline fills the outline's style kind occupies bits 6–7 of the payload byte
that also holds `count − 1` in bits 0–5.

**Rotation quirk.** `ARC_ELLIPSE` stores rotation **negated**: the file
receives `−rotation_deg` (both for ellipse shapes and ellipse arc
instructions), because TinyVG stores rotation in the mathematical-negative
direction while windvg's convention is clockwise-on-screen.

**Header.** Magic `72 56`, version `1`, then
`scale | (color_encoding << 4) | (coord_range << 6)` with color encoding 0
(RGBA8888) and coord range 0 (16-bit) or 2 (32-bit), then width and height,
then the color table, commands, and the `0x00` end marker.

--------------------------------------------------------------------------------

## 9. Conformance and golden vectors

An implementation conforms when, for every case in the golden-vector suite,
it produces:

1. `document.json` — the Document IR (ids `n1..nN` in declaration order),
   compared with exact structural equality and binary64-exact numbers;
2. `ops.json` — the resolved draw ops (`resolve_to_json`), compared with
   absolute/relative tolerance ≤ 1e-9 per float (flattened paths and
   ellipse tables make bit-exactness across languages impractical here);
3. `output.tvg` — **byte-exact**.

The suite must cover, at minimum: every shape kind filled/stroked/
outline-filled; anchors on every track kind (including wrap `p > 100`,
negative `p`, open-track clamping, `from` projection); polygon windings both
ways; segment references (closing edge `n−1`, both windings, `p` clamping at
`0`/`100`/`−50`/`150`, zero-length edges, refs nested in path instructions);
ellipse anchors at several rotations; paths with holes and multi-
subpath tracks; along/polar/grid including `align=none`, open tracks, multi-
motif lists, and `n = 0`; rounded at the exact fit limit; grid guides and
cell offsets; all color spellings and the color-table dedup rules; gradient
paints; the 16→32-bit coordinate upgrade; the > 64-point outline fallback;
and the ellipse-rotation negation.

Text documents (§7.19, tier B) are exempt from the byte-exact `.tvg`
comparison: hosts bake glyphs with engine-local settings, so text
documents conform via their SVG export (exact `<text>` string match) and
their resolved metadata (at/content/size/anchor). Non-text documents
remain byte-exact. Implementations are encouraged to expose the IR and
ops JSON verbatim in their APIs so third-party tooling can diff against
the suite.

--------------------------------------------------------------------------------

## 10. Versioning and extension policy

- Version 2 is additive over version 1: every v1 file is a valid v2 file.
  Version 1 is frozen: no construct changes meaning, and any file using
  features defined here must behave identically under every conforming
  implementation.
- Future versions may add constructs; loaders must reject higher versions
  rather than guess. Unknown properties are errors (strict parsing) — there
  are no optional extensions inside a version.
- Excluded from v2, with room to add later: arithmetic expressions,
  clip paths and masks (Tier B/C — see `format-review.md` §5),
  `rule=nonzero`, star polygons via skip traversal (`star_polygon`),
  segment references on paths, and path tolerance configuration.
  Markers, symbol defs/use, the text construct, and tangent offsets
  arrived in v3/v4/v5; dash patterns remain a Tier B candidate.

Python's `Document.generate_code()` (Python-source persistence) remains an
independent, optional export for generative workflows; `.wvg` is the
interchange and editor format.

--------------------------------------------------------------------------------

## Appendix A — Reserved words

Identifiers must not be any of the following keywords, property names, or
named colors:

```text
align       arc         arc_circle  arc_ellipse  along      between
black       blue        c1          c2           ccw        center
center_color chord      circle      close        color      cols
compound    ctrl        cw          cyan         direction  dx
dy          edge        ellipse     end          end_color  fill
from        gray        green       grid         guide      hidden
inner_radius large     line        linear       magenta    matrix
mirror_x    mirror_y    motifs      n            none       offset_pct
origin      outline     outline_fill outer_radius p1         p2
paint       path        pie         points       polar      polygon
polyline    quad        radial      radius       red        regular_polygon
rgba        rgb         rounded     rotation_deg rows        rotate
rx          ry          scale       scene        seg        shape
shapes      sides       star        start        start_angle_deg
start_color start_deg   stroke      subpaths     sweep_deg  tangent
to          track       transform   translate    wvg        white
width       yellow
```

## Appendix B — Complete example

```text
// donut.wvg
wvg 1
scene 200 200

paint glaze = radial center=(90,90) edge=(140,110)
  center_color=#ff9aa2 edge_color=#c2404d

guide outer = circle center=(100,100) radius=80

fill donut = compound shapes=[
  circle center=(100,100) radius=80,
  circle center=(100,100) radius=35
] color=glaze

// an invisible hexagonal hull, referenced by segment anchors
fill hull = regular_polygon center=(100,100) radius=85 sides=6 color=#3e6fa8 hidden
stroke tick = line p1=@hull seg 2 50% p2=@hull seg 3 50% color=#5a8fd6 width=1.5

stroke sprinkles = along
  track=circle center=(100,100) radius=57
  motifs=[line p1=(-8,0) p2=(8,0)]
  n=9 offset_pct=4% align=tangent direction=cw
  color=#ffffff width=4

// parametric tie: from 25% cw on the outer guide to cell (2,3) of a grid
guide lattice = grid cols=5 rows=4 dx=40 dy=40 origin=(0,0)
stroke tie = line p1=@outer 25% p2=@lattice[2,3] + (10,-5)
  color=#222222 width=2
```
