# Kitden design

How the page looks and moves. `src/kitden/web/static/style.css` holds the values; this file says why.
Quiet Den + Graphite, light and dark.

## Identity

Kitden is a calm local home for a developer's coding tools. The mark is a soft asymmetric house with an off-center arched door. The wordmark is Kitden in the existing system sans, medium-bold, with slightly tight tracking.

Canonical asset: `src/kitden/web/static/brand/kitden.svg`. The sidebar and favicon reuse this file. It contains no third-party mark.

**The house is always #C85835.** Never recolor it for dark mode, use a white fallback, apply opacity, or add gradients. Use the same silhouette in both themes. Keep clear space around it. The sidebar renders at 30 px; favicon has a 64-unit viewBox and a simple silhouette for small sizes.

## Color roles

| Role | Light | Dark |
| --- | --- | --- |
| Brand mark | #C85835 | #C85835 |
| Canvas | #F5F6F8 | #171A20 |
| Panel | #FFFFFF | #20242C |
| Raised panel | #FFFFFF | #282D36 |
| Inset | #F0F2F5 | #12151A |
| Main text | #161A21 | #F2F3F5 |
| Secondary text | #464D5B | #C1C6CF |
| Muted text | #646B79 | #A5ADBA |
| Action fill | #B34B2D | #B34B2D |
| Action text | #FFFFFF | #FFFFFF |
| Action hover | #9F4025 | #9F4025 |
| Success fill (Applied button) | #177A42 | #47C27A |
| Success text | #FFFFFF | #0B1A12 |
| Added diff text (`--diff-add`) | #136A39 | #47C27A |
| Removed diff text (`--diff-del`) | #B23434 | #F07070 |
| Accent text / links | #A44226 | #F09A7C |
| Selection surface | #F6E8E2 | #382A27 |
| Focus | #B34B2D | #F09A7C |

The brand mark is fixed; functional shades adapt for text contrast. Text on the action and success fills, and diff text on its tint and on the drawer, keeps at least 4.5:1 in both themes (WCAG 2.2 AA, checked 2026-10-19); `tests/unit/test_contrast.py` holds the line. Do not use the logo color for every small label. Success stays green, warnings amber and errors red, paired with text/shape. Gateway routes use the accent family and square state indicators. Vendor marks must retain their own permitted colors when verified; Claude, Cursor and Codex use local vendor icons (see `src/kitden/web/static/brand/clients/ATTRIBUTION.md`). Neutral monograms are used only for unknown clients or failed image loads.

## Client marks

Every client mark is the same rounded tile (24 px, radius 6, raised-panel background, thin border), so the row of clients reads as one family. The Codex and Cursor icons fill the tile and switch to the vendor's own dark version in the dark theme; the Claude glyph sits inside it with 4 px padding and works on both. The tile grows to 28 px where the client is the headline: the Clients card on Overview and the title of a detail panel. The Gateway route diagram draws the same tile in SVG. Do not tint, recolor or shrink a vendor icon to show a state; state lives in the badge next to it.

## Components

Preserve the compact information layout. Use restrained neutral panels, fine borders and the existing 6–10 px corner radii. Primary actions use the action fill. Selected navigation uses a tinted background, accent text and a brand-colored inset bar. Tabs and selected filters use the same accent family. Tables, drawer, forms, loading, toast and empty states inherit shared tokens; no page-specific blue accents.

On Overview, an option ("Can improve") is a quiet card: `.issue.suggestion` has no warning border and a plain button, not the primary one. A card with no button (a file Kitden could not read) keeps its title and sentence in the wide column.

A row that opens Details ends with a quiet › and the hidden words "Open details" (`opens()` in `parts.js`). The chevron turns accent on hover and keyboard focus; it does not move. The search box names what it searches: "Search your setup and marketplaces…". In `kitden demo` a quiet "Demo" flag (`.flag.info`) follows the wordmark; its hover text says the setup is a sample in a temporary folder. The page reads `/api/about` once to know.

A Details footer button never grows past the panel: long words end in "…", and the whole label stays in its hover text. When one client has two Remove buttons for the same scope, each names its folder by the last two parts: "Remove from Codex (.agents/skills)…".

The Library has one row per item and one column per client found on this computer.

