# Kitden motion

How the page moves, and why. Reviewed 2026-10-18. Visual identity: [DESIGN.md](../DESIGN.md).
Audit and skills review: [motion design review](research/motion-design-2026-10-18.md).

## Why motion

Kitden edits real settings files. Motion has one job: explain what changed and where. It never
decorates, never suggests work the page cannot see, and never shows a result before the server
has verified it. Calm beats bouncy: a tool that edits files must feel steady.

## Principles

1. **Truth first.** A success look (check, green button, flipped switch, new socket) appears
   only after the server says `verified`. A control under review shows a pending state, not
   the new state.
2. **No fake activity.** Nothing loops to suggest traffic, scanning or progress Kitden cannot
   observe. A gateway wire draws once when its connection first appears, then rests.
3. **Point, don't move.** To show where something is, light it (row glow, socket ping, lit
   rows). Layout moves only when the thing itself moves (a tile flying to its column).
4. **Errors stay.** An error is a callout that stays until the next action; the button that
   failed shakes once. No success animation can follow an error.
5. **Interruptible.** Every animation can be cut short; the true state is always the resting
   style, never something an animation must finish to reach.
6. **Transform and opacity.** Only these animate, with three small exceptions (the client
   counts row, a folded `<details>`, the sliding mark), all on one small element at a time.

## Tokens

Defined once in `style.css`; JavaScript reads `--spring` from there.

| Token | Value | Use |
| --- | --- | --- |
| Press | 80 ms in to 0.98, 260 ms `--spring` out | Buttons, tabs, filters, rail links, switches, tiles |
| `--t-fast` | 180 ms ease | Hover colour, label swaps, focus |
| `--t-panel` | 320 ms `--ease-drawer` | Drawer, scrim |
| Fold | 280 ms `--ease-out` | A `<details>` opening or closing |
| Glide | 300 ms `--spring` | The mark sliding between choices |
| Flight | 340 ms `--ease-drawer` | A shared tile between places |
| Status | 320–380 ms `--ease-in-out` | Socket morph (dot fill, words blur) |
| Success | check draws 320 ms, button stays green 450 ms | Applied, Undone |
| Error | 10 px shake, 360 ms | A failed Apply |
| Stagger | 45 ms between blocks, 18 ms between diff lines (14 at most) | First visit, diff |
| `--spring` | critically damped `linear()` spring, no overshoot; falls back to `--ease-out` | Everything the hand moves |

## Patterns

All helpers live in `src/kitden/web/static/js/motion.js`.

| Pattern | Helper | Where |
| --- | --- | --- |
| Place change cross-fade | `transition(change)` | Rail links, Back, a scope change off the Load map |
| Shared tile | `fly(node, name)` before `go()`, `land(twin, name)` while the new place draws | Overview count → Load map column |
| Sliding mark | `glide(box, active, key)` | Rail, Load map tabs, filters |
| Smooth `<details>` | `fold(details)` | File change in a review, gateway forms |
| Rolling number | `rollTo(holder, value)` | Rail counts |
| Socket morph | `morphSocket(node, state)` (parts.js) | Load map after Apply, Undo or a scope change |
| Resolved flag | `.flag.gone` | Load map after a verified change |
| Arrival | `.arrive` row glow + `.pulse` socket ping | Coming from a finding |
| First visit | `entrance(place, nodes)` | Every place, once |
| Pending switch | `.switch.pending` (thumb half-way) | Plugin switch while the preview loads |
| Applied | `.btn.primary.done` + drawn check | Review footer, after `verified` |
| Toast check | `toast(text, undo, { ok: true })` | Only for verified and undone |
| Route focus | `focusRoutes(clients, { wires, rows })` | Gateway diagram and lists, hover and keyboard |

## Conventions

- One motion per change. A change that morphs cells does not also cross-fade the page.
- A new control gets the press (`transform`), a hover colour and a visible focus ring; nothing else.
- Lists stagger, single things do not. Total stagger under 500 ms.
- Put the resting style in CSS and the animation in a class or keyframe, so a skipped animation
  still lands on the right look.
- Never read the true state from `transitionend` or `animationend`; use a timer or the data.
- New wording tests go in `tests/unit/test_page_words.py`; helper logic in `tests/frontend/motion.test.mjs`.

## Accessibility

- `prefers-reduced-motion: reduce` turns every animation and transform transition off (one
  rule at the end of `style.css`); `animate()` and `transition()` return early; folds and
  flights just switch.
- Keyboard opens and closes the panel instantly. Gateway routes are focusable and announce
  their state. Every control keeps `:focus-visible`.
- Live regions: the toast is `role="status"`; errors are `role="alert"`.

## Performance

- Checked with 39 MCP servers, 6 plugins and 3 findings on one page: no long task over 50 ms
  while moving between places or applying a change.
- Animate `transform` and `opacity`; a sliding mark animates its own width and height only.
- No library, no bundler, nothing loaded at run time.

## Examples

Open a place with a shared tile:

```js
fly(tile, `client-${clientId}`);   // on the old place, right before go()
go("map", { kind });
// on the new place, while it draws:
land(columnTile, `client-${columnId}`);
```

A group with a sliding mark (the group needs `position: relative`):

```js
glide(box, box.querySelector('[aria-selected="true"]'), "map-tabs");
```

A smooth `<details>`:

```js
details.append(summary, content);
main.append(fold(details));
```
