# Scripting windvg: the Lua extension layer

**Status: design — v1 API surface, embedding architecture, conformance policy**

`.wvg` is deliberately declarative: no expressions, no loops, no code
execution. That identity is what keeps documents safe to open, small,
diffable, and implementable in three languages. But everything
*procedural* — spirals, fractals, charts, gear teeth placed by real
trigonometry — needs computation somewhere.

The answer is a **scripting layer beside the language, not inside it**:
scripts written in **Lua** build document IR through a builder API and
hand it to a host (the CLI, an editor) which resolves and encodes it with
the existing engines. The language stays declarative; the safety property
stays intact; and all resolution semantics stay in the three
implementations rather than being reimplemented in Lua.

```text
gears.lua ──(wv builder API)──▶ Document IR ──resolve──▶ ops ──▶ .tvg / .svg / .wvg
```

This is the same shape as the Python `windvg` library — which has been a
scripting layer all along — now made portable.

--------------------------------------------------------------------------------

## 1. Decision record

| Decision | Choice | Rationale |
| --- | --- | --- |
| Language | **Lua 5.4** | The only interpreter with first-class support in all three hosts: mlua (Rust), LuaJ (pure-Java, Android-proven), lupa (Python). Rhai and Wren are Rust/C-locked; QuickJS has weak JVM ports. |
| Script locus | **Standalone generators** | `windvg run gears.lua -o gears.tvg`. Documents remain 100% code-free — opening a `.wvg` never executes anything. Document-embedded extension references are deferred (§7) and would ship with a trust model, never by default. |
| Sandbox | **Trusted-local** | Scripts run with the full standard library (`io`, `os` included). This matches CLI reality and keeps v1 simple. A restricted environment (no `io`/`os`, instruction budget, `wv.rng`-only randomness) is reserved for the embedded/document-referencing future. |
| API shape | **Builder over the IR** | Scripts construct the same spec kinds the language parses — anchors, between blends, and grid references stay *parametric* in the output document. No geometry is reimplemented in Lua; resolution and encoding stay in the cores. |

**The promotion path.** Extensions that prove popular graduate into the
declarative core — the way `rect`, `pie`, and `between` were added in
v2. The dividing rule from `format-review.md` stands: if an editor needs
the *relationship* to survive editing, it belongs in core; if only the
*result* matters, a script (or baked construct) is the right home.

--------------------------------------------------------------------------------

## 2. Script contract

A script is a Lua 5.4 chunk executed with the global **`wv`** table
preloaded. Its contract:

1. It calls `wv.document(width, height)` to create a document handle.
2. It fills the document through the builder methods (§3).
3. It **returns the document** as its last statement.

```lua
-- dots.lua — a spiral of dots (declarative .wvg cannot express this)
local doc = wv.document(200, 200)
local rng = wv.rng(7)
local palette = { "#4073cc", "#5a95e0", "#7fb2f2", "#a9cef7" }
for i = 1, 120 do
  local t = i / 120
  local a = t * math.pi * 12
  local r = 10 + 80 * t
  doc:fill(nil, wv.circle{
    center = { 100 + r * math.cos(a), 100 + r * math.sin(a) },
    radius = 2 + 3 * t,
  }, palette[1 + i % #palette])
end
return doc
```

The host resolves the returned document and encodes it per its output
flags (`windvg run dots.lua --format tvg -o dots.tvg`). Script errors
(missing fields, type mismatches) and resolution errors (unknown
references, non-fillable fills) abort with a diagnostic naming the script
and, where available, the Lua line.

Nothing a script builds is written anywhere except through the host's
output flags — running a script has no effect on the filesystem beyond
the requested output.

--------------------------------------------------------------------------------

## 3. API surface (v1 — normative for the first implementation)

All constructors take a single **named-field table** and return an opaque
spec value. Unknown fields are **errors** (strict, mirroring the
language), and every spec field maps 1:1 onto the document IR keys — the
Lua API is the JSON schema with braces swapped for tables.

### 3.1 Document handle

```lua
local doc = wv.document(width, height)
doc:fill(name, shape, paint)                          -- op = fill
doc:stroke(name, shape, paint, width)                 -- width optional, default 1.0
doc:outline_fill(name, shape, paint, outline, width)  -- width optional
doc:guide(name, grid_guide_spec)                      -- grid guide (invisible)
```