| Part | Look |
| --- | --- |
| Row, line one | The name in mono, then quiet muted text: the category, and the source only when two rows share a name. The quiet text gives way first when the line is tight. The › comes last. |
| Row, line two | Flags first, then what it does, in muted text, one line, cut with "…". With no description the flags have the line to themselves; a row with neither has one line. |
| Cell state | A dot and a word. "Via Claude Code" is an empty gray ring, like Off: Cursor does not have it yet, and loads it through Claude Code once Claude Code has it. "Has its skills" (the client has every skill in the plugin, copied here or from another plugin) is a filled green dot, like Loads. On Instructions every cell that has the file says "Has it" (a filled green dot), never "Loads": commands and agents run on demand; Details says when each client reads it. On plugins and skills, a dash says why in its hover text. |
| Cell button | A small outlined button in the accent family ("+ Add", "+ Add skills", "+ Add the plugin") in place of a state. It opens the review for that one client; the rest of the row opens Details. |
| Column head | The client's tile and name, and a small "−" in quiet gray that hides the column; it darkens on hover and keyboard focus. The last shown column has none. |
| Hidden line | One quiet line above the table: "Hidden: Cursor · Show". Show brings every column back. |
| Group line | With All: "Installed", then "New", each on a quiet band. |
| Instruction file Details | Under each file's path, when the client reads it, then its first 12 lines in a quiet mono block on the inset color (common secret shapes hidden, values that span lines and key blocks too, each line cut at 200 characters). The badge says "Has it", or "In a project" for another project's file; never "Loads" or "Not loaded". With no project picked only global files show lines; a project's files show theirs when that project is picked. Agents asking through Kitden's MCP server get no file lines: they stay on the local page. |
| Add missing | In a project, a small plain "Add missing…" in the toolbar (not on Instructions, where Kitden adds nothing). Its review lists what each client lacks as checkboxes, one group per client; each line says where it goes. An add that would make a duplicate (a name in another case, or a skill another client would load twice) starts unchecked and says why. A change previews again; with none checked, Apply waits. Names loaded from another source are listed under "Not the same; not touched". |

Every pressable area is at least 24 px tall and wide (WCAG 2.2 AA target size, checked 2026-10-19). The plugin switch keeps its 34 x 20 track inside a 24 px button, and a client checkbox is pressed through its 24 px label.

The Gateway page lists the Kitden gateway first, then any registered gateway (Obot, MetaMCP). Its rows show a name and flags; the command and address stay in Details.

| Part | Look |
| --- | --- |
| Kitden gateway card | The kicker "Kitden gateway · On this Mac", the route diagram (a wire to each client whose `kitden` entry is on), then "In the gateway · N": a name, a Local or Remote flag, a quiet "12 tools" when Kitden knows its tools, an Off flag where it is off, and Details. Its Details, and an MCP server's Details in the Library, show the same count once; a server outside the gateway shows none. A client without the entry gets a quiet line, "Codex does not use it yet.", and "Set up in Codex…". |
| Tool switches | In the Details of a server in the gateway: "Tools · {project folder}" or "Tools · All projects", then "Whole server" first and one row with a switch per tool (name in mono, description cut at two lines). A project row that differs shows what it would follow without its own setting, "Differs from all projects" or "Differs from {project around it}", and a "Use all projects" or "Use {project}" button. |
| A switch changes | It rests half-way while the preview loads, then opens the review. The switch flips only after `verified`: Details stays open and is drawn again in the new state, the thumb slides once (`.switch.flipped`), focus is on that switch, and the toast has Undo. Cancel, or a refused preview (a callout says why), also comes back to Details, with focus on the control you pressed (for "Use …", that button). |
| Move choice | "Move into the gateway…" asks only when there is a choice: "Move into the Kitden gateway…" first (primary), a registered gateway second (plain). With one choice the review opens at once. A local server can go only into the Kitden gateway. |

Keep existing system fonts and motion, keyboard focus, and reduced-motion support. Search and project controls show a visible focus outline. Preserve explicit Apply, backup and Undo semantics. Brand color must not imply success or a safe action.

## Motion


Kitden edits real settings files. Motion has one job: explain what changed and where. It never
decorates, never suggests work the page cannot see, and never shows a result before the server
has verified it. Calm beats bouncy: a tool that edits files must feel steady.

### Principles

1. **Truth first.** A success look (check, green button, flipped switch, new socket) appears
   only after the server says `verified`. A control under review shows a pending state, not
   the new state.
2. **No fake activity.** Nothing loops to suggest traffic, scanning or progress Kitden cannot
   observe. A gateway wire draws once when its connection first appears, then rests.
3. **Point, don't move.** To show where something is, light it (row glow, socket ping, lit
   rows). Layout moves only when the thing itself moves (a tile flying to its column).
4. **Errors stay.** An error is a callout that stays until the next action; focus goes back to
   the button that failed. No success animation can follow an error.
5. **Interruptible.** Every animation can be cut short; the true state is always the resting
   style, never something an animation must finish to reach.
6. **Transform and opacity.** Only these animate, with three small exceptions (the client
   counts row, a folded `<details>`, the sliding mark), all on one small element at a time.

### Tokens

Defined once in `style.css`; JavaScript reads `--spring` from there.

| Token | Value | Use |
| --- | --- | --- |
| Press | 80 ms in to 0.98, 260 ms `--spring` out | Buttons, tabs, filters, rail links, switches, tiles |
| `--t-fast` | 180 ms ease | Hover colour, word fades, focus |
| `--t-panel` | 240 ms `--ease-drawer` | Drawer, scrim |
| Fold | 280 ms `--ease-out` | A `<details>` opening or closing |
| Glide | 300 ms `--spring` | The mark sliding between choices |
| Flight | 340 ms `--ease-drawer` | A shared tile between places |
| Status | 320–380 ms `--ease-in-out` | Socket morph (dot fill, words fade) |
| Success | check draws 320 ms, never delays the next action | Applied, Undone |
| Stagger | 45 ms between blocks | First visit |
| Busy | spinner after 150 ms, in the button's own place | A button whose work takes a moment |
| Scan line | shows after 400 ms, 1.6 s calm sweep | A rescan that takes a while |
| Start line | shows after 1 s; fills from the left as each step of the first scan ends, then fills up and goes; a quiet note under its right end says "Reading Codex and Cursor…" or "Still checking …" | Starting Kitden |
| `--spring` | critically damped `linear()` spring, no overshoot; falls back to `--ease-out` | Everything the hand moves |

