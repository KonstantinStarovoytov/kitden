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

On Overview, an option ("Can improve") is a quiet card: `.issue.suggestion` has no warning border and a plain button, not the primary one. A card with no button (a file Kitden could not read) keeps its title and sentence in the wide column. On the Clients card a client Kitden could not read says "Could not read", never "Not installed".

Overview's notes are grouped by item: one row per name with the mark of every client it is about, and each note as a quiet flag. Flags that do not fit wrap under the name. "Same name, another source" says two entries differ; "Set up in more than one client" says the same one is set up twice.

A row that opens Details ends with a quiet › and the hidden words "Open details" (`opens()` in `parts.js`). The chevron turns accent on hover and keyboard focus; it does not move. The search box names what it searches: "Search your setup and marketplaces…". The project picker's first choice is "All projects": what applies in every project. A picked project that leaves the list stays picked (the picker says "No longer on the list"), while Overview, Library and Gateway say "This project is no longer on the list." and read nothing for it. A review names its scope in the title ("… for all projects", "… in website"; see Review below) and an add, with All projects picked, in the lede too. A gateway's entry and a server put back in a client are adds for all projects too. In `kitden demo` a quiet "Demo" flag (`.flag.info`) follows the wordmark; its hover text says the setup is a sample in a temporary folder. The page reads `/api/about` once to know.

The address keeps the project and the selected item (`sel=<kind>:<name>`, as in `#library?kind=skill&project=a&sel=skill%3Atidy`) on every page, so Back and a copied link return to them. Arriving with a selection (an Overview card or note, Back, Forward or a link), the Library opens that row's Details once, and the Gateway opens the selected server's Details once, in the Kitden gateway's own panel for a server it holds; a redraw does not open it again. A rail link opens its place fresh. An arrival never opens over a panel that is open, and a row or Details the person opens first wins.

A Details footer button never grows past the panel: long words end in "…", and the whole label stays in its hover text. A Remove names every client it reaches: "Remove from Codex and Cursor…" for a skill in a folder both read, but not a client that keeps another copy of its own; a switch names only its own client. When one client has two Remove buttons for the same scope, each names its folder by the last two parts: "Remove from Codex and Cursor (.agents/skills)…".

Details answers in the same order for every kind (`DETAILS_ORDER` in `details.js`).

