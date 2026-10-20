# DESIGN.md: results dashboard (demo track, ADR-019)

**Reference style: Linear (`awesome-design-md` → `linear.app`).** Reason: it is the closest match to what this site
is, a dark, data-dense, precision-engineered product UI where content emerges from a near-black canvas, with
one accent colour, hairline translucent borders and quiet typography. It lets charts and numbers carry the page.
We reproduce the style (tokens, density, depth), not the brand: no logo, wordmark or copy.

## 1. Principles
1. **Numbers first.** Every number on the site is read through the DataSource and shows its source file and config hash on hover/focus and in a footnote. A missing result is a labelled "not run" state, never a placeholder that looks like data.
2. **Never colour-only.** Every series is told apart by colour AND a second channel (marker shape, dash pattern, direct label). The palette is colour-blind-safe (Okabe-Ito).
3. **Dark by default, readable by design.** Contrast of body text on its surface is at least 7:1, secondary text at least 4.5:1.
4. **Motion explains, never decorates.** Short eased transitions; `prefers-reduced-motion: reduce` turns all non-essential motion off (replay still works, stepped instead of animated).
5. **Plain fallback first.** Every page works as static, semantic HTML + SVG before any polish.

## 2. Tokens

### Surfaces and text (from the Linear reference)
| Token | Value | Use |
|---|---|---|
| `--bg` | `#08090a` | page canvas |
| `--panel` | `#0f1011` | panels, sidebar |
| `--surface` | `#191a1b` | cards, popovers |
| `--surface-hover` | `#28282c` | hover state |
| `--border` | `rgba(255,255,255,0.08)` | cards, inputs |
| `--border-subtle` | `rgba(255,255,255,0.05)` | dividers |
| `--text` | `#f7f8f8` | primary text |
| `--text-2` | `#d0d6e0` | body, descriptions |
| `--text-3` | `#8a8f98` | metadata (still ≥ 4.5:1 on `--bg`) |
| `--accent` | `#7170ff` | links, focus ring, selection |
| `--accent-hover` | `#828fff` | hover on accent |

### Data palette (Okabe-Ito, colour-blind safe) with the second channel
| Series | Colour | Marker / dash |
|---|---|---|
| Learned agents (DDQN) | `#E69F00` orange | filled circle, solid line |
| SED (global) | `#56B4E9` sky blue | square, solid |
| SED (local) | `#0072B2` blue | square, dashed |
| Cache-aware | `#009E73` green | triangle, solid |
| Random / round-robin | `#CC79A7` purple | diamond, dotted |
| JSQ / Po2 | `#F0E442` yellow | cross, dotted |
| Breach / error | `#D55E00` vermillion | with an icon and text, never colour alone |

Confidence intervals: a translucent band (same hue, 18% opacity) plus whiskers; the mean is always a marker.

### Typography
System-first stack so the site needs no font download: `Inter, "SF Pro Text", -apple-system, "Segoe UI", Roboto, system-ui, sans-serif`; numerals `font-variant-numeric: tabular-nums`; mono `ui-monospace, "SF Mono", Menlo, monospace` for file paths, hashes and logs. Scale (px / weight): display 40/510, h1 28/510, h2 20/590, body 15/400 (line height 1.6), caption 13/400, micro 11/510. Display sizes use slightly negative letter-spacing (-0.02em), body none.

### Spacing, radius, depth
4 px base scale: 4, 8, 12, 16, 24, 32, 48, 64. Radius: 6 (controls), 8 (cards), 12 (featured panels). Depth by border and a 1 px translucent outline, not heavy shadows. Page gutter 16 px on phones, content max width 1120 px, charts fill the card width. Phone layout: one column, tabs become a scrollable pill row, no horizontal page scroll.

### Charts
Hand-built SVG: thin 1 px gridlines at `--border-subtle`, axis labels in `--text-3` with units, direct labels at line ends, tooltip on hover AND keyboard focus. Every chart has a title, an axis label with units, a 95% CI where the evaluation has one, and a footnote with the source file and config hash. Empty data renders the "not run" card, not an empty axis.

### Server visual language (replay and hero)
- **Fast-expensive** server: solid rounded square, accent-blue outline, label "fast, expensive".
- **Slow-cheap** server: outlined circle, dashed outline, label "slow, cheap".
- Queue = a bar under the server (length = waiting requests); KV fullness = a thin ring that turns vermillion above 80% (plus a text label "KV 83%").
- Request = small dot sized by prompt tokens; a dot that missed its SLA gets a ring and an "x" glyph at completion.
- Agent decision markers: Accept = filled dot, Forward = arrow, Defer = clock glyph (shape, not colour).

### Motion
Durations 120 ms (hover), 200 ms (panels), 320 ms (page/section), ease-out `cubic-bezier(0.2, 0.7, 0.2, 1)`. Replay playback speed is user-controlled (0.5x to 16x) and independent of CSS motion. Reduced motion: no transforms/fades; the replay advances in discrete steps on Play and via the scrubber; scroll-linked hero animation becomes a static diagram.

## 3. Budgets and rules
- Initial JavaScript at most 150 kB gzip (React + app code, no charting library, no animation library).
- Layout works at 375 px width; no horizontal page scroll; touch targets at least 40 px.
- Keyboard: every control reachable in order, visible focus ring (2 px `--accent`), replay controls have shortcuts (space = play/pause, arrows = step).
- Semantic landmarks (`header`, `nav`, `main`, `section` with headings); charts have a text summary and a data table toggle.
- Console must be clean in the final screenshots check.