### Patterns

All helpers live in `src/kitden/web/static/js/motion.js`.

| Pattern | Helper | Where |
| --- | --- | --- |
| Place change | `transition(change, "place-change")`: only the page goes (120 ms) and the new one rises 6 px (260 ms); the rail and top bar stay still | Rail links, Back; the Library's rows are read first (up to 300 ms) |
| Shared tile | `fly(node, name)` before `go()`, `land(twin, name)` while the new place draws | Overview count → Library column |
| Sliding mark | `glide(box, active, key)` | Rail, Library tabs, the show choice |
| Ready, then swap | `choose(params)` (library.js): read the rows first; over 300 ms the old list dims (`.table-scroll.waiting`), never a skeleton | Library tabs, Installed / New / All, category, Needs attention |
| List settle | `snapshotRows()` before a redraw, `settleRows()` after: rows that stay slide from their old place (260 ms `--spring`), new rows rise 4 px (200 ms, 20 ms apart, first 12) | Library filters and search |
| Tab slide | in `settleRows()`: another tab's list slides in 8 px from that tab's side (220 ms) | Library kind tabs |
| Smooth `<details>` | `fold(details)` | File change in a review, gateway forms |
| Rolling number | `rollTo(holder, value)` | Rail counts, Library tab counts |
| Socket morph | `morphSocket(node, state)` (parts.js) | Library after Apply, Undo or a scope change |
| Resolved flag | `.flag.gone` | Library after a verified change |
| Arrival | `.arrive` row glow + `.pulse` socket ping | Coming from a finding |
| Add lands | `.socket.pulse` on a cell that held a button | Library after a verified add |
| First visit | `entrance(place, nodes)` | Every place, once |
| Pending switch | `.switch.pending` (thumb half-way) | Plugin and tool switches while the preview loads |
| Flipped switch | `.switch.flipped`: the thumb slides once into the verified state | Tool switch, after Apply or Undo is verified |
| Busy button | `busyWhile(button, work)` (dom.js); `button()` uses it | Every button that waits on the server; quick work never shows it |
| Step count | `change_progress` events → "Applying 2 of 5" + `.btn .meter` | Apply of a change with several steps, from the server's own count |
| Applied | `.btn.primary.done` (green at once, full strength) + drawn check | Review footer, after `verified` |
| Toast check | `toast(text, undo, { ok: true })` | Only for verified and undone |
| Route focus | `focusRoutes(clients, { wires, rows })` | Gateway diagram and lists, hover and keyboard |

### Conventions

- One motion per change. A change that morphs cells does not also cross-fade the page.
- A new control gets the press (`transform`), a hover colour and a visible focus ring; nothing else.
- Lists stagger, single things do not. Total stagger under 500 ms.
- A drawer has one motion: it slides in. Its blocks and diff lines are there at once.
- Put the resting style in CSS and the animation in a class or keyframe, so a skipped animation
  still lands on the right look.
- Never read the true state from `transitionend` or `animationend`; use a timer or the data.
- New wording tests go in `tests/unit/test_page_words.py`; helper logic in a node test in `tests/frontend/` (all run with `node --test tests/frontend/*.test.mjs`).

### Accessibility

- `prefers-reduced-motion: reduce` turns every animation and transform transition off (one
  rule at the end of `style.css`); `animate()` and `transition()` return early; folds,
  flights and socket morphs just switch.
- Keyboard opens and closes the panel instantly. Gateway routes are focusable and announce
  their state. Every control keeps `:focus-visible`.
- A redraw keeps keyboard focus: a tab, filter button, menu or row with a `data-focus` key (or
  a row key) gets focus back. Arrow keys, Home and End move between tabs and select (`tabKeys()`
  in `dom.js`). The review's Tab loop includes its "Show file change" summary. After a page's
  Retry, focus goes to the new Retry if the read failed again, else to the page's first control.
- Live regions: the toast is `role="status"`; errors are `role="alert"`.

### Performance

- Checked with 39 MCP servers, 6 plugins and 3 findings on one page: no long task over 50 ms
  while moving between places or applying a change.
- Animate `transform` and `opacity`; a sliding mark animates its own width and height only.
- No library, no bundler, nothing loaded at run time.

### Examples

Open a place with a shared tile:

```js
fly(tile, `client-${clientId}`);   // on the old place, right before go()
go("library", { kind });
// on the new place, while it draws:
land(columnTile, `client-${columnId}`);
```

A group with a sliding mark (the group needs `position: relative`):

```js
glide(box, box.querySelector('[aria-selected="true"]'), "library-tabs");
```

A smooth `<details>`:

```js
details.append(summary, content);
main.append(fold(details));
```