| Part | Look |
| --- | --- |
| Order | The header: the kind, the name and where it is available. Then the body: warnings, what it is (a marketplace entry's description), Why, what each client loads, the tools of a server in the Kitden gateway, the secret note, what comes next (what the lead action changes, why nothing can be done, when so, and the gateway notes), the links, and Technical details last. The lead action and More stay in the footer. |
| Why | One or two quiet lines before the client sections. The first says where each client loads it from, in the route and scope words: "Codex and Cursor load it from all projects.", "Claude Code loads it from all projects; Cursor through Claude Code's folder.", "… load it through the Kitden gateway.". The second says what decides, in short sentences. First one skill folder several clients read ("One folder, read by Codex and Cursor."), or one definition over another of the same client: "In Claude Code, the one from this project overrides the one from all projects.", "In Codex, the ones from this project and from all projects are merged.", for a server in the Kitden gateway "Claude Code uses this project's switch for files in the Kitden gateway." (or "In the Kitden gateway, this project's switch for files is off."), and "In Claude Code, two of them come from a plugin; only one loads." when nothing tells them apart. Then, with All projects picked, "It is in 2 projects; it loads only there." or "It is also in 1 project.". Then "Turned off in Codex." for a client that loads no other copy, or "Turned off in api." for another project's copy. A fact the Why says is not said again under a definition; a copy that is off while its client loads another one keeps its own line. An unknown state keeps its own reason there ("Its on/off state is kept in your Claude account, not on this Mac."), and the Why adds nothing for it. An instruction file has no Why: its own lines say when each client reads it. A section title names only a client's folder ("All projects · through Claude Code's folder"), never a shared one. |
| Affects | One quiet line after what each client loads, before the links, only when something leads, naming what the lead action changes before any action: "Changes Codex and Cursor (Cursor reads Codex's folder). All projects." The place is "All projects.", "In this project.", "In website." for another project's definition, or "All projects except this one." when it names one client and this project's own definition of that client wins over it. A move names the clients whose entries move and every client that reaches that gateway already (for the Kitden gateway, each client whose kitden entry is on, also before it holds a server); with two gateways to choose from, only those both reach. An add that asks where says "You choose this project or all projects next." and names only what both choices reach; a project's own skill adds "In this project.". For "Manage tools" it names the clients that load the server through the Kitden gateway. |
| Links | One row of quiet ghost buttons after what comes next: "Compare across clients" (the item's row in the Library) and "Manage tools" (a server in the Kitden gateway, on the Gateway page). Never a link to the page shown. A link closes the panel, keeps the project and the item, and opens the item's Details there. The Kitden gateway's own panel of a server links to the Library too, while some client loads the server through it (else the Library has no row). |
| Lead | The footer's primary button: a warning's fix first; then, for a server the Kitden gateway already holds, "Manage tools" (Move waits under More); then "Move into the gateway…"; then a lone switch or Remove; then the first add. A lone Remove gives way to an add, so the add the cell offers stays in sight. |
| Cancel | Cancel in any review opened from Details (or from the Kitden gateway's own panel of a held server), also after the Move or Add choice, goes back to that panel, drawn as it was (no new read), with focus on the control you pressed, or on More when that control waits under More again. A refused preview comes back the same way, with a callout first that says why. A tool switch comes back the same way, with Details read again. A review that answers after you left that panel does not go back to another one. Escape still closes the panel. |
| Technical details | Folded at the end, with the look of "Show file change". One part per file, file key, command and first lines, titled with every client that reads it and the file words: "Codex and Cursor · Global settings", "Project website", "… · via Claude Code"; a server in the Kitden gateway is the gateway's own entry, "Kitden gateway · Global settings". Then the path (the whole path in its hover text), the file key and the command in mono, and an instruction file's first lines. Left out when there is nothing to show. What a plugin's MCP servers run joins the fold; the list above says only their names. Details of a plugin or skill not set up here fold their source, pinned version, commands and folder the same way ("Source", "Pinned to", "MCP server files", "Skill folder"). |

A review leads with the outcome, in this order.

| Part | Look |
| --- | --- |
| Title | One sentence: the change, the clients it reaches (the ones Details' Affects line names) and where the steps go: "Remove neon from Codex in website", "Remove linter from Claude Code and Cursor for all projects" (Cursor loads Claude Code's plugins), and "Turn off superpowers in Claude Code for all projects except website" when the project picked at the top has its own definition that wins there for every client the change reaches. The review checks this for every client; Details says "All projects except this one." only when its Affects line names one client, so the two can differ for a change that reaches several. Steps in more than one place name no place. A title that names its place already (a tool rule, strict mode, Add missing) or has none (an update of "show my setup", a server leaving the Kitden gateway, secrets to the Keychain) gets no scope words. The toast after Apply and the Changes page say the same, also after a restart. |
| Lede | Quiet, in order: "Adds for all projects." for an add with All projects picked whose steps go to all projects (or that does not say where), or "Other projects are unchanged." only when every step is in one project's files (or is a Kitden gateway rule for it), no other known project lies inside that folder or around it, and no step runs a client's plugin command (`claude plugin …`, `codex plugin …` also work on the plugin cache every project shares; Kitden checks only the settings file). An MCP command (`claude mcp remove -s local`) is judged by the file it edits; then "Nothing is written until you press Apply. A backup is kept."; then what Undo cannot bring back, when Kitden knows: "Undo installs it again; its saved options are not brought back." for a removed Claude Code plugin, "After Undo, files/TOKEN in your Keychain keeps its new value." for a Keychain item that was there before ("… keep their new values" for several). It never promises Undo for every change. |
| Body | The After chips, then the folded file change, as before. A chip keeps only its own note (why Cursor gains or loses a plugin); the Undo limit is said once, in the lede. |

The Library has one row per item and one column per client found on this computer.

| Part | Look |
| --- | --- |
| Row, line one | The name in mono, then quiet muted text: the category, and the source only when two rows share a name. The quiet text gives way first when the line is tight. The › comes last. |
| Row, line two | Flags first, then what it does, in muted text, one line, cut with "…". With no description the flags have the line to themselves; a row with neither has one line. |
| Cell state | A dot and a word. "Unknown" is a dashed amber ring: Kitden could not read where the state comes from, whether a whole client ("Could not read Codex." in the hover text), a file, or a place it cannot see, such as your Claude account. It never means missing. "Needs review" (amber ring, small dot) is a same-name item from another source: another command, address or skill files; its hover says "Same name, another source." In a row with a Needs review cell no cell offers "+ Add"; an empty one says "Same name, another source: decide first." A cell kept from the last good read of a file that now fails keeps its state with a dashed dot (so does a project's item while the file that lists the project fails: ~/.claude.json for Claude Code, config.toml for Codex), and its row's first flag says "From the last good read at 14:02"; Kitden keeps that read in memory only, while the page runs. The rows a client Kitden could not read had at its last good read stay on the page. Its Details adds one quiet line with the same words, and a change to it is refused: "Kitden can't change this until it reads .claude.json again." "Via Claude Code" is an empty gray ring, like Off: Cursor does not have it yet, and loads it through Claude Code once Claude Code has it. "Has its skills" (the client has every skill in the plugin, copied here or from another plugin) is a filled green dot, like Available. On Instructions a cell that has the file says "Available", as on every tab; Details says when each client reads it. On plugins and skills, a dash says why in its hover text. |
| Scope word | In a project every cell with an item also says where it applies: "· all projects", "· this project" or "· project override" (a project item that wins over an all-projects one); with All projects picked, none. The hover text says the scope word in full, then how the client gets the item ("through Claude Code's folder", "from a plugin", "through the Kitden gateway", "from the Desktop app"), then the reason, as in "Project override. Through Codex's folder". The route is never beside the state. |
| Cell button | A small outlined button in the accent family ("+ Add", "+ Add skills", "+ Add the plugin") in place of a state. It opens the review for that one client; the rest of the row opens Details, which offers the same add. In a project, a skill only that project has offers "+ Add" for the clients that lack it; it adds into that project with no choice. A server only that project has keeps "—", saying "Kitden adds MCP servers for all projects only." In a project, a quiet line above the table says where an Add goes. |
| Column head | The client's tile and name, and a small "−" in quiet gray that hides the column; it darkens on hover and keyboard focus. There is none when no other column of a client Kitden could read would stay. A client Kitden could not read keeps its column, with "Could not read" under its name. |
| Read problem | One quiet line above the table per file that failed on its first read: "Could not read mcp.json; its items are not shown." A file inside a project shows only when that project is picked (the deepest project that holds it; the home folder does not count as one). No "+ Add" writes into a settings file Kitden cannot read: that cell says "Unknown", and its hover text says "Can't add while mcp.json can't be read." Adds into the client's other files stay; an add that asks "this project or all projects" stays while one of its places reads well. |
| Hidden line | One quiet line above the table: "Hidden: Cursor · Show". Show brings every column back. |
| Group line | With All: "Installed", then "New", each on a quiet band. |
| Instruction file Details | Each file's line says when the client reads it. Its path and its first 12 lines sit under Technical details, the lines in a quiet mono block on the inset color (common secret shapes hidden, values that span lines and key blocks too, each line cut at 200 characters). The badge says "Available", or "In a project" for another project's file; never "Not loaded". With All projects picked only the files for all projects show lines; a project's files show theirs when that project is picked. Agents asking through Kitden's MCP server get no file lines: they stay on the local page. |
| Add missing | In a project, a small plain "Add missing…" in the toolbar (not on Instructions, where Kitden adds nothing). Its review lists what each client lacks as checkboxes, one group per client; each line says where it goes. An add that would make a duplicate (a name in another case, or a skill another client would load twice) starts unchecked and says why. A change previews again; with none checked, Apply waits. Names loaded from another source are listed under "Not the same; not touched". |

Every pressable area is at least 24 px tall and wide (WCAG 2.2 AA target size, checked 2026-10-19). The plugin switch keeps its 34 x 20 track inside a 24 px button, and a client checkbox is pressed through its 24 px label.

The Gateway page lists the Kitden gateway first, then any registered gateway (Obot, MetaMCP). Its rows show a name and flags; the command and address stay in Details.

| Part | Look |
| --- | --- |
| Kitden gateway card | The kicker "Kitden gateway · On this Mac", the route diagram (a wire to each client whose `kitden` entry is on), then "In the gateway · N": a name, a Local or Remote flag, a quiet "12 tools" when Kitden knows its tools, an Off flag where it is off, and Details. Its Details, and an MCP server's Details in the Library, show the same count once; a server outside the gateway shows none. A client without the entry gets a quiet line, "Codex does not use it yet.", and "Set up in Codex…". |
| Tool switches | In the Details of a server in the gateway: "Tools · {project folder}" or "Tools · All projects", then "Whole server" first and one row with a switch per tool (name in mono, description cut at two lines). A project row that differs shows what it would follow without its own setting, "Differs from all projects" or "Differs from {project around it}", and a "Use all projects" or "Use {project}" button. Picking another project, also by Back or an edited address, closes the panel, cancels an open review and drops one still being prepared, except while a change is being written, so a switch never acts on a project it does not name. |
| A switch changes | It rests half-way while the preview loads, then opens the review. The switch flips only after `verified`: Details stays open and is drawn again in the new state, the thumb slides once (`.switch.flipped`), focus is on that switch, and the toast has Undo. Cancel and a refused preview come back as Details' Cancel row says (for "Use …", focus on that button). |
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