- `name` is a string, or `nil` for auto-generated names (`shape1`, `shape2`, …).
- Names must be unique and are not reserved words (the language's rules).
- Hidden nodes (guides for anchor targets) are created via
  `doc:guide(name, wv.grid_guide{ … })` for lattices, or as ordinary
  fills/strokes the editor hides; v1 scripts rarely need them.

### 3.2 Shape constructors

Every field maps 1:1 onto the spec keys from `language.md` §6.

| Constructor | Fields |
| --- | --- |
| `wv.circle` | `center, radius` |
| `wv.ellipse` | `center, rx, ry, rotation_deg?` |
| `wv.arc` | `center, radius, start_deg, sweep_deg` |
| `wv.rect` | `center, width, height` |
| `wv.pie` / `wv.chord` | `center, radius, start_deg, sweep_deg` |
| `wv.polygon` / `wv.polyline` | `points` (list of point specs) |
| `wv.line` | `p1, p2` |
| `wv.path` | `subpaths` (list of `wv.sub` values) |
| `wv.sub` | `start, instructions` |
| `wv.compound` | `shapes` (list) |
| `wv.along` | `track, motifs, n, offset_pct?, align?, direction?` |
| `wv.polar` | `center, motifs, n, radius, start_deg?, align?` |
| `wv.grid` | `motifs, cols, rows, dx, dy, origin?` |
| `wv.regular_polygon` | `center, radius, sides, start_angle_deg?` |
| `wv.star` | `center, outer_radius, inner_radius, points?, start_angle_deg?` |
| `wv.rounded` | `shape, radius` |
| `wv.grid_guide` | `origin?, cols?, rows?, dx?, dy?` |
| `wv.transformed` | `transform, shape` |

`wv.sub` instructions mirror the IR instruction dicts exactly:

```lua
{ cmd = "line",  to = p }
{ cmd = "quad",  ctrl = p, to = p }
{ cmd = "cubic", c1 = p, c2 = p, to = p }
{ cmd = "arc_circle",   radius = r, large = b, sweep_cw = b, to = p }
{ cmd = "arc_ellipse",  rx = r, ry = r, rotation_deg = d,
  large = b, sweep_cw = b, to = p }
{ cmd = "close" }
```

### 3.3 Point forms

A **point spec** is a literal `{ x, y }` table or one of:

```lua
wv.anchor{ node = "gear", pct = 25, dir = "ccw", from = { x, y } }  -- pct/dir/from optional
wv.segment{ node = "hull", index = 2, pct = 50 }                    -- pct optional
wv.grid_cell{ node = "lattice", col = 2, row = 1, offset = { x, y } }
wv.between{ a = p, b = q, pct = 50 }                                -- pct unrestricted
```

The `between` second-operand rule from the language (§7.13: the second
operand carries an explicit percentage; the trailing percentage is the
blend's) does not apply here — Lua fields are named, so there is no
ambiguity to resolve. Emitters still write the canonical explicit form.

### 3.4 Transforms

The transform constructors return six-coefficient tables
`(a, b, c, d, e, f)`, consumed by `wv.transformed`:

```lua
wv.translate{ 40, 20 }                    -- positional: tx, ty
wv.rotate{ deg = 45, about = {100, 100} } -- about optional, default origin
wv.scale{ sx = 1.5, sy = 1, about = {0, 0} }
wv.mirror_x{ axis = 50 }
wv.mirror_y{ axis = 50 }
wv.matrix{ a, b, c, d, e, f }             -- positional: six coefficients

doc:fill("spun", wv.transformed{
  transform = wv.rotate{ deg = 45, about = {100, 100} },
  shape = wv.rect{ center = {100, 100}, width = 20, height = 20 },
}, "#43a047")
```

Baking happens at resolve time inside the host engine — the script never
does matrix math it does not want to.

### 3.5 Paints

A paint is a string (`"#rrggbb"`, `"#rrggbbaa"`, or a named color:
`"black"`, `"white"`, `"red"`, …, `"gray"`) or:

```lua
wv.linear{ start = p, end = p, start_color = c, end_color = c }
wv.radial{ center = p, edge = p, center_color = c, edge_color = c }
```

### 3.6 Introspection and determinism helpers

```lua
wv.version            -- 1
wv.rng(seed)          -- deterministic PRNG: :next() [0,1), :range(a, b), :int(a, b)
doc:nodes()           -- list of { name = …, op = … } (inspection)
doc:to_ir()           -- the document as a plain Lua table (the JSON schema)
```

`wv.rng` exists so *shared* scripts can be deterministic by construction;
trusted-local scripts that use `os.time()` own their nondeterminism.

--------------------------------------------------------------------------------

## 4. Trust, sandboxing, determinism

- **Trusted-local (v1).** Scripts run with the full standard library.
  Running a script is running code; only run scripts you trust. This is
  the same trust model as Makefiles and LaTeX documents.
- **Determinism.** For a given host engine, a script's output is
  byte-deterministic unless the script itself draws from an external
  source (`os.time`, files). Shared scripts should derive all
  randomness from `wv.rng(seed)`.
- **Reserved: restricted mode.** When scripts become
  document-embedded (§7), hosts will run them in a restricted
  environment: no `io`/`os`, an instruction budget, and only `wv.rng`
  for randomness. Nothing in the v1 API surface depends on the
  environment, so the same scripts run in both modes.

--------------------------------------------------------------------------------

## 5. Conformance policy

The golden corpus (`tests/scripts/*.lua` in windvg-rs) is the contract
between hosts:

1. **Cross-host: resolved ops, tolerant.** Two hosts run the same script
   and compare resolved-ops JSON with `1e-9` relative tolerance. They
   will *not* be byte-identical: C Lua's `math.sin` and LuaJ's differ by
   ulps, and those differences propagate into coordinates.
2. **Per-host: `.tvg` bytes, exact.** Each host's output must match its
   own engine byte-for-byte (quantization is host-local, so libm ulps
   that survive resolution usually wash out at 1/16-unit quantization —
   but tolerance across hosts remains the honest contract).

The v1 corpus: `gears_loop.lua` (loop-placed teeth), `spiral.lua`
(phyllotaxis with `wv.rng`), `chart.lua` (bar chart from a table),
`parametric.lua` (anchors, between, grid-cell refs built in Lua),
`koch.lua` (recursive edge subdivision → path), `wave.lua` (sine
polyline). Each ships with expected ops JSON; the Rust host additionally
freezes expected `.tvg` bytes.

--------------------------------------------------------------------------------

## 6. What scripts can and cannot express

**In — the point of the layer:** loops and recursion (Koch subdivision),
trigonometry (Lissajous, phyllotaxis), data-driven drawing (charts from
tables), seeded randomness, parameterized shape libraries as Lua modules
(`require "shapes.gears"`), importers (CSV/JSON → drawings in trusted
mode).

**Out — deliberately:**

- **Document-embedded scripts.** Deferred until standalone proves out;
  requires the restricted environment and a trust UI (§4).
- **Scene-level painting.** Scripts build IR, not pixels; there is no
  direct "draw a triangle now" canvas. Resolution stays in the engines.
- **Bypassing validation.** Everything a script builds flows through the
  same resolve semantics — a script cannot produce a document that a
  hand-written `.wvg` could not.
- **Kotlin/Python hosts.** LuaJ (Android) and the lupa adapter are the
  next phase; the corpus above is their conformance target.

--------------------------------------------------------------------------------

## 7. Future work, in order

1. **Rust host** (`windvg run`) — this design, implemented with mlua
   (vendored Lua 5.4), the v1 corpus, and per-host golden freezing.
2. **Kotlin host** — LuaJ embedding behind the same API; the corpus runs
   on-device; windstudio-mobile gains a "run script" import.
3. **Python adapter** — lupa executing the same corpus against the
   Python reference (completing the three-host conformance triangle).
4. **Document-embedded extension references** — `use script "gears.lua"
   with { teeth = 14 }`-style declarations, gated behind the restricted
   environment and an explicit trust prompt; requires the fidelity-tier
   policy from `format-review.md` §5 first.
5. **Sugar** — path-instruction helpers (`wv.turtle`), a chart module,
   and whatever the corpus proves people write most.

Promotion remains the endgame: an extension hot enough becomes a
declarative construct in the next additive language version — the same
path `rect`, `pie`, and `between` took from "obvious thing everyone
hand-computes" to core.
