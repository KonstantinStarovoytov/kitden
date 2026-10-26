# Phase 6B: Library actions, add panel, Instructions and the List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Library as in the mockup:
- a plugin or skill can be dragged onto a client;
- a link's × removes or turns off;
- "+ Add" opens the shared add panel for plugins and skills;
- the Instructions tab draws its own map of files and imports;
- the List becomes the mockup's two-tab list, with Installed | Differences and "Add missing plugins and skills…";
- the leftovers noted after Phase 6A close.

**Architecture:**
- **Drag engine.** The Gateway's engine (`startDrag`, the 5 px start, capture, Escape and blur, the swallowed click, `covered`, `flyGhost`) moves from `gateway-drag.js` into a shared `map-drag.js`. Each page keeps its own `DRAGS` hooks and its own map state.
- **Add panel.** gateway-add.js's panel moves into a shared `add-panel.js`, which takes a page config: rows, words, a pill, a body builder and a drag. The Gateway and the Library each pass their own config.
- **Instructions.** A new backend reader, `views/imports.py`, reads Claude Code's `@` imports. A new view, `views/instructions_map.py`, feeds the Instructions map.
- **List.** The List is rebuilt from the map's data shape, with `/api/library` keeping its cells, adds and filters.

**Tech Stack:** Python 3.13 + Starlette, pytest on sandbox homes; plain ES modules, one CSS file, node's test runner with each file's fake DOM.

**Spec:**
- **Master plan** `docs/superpowers/plans/2026-10-24-mockup-alignment.md`:
  - Phase 6, Tasks 6.3–6.6;
  - the note "Carried from Phase 3" ("In preview" on the Library's add choice and the `offer.js` add forms);
  - the "Notes from Phase 6A" list.
- **Owner decisions:** D14, D23–D27.
- **`docs/superpowers/specs/2026-10-23-map-pages-design.md`:**
  - Part 5: 5.2 tabs, 5.4 List, 5.5 actions, 5.6 add panel;
  - Part 6: 6.1 Instructions.
- **`docs/mockup/library-notes.md`:** §1 hint line, §4 drags, §5 link ×, §6 Instructions, §7 List, §8 tray words, §11.
- **Frames** in `design/kitden.pen`:
  - `L3 · Library · list`;
  - `L4 · Library · add from a marketplace`;
  - `I1 · Library · Instructions`;
  - `M7·6`, `M8·1`–`M8·5`.

## Decisions

### Drag a plugin or skill onto a client (6.3, library-notes §4)
- **What drags.** Plugin cards and skill rows on the map drag, and so do rows of the add panel. Clients, inside rows, hooks, files and imports do not drag.
- **The press and the tip.**
  - Start after 5 px. The tip says "Drop on a client".
  - Over a client the page can add to:
    - the client lights (`.drop`);
    - a dashed accent wire runs from the client to the block;
    - the tip says "Add to <Client>".
  - Refused before the drop: the client does not light, and the tip says the reason. On release the block goes home (220 OUT3) and the client shakes (380).
- **Refusals, checked in order:**
  1. "Cursor gets plugins through Claude Code" (a plugin onto Cursor, D26).
  2. "Already in <Client>" (the client has it on, or loads it through Claude Code).
  3. "Already in preview" (its add for that client is in the tray).
  4. "<Client> cannot get <name>" (no route).
- **Skills and Cursor.** A skill may be dropped on Cursor when the skill catalog gives Cursor a route.
- **What a drop adds.**
  - It adds one row for that client only: `plugin.install` or `skill.install`, for all projects. The hint line says "+ adds it for all projects".
  - With a project picked, the row's review names the scope, as today's "+ Add" does. A drop never asks.
- **While the row waits.** A dashed accent link runs from the client to the item, and the item's meta says "Preview · <Client>". A press on that link or on the item takes the row out.

### Link × (6.4, library-notes §5)
- **Client → plugin.**
  - The × says "Remove <name> from <Client>" and adds `plugin.remove` for that client's item.
  - Claude Code's review keeps today's note: "Undo installs it again; its saved options are not brought back."
  - Cursor's plugin links have no ×: Cursor removes plugins only in its own app (D26). Its Connection Details say so, with today's Cursor hint.
- **Client → skill.**
  - Claude Code and Codex: the × says "Turn off <name> in <Client>" and adds the same `skill.rule` row as Details' "Turn off for all projects…" for that client.
  - Cursor: the × says "Remove <name> from Cursor" (`skill.remove`), and only for Cursor's own skill folder.
- **Preview links:** the × says "Take it out of the preview" and takes the row out.
- **Read only:**
  - plugin → inside item (D25);
  - faint Cursor-through-Claude-Code lines;
  - Unknown clients;
  - all Instructions links.

### The add panel for plugins and skills (5.6, frame L4)
- **One shared panel** (`add-panel.js`). The Library's config:
  - title "Add a plugin or skill";
  - search "Search the marketplaces…";
  - pill "All · Plugins · Skills" (a real filter on kind);
  - rows grouped by marketplace in name order, with the `store` icon;
  - footer "Click to preview, or drag onto a client.";
  - a quiet "Add a marketplace…" at the end, which opens today's `marketplaceForm`.
- **Data:** a new `GET /api/library-offers`, built from `catalog()` and `skill_catalog()`. A row is `{id, kind, name, marketplace, count?, routes, installed, refusal}`. `count` is what Kitden read inside a plugin. There are no paths.
- **Row small line:** "Plugin · <n> skills" (or "· <n> items" when it holds more than skills), or "Skill".
- **Row status, first match wins:**
  1. "Added" (added by an Apply since the page loaded);
  2. "In every client" (every client with a route has it);
  3. the refusal reason;
  4. "In preview";
  5. empty.
- **A click** adds the item for all projects to every client that has a route and lacks it, as one tray row (today's multi-client `plugin.install` / `skill.install` body). A second click takes it out.
- **A drag** onto a client works as in the drag section above, for that client only.
- **A row that waits** is drawn on the map as a preview card in its marketplace group. A plugin no client has gets a new card. Its dashed links run to each target client, and its meta says "Preview · for all projects" or "Preview · <Client>".
- **Words.** The tray and review words are today's for these actions, with no new title.

### Instructions (6.5, spec 6.1, frames I1 and M8·4–M8·5)
- **Columns:** "Clients", "Files", "Pulls in".
- **Files.**
  - Grouped "All projects" and "Only this project · <folder>": one block per file path, with the clients that read it.
  - The block name is the file's name (`CLAUDE.md`, `AGENTS.md`); a Cursor rules folder folds into one block, ".cursor/rules", with "Cursor · <n> rules".
  - The meta reads "<Client> · this project" or "<Client> · all projects", or "<Client> · <n> import(s)" when it imports.
- **Imports.**
  - Claude Code's `@path` imports, read from its CLAUDE.md files (CLAUDE.md, CLAUDE.local.md, `.claude/CLAUDE.md`).
  - A path is relative to the file, and `~` works.
  - Imports nest up to four hops. Code spans and fenced blocks are skipped. A loop stops at the first repeat.
  - An import outside the project says "Claude Code may ask before it reads this."
  - Codex and Cursor files have no import links (D27).
  - Check these facts in code.claude.com/docs/en/memory and date them.
- **AGENTS.md.** Claude Code reads AGENTS.md when a project has no CLAUDE.md; only if the docs say so, with the version and the date. Then "Read by" names Claude Code too, through no import.
- **File Details:**
  - kicker "Instruction file";
  - facts "Read by", "Through" (for example "CLAUDE.md for Claude Code") and "Size" ("42 lines");
  - say line "Kitden only reads this file." plus "It brings in <n> more." or "It imports nothing.";
  - Technical details: the path and the first lines (today's `preview`, secrets redacted).
- **Imported file Details:** kicker "Imported file", "Brought in by <files>", and "Kitden only reads it."
- **Read only.** Nothing on this tab enters the tray. Imports reach the page only, never the MCP server's answers.

### The List (6.6, spec 5.4, frame L3)
- **Tabs:** "Plugins and skills" | "Instructions", as on the Map.
  - MCP servers live on the Gateway. Old `kind=mcp_server` links already land there.
  - Hooks are rows under "Your settings".
  - Marketplaces are the group rows. A marketplace row opens its caption Details.
- **Plugins and skills rows:**
  - one group row per source;
  - one row per plugin ("Plugin · <n> items"), folding child rows for its parts (kind word "Skill" or "Command");
  - one row per skill and hook.
- **Columns:** one per client.
- **Cells:** "On", "Off", "Via Claude Code", "+ Add", or nothing, from today's `/api/library` cells.
- **Filters:**
  - Installed | Differences (hash `show=diff`). "New" and "All" give way to the add panel, and so does the category filter.
  - "Needs attention · N" stays, because Overview links use it.
  - Differences shows the rows whose cells differ between the found clients: On next to empty, Off next to On, Needs review, Unknown, or a cell kept from the last good read. A plugin row differs when any child row differs.
- **"Add missing plugins and skills…"** opens today's review in its groups. It works in a project and, new here, in All projects: the item one client has for all projects and another lacks. "Nothing is missing." when there is nothing.
- **Instructions List:** one row per file, the clients as columns. Cells say "Reads it" or nothing. A press opens the file's Details.
- **Hint line on the List:** "One row per item, one column per client. Right opens a plugin, Enter opens Details."
- **Keyboard:** Up and Down move between rows, Right opens a plugin, Left folds it, and Enter opens Details.

### Leftovers from Phase 6A (master plan notes)
- **"Use the shared rule…"** In a project where a Claude Code skill's state comes from the project's own rule, Details offer it: one `skill.rule` with `off: false`.
- **The project checklist** marks a row "Already off there" when that project already turns the skill off. The row cannot be ticked.
- **A Codex skill in one project only** gets "Turn off this copy in Codex…" (a `skill.rule` for all projects, keyed by that copy's path).
- **`here` per client.** `here` is decided per client (`here: {client: bool}`), so another client's project copy does not offer "Turn off in this project…" for Claude Code.
- **A project-only Claude Code skill** with `skillOverrides` in the user file shows the reason in Details: "Claude Code may not merge skill settings across files; turn it off for all projects instead." This is the existing guard's words.
- **The git root's local settings.** Claude Code v2.1.211+ keeps `.claude/settings.local.json` at the git root when started in a subfolder, and the root's value wins (docs checked 2026-10-26; check again and date it).
  - Reads: Kitden reads the git root's local file for a project inside a repository, with that precedence.
  - Writes: Kitden writes a project rule to the file Claude Code reads first.
- **NEW_LOCAL_FILE words.** They become: "Kitden creates .claude/settings.local.json in <folder>. If git lists it, add it to .gitignore."
- **Find chip rule** (Gateway and Library alike). It counts what lights on the shown page: a lit card counts once. Matches on other pages are named by the caption's range.
- **A count fold during a search** stays folded for that search, as design.md says.
- **Stale reads.** A failed library-map read is never taken as fresh. A read that began before a page reload does not mark old data fresh.

### Words, kept from the mockup where Kitden can keep them
- Map hint line: "Point at a link and press × to remove it · drag a plugin onto a client to add it there · + adds it for all projects · click anything for its Details".

## Global Constraints

- **AGENTS.md in full.** Simple English in code, comments and page words. Tests on sandbox homes only. Dated facts about other tools.
- **The tray is the only way to write.** Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. A drag, a ×, a click or a tick only adds a tray row (`addToTray`); nothing writes without the tray's Apply. A refusal is said when a row is added, never at Apply.
- **No paths on main pages.** Main pages show a name, the client and an action. Paths, addresses, commands, ids and file lines stay under Technical details. A file's name (`CLAUDE.md`) is a name; its folder path is not.
- **CSP** stays `script-src 'self'; style-src 'self'`:
  - no innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText`;
  - CSSOM properties and `setProperty` only;
  - icons through `icon()`, adding any missing lucide data to icons.js.
- **Calm motion only**, from `motion.js`. Every motion has a reduced-motion path that lands at once. Nothing stays at opacity 0, nothing loops, and there is one motion per change.
- **Docs and pins in the same commit.**
  - `docs/design.md` changes with the page change it describes.
  - New page words are pinned in `tests/unit/test_page_words.py`.
  - `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- **Before each commit:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- **ROADMAP.md** gets its line in the same commit when a task changes what Kitden does.
- **Repository and processes.**
  - Never stage `design/`. Stage only your own files, by name. No `git stash`.
  - Never `pkill -f kitden`; stop only a process you started, by its pid. The owner's pages run from `/tmp/kitden-check`; leave them.
  - Another session may add logo work: keep the `--hearth` token, `.brand` / `.brand-mark`, `startLogo`, the Identity paragraph and the Logo row.
- **Guarded functions.** Do not grow `gatewayTree` (gateway.js), `layoutTree` (map.js), `showDetails` (details.js), `toolsSection` (tools.js) or `mapView`'s `draw` (map-view.js); add small named helpers. Pins in test_page_words.py that name moved source strings move with the code.
- **Commit messages:** a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

- **A drop that must change nothing.** A plugin dropped on Cursor, on a client that already has it, over the add panel, over the dock or on nothing: the block or ghost goes home, and the tray and the map are as they were. Test in Task 1.
- **The × and Undo on a Claude Code plugin.** A plugin removed from Claude Code by its link's × and then Undone comes back, and its review said its saved options are not brought back. Test in Task 2.
- **Hard CLAUDE.md imports.** A CLAUDE.md with an import loop (A imports B imports A), an import inside a fenced block, a missing import and a five-hop chain: no hang, no import from the fence, the missing one named, and the chain stopped after four hops. Test in Task 4.
- **The owner's real setup on the List.** With dozens of plugins, the Differences filter shows only differing rows and plugin rows fold, and nothing overflows its cell. Test in Task 6 with the large sample.
- **Add missing under All projects.** With nothing missing it says "Nothing is missing." and adds nothing to the tray. Test in Task 7.

---

### Task 1: A shared drag engine, and a plugin or skill onto a client

**Files:**
- Create: `src/kitden/web/static/js/map-drag.js` (the engine moved out of gateway-drag.js)
- Modify:
  - `src/kitden/web/static/js/gateway-drag.js` (keeps the Gateway's `DRAGS` hooks; the Gateway behaves exactly as before);
  - `src/kitden/web/static/js/library-map.js` (blocks that drag, the Library's `DRAGS`, preview links and the "Preview · <Client>" meta);
  - `src/kitden/web/static/style.css`;
  - `docs/design.md`.
- Test: `tests/frontend/map-drag.test.mjs` (create), `tests/frontend/gateway.test.mjs`, `tests/frontend/library-map.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:**
  - map-view.js's `hold`, `homeIn`, `tip`, `untip`, `lightTarget`, `unlightTarget`, `wire`, `unwire` and `glance`;
  - the Library map data's `items`, `by`, `can`, and the skill and plugin routes;
  - the `plugin.install` and `skill.install` bodies for one client (library.js `previewFor`).
- **Produces:**
  - `startDrag(event, block, kind, { hooks, map, onStart })` in map-drag.js, with the same behaviour the Gateway has today;
  - the Library's `DRAGS.item` (begin, over, drop), with the refusals and words in Decisions;
  - the map's preview link and meta for a waiting add row.

- [ ] **Step 1: Write the failing tests.**
  - `the Gateway's drags behave as before through the shared engine`: run today's drag tests unchanged.
  - `a plugin dragged onto Codex adds one plugin.install row for Codex`.
  - `a plugin over Cursor says Cursor gets plugins through Claude Code and Cursor shakes on release`.
  - `a client that has it says Already in <Client>; a waiting add says Already in preview`.
  - `a drop over Details, the dock or nothing leaves the tray as it was` (Review Focus).
  - `a waiting add draws a dashed link and Preview · <Client>; a press takes it out`.
  - `a skill may drop on Cursor when it has a route`.
  - `under reduced motion it lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`** and the Map hint line. Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frames `M8·1` and `M8·2`.
- [ ] **Step 6: Commit** — `Library: drag a plugin or skill onto a client`.

### Task 2: Link × on the Library map

**Files:**
- Modify: `src/kitden/web/static/js/library-map.js` (`LINKS`: `tip`, `onRemove`, `waits`), `src/kitden/web/static/js/library-details.js` (the Connection Details words for links with no ×), `docs/design.md`
- Test: `tests/frontend/library-map.test.mjs`, `tests/frontend/library-details.test.mjs`, `tests/unit/test_remove_plugin.py` (the Undo note through the tray), `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:** the `plugin.remove`, `skill.rule` and `skill.remove` bodies and keys; map-view.js's link hooks (`tip` "" means no ×); `REMOVE_NOTE`.
- **Produces:** the × rules and words in Decisions ("Link ×"); Delete on a focused link does the same; links with no × keep their Details.

- [ ] **Step 1: Write the failing tests.**
  - `a client→plugin link's × adds plugin.remove for that client`.
  - `the review of a Claude Code removal says its saved options are not brought back; Undo puts it back` (Review Focus).
  - `a client→skill link's × turns it off in Claude Code or Codex, and removes Cursor's own copy`.
  - `a preview link's × takes the row out`.
  - `plugin→inside, Cursor plugin, faint and Unknown links have no ×`.
  - `Delete on a focused link does what its × does`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`.** Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frame `M7·6`.
- [ ] **Step 6: Commit** — `Library: a link's × removes or turns off`.

### Task 3: The shared add panel, and "+ Add" for plugins and skills

**Files:**
- Create:
  - `src/kitden/web/static/js/add-panel.js` (the panel moved out of gateway-add.js, with a page config);
  - `src/kitden/web/static/js/library-add.js` (the Library's config).
- Modify:
  - `src/kitden/web/static/js/gateway-add.js` (now the Gateway's config; the Gateway behaves exactly as before);
  - `src/kitden/views/catalog.py` and `src/kitden/views/skills.py` (`library_offers(inventory, adapters) -> list[dict]`);
  - `src/kitden/web/app.py` (`GET /api/library-offers`);
  - `src/kitden/web/static/js/library-map.js` ("+ Add" on the "Plugins and skills" caption; preview cards for waiting adds);
  - `src/kitden/web/static/js/offer.js` (its `marketplaceForm` opens from the panel);
  - `src/kitden/web/static/style.css`, `docs/design.md`, `ROADMAP.md`.
- Test: `tests/unit/test_library_offers.py` (create), `tests/security/test_no_secrets.py`, `tests/frontend/add-panel.test.mjs` (create; the Gateway's add-panel tests move or stay green), `tests/frontend/library-add.test.mjs` (create), `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:** `catalog()` and `skill_catalog()`; the multi-client `plugin.install` and `skill.install` bodies; Task 1's Library drag for panel rows; `addRowWords` and `matchRows` from gateway-add.js, moved into the shared panel.
- **Produces:**
  - `library_offers` and `GET /api/library-offers` (rows as in Decisions, no paths);
  - `openAddPanel(config, { from })` in add-panel.js;
  - the Library's panel, with the words in Decisions;
  - preview cards on the map for waiting adds.

- [ ] **Step 1: Write the failing tests.**
  - `library_offers lists plugins and skills by marketplace with no paths`.
  - `the Gateway's add panel behaves as before`: run today's gateway-add tests.
  - `+ Add opens Add a plugin or skill; the pill filters Plugins and Skills`.
  - `a click adds for all projects to every client with a route that lacks it, and a second click takes it out`.
  - `a row says Added, In every client, its refusal or In preview`.
  - `a plugin no client has shows as a preview card with dashed links while it waits`.
  - `a panel row dragged onto Codex adds for Codex only`.
  - `Add a marketplace… opens the marketplace form`.
  - `under reduced motion it lands at once`.
  - The secrets sweep and the pins.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md` and `ROADMAP.md`.** Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frames `L4`, `M8·2` and `M8·3`.
- [ ] **Step 6: Commit** — `Library: add a plugin or skill from a marketplace`.

### Task 4: Instruction files and their imports (backend)

**Files:**
- Create: `src/kitden/views/imports.py` (`imports(path: Path, root: Path | None, home: Path) -> list[dict]`), `src/kitden/views/instructions_map.py` (`instructions_map(inventory, adapters, project) -> dict`)
- Modify: `src/kitden/web/app.py` (`GET /api/instructions-map?project=`)
- Test: `tests/unit/test_imports.py` (create), `tests/unit/test_instructions_map.py` (create), `tests/security/test_no_secrets.py`

**Interfaces:**
- **Consumes:**
  - the instruction items each adapter lists today: Claude Code's CLAUDE.md, CLAUDE.local.md, `.claude/CLAUDE.md` and rules; Codex's AGENTS.md; Cursor's rules;
  - `brief`/`preview` in views/explain.py for first lines, with secrets redacted.
- **Produces:**
  - **`imports(...)`** gives `[{name, target, depth, outside: bool, missing: bool, via}]`. It follows the import rules in Decisions: relative to the file, `~`, four hops, skipping spans and fences, stopping a loop at the first repeat.
  - **`instructions_map(...)`** gives:
    - `{clients, groups: [{key, name, files: [{id, name, by: {client: true}, through?, count?, imports: [ids], lines, technical: {path}}]}], imports: [{id, name, by_files, outside, technical: {path}}]}`;
    - groups "All projects" and "Only this project · <folder>";
    - Cursor rules folded by folder;
    - Claude Code reading AGENTS.md only if the dated docs say so.
  - **`GET /api/instructions-map?project=<id>`**, with the same token and origin checks. It never feeds the MCP server.

- [ ] **Step 1: Check the docs** (code.claude.com/docs/en/memory: `@` imports, depth, code spans, AGENTS.md). Date the claims in code comments.
- [ ] **Step 2: Write the failing tests.**
  - `an import is read relative to its file and ~ works`.
  - `imports nest four hops and stop`.
  - `an import in a code span or a fenced block is skipped`.
  - `a loop stops at the first repeat` (Review Focus).
  - `a missing import is named, not followed`.
  - `an import outside the project is marked outside`.
  - `Codex and Cursor files have no imports`.
  - `Cursor rules fold by folder`.
  - `the answer has no paths outside technical`.
  - The secrets sweep.
- [ ] **Step 3: Run** them — expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Library: read instruction files and their imports`.

### Task 5: The Instructions map and file Details

**Files:**
- Modify:
  - `src/kitden/web/static/js/library-map.js` (the "Instructions" tab draws its own map through `mapView`; it no longer switches to the List);
  - `src/kitden/web/static/js/library-details.js` (the file and imported-file Details);
  - `src/kitden/web/static/style.css`, `docs/design.md`, `ROADMAP.md`.
- Test: `tests/frontend/library-map.test.mjs`, `tests/frontend/library-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:** Task 4's `/api/instructions-map`; the Library map's select, path light and Details plumbing; `library-notes.md` §6.
- **Produces:**
  - **The map:** the Instructions columns, file blocks (190×54, `file-text` tile, name and meta) and import blocks (200×40, `scroll-text`).
  - **The tab switch:** clients stay and move (260); leaving blocks shrink (160 IN3); arriving ones grow (220 OUT3, 15 apart).
  - **Details:** the file and imported-file panels, with the words in Decisions.
  - Nothing enters the tray, and links have no ×.

- [ ] **Step 1: Write the failing tests.**
  - `the Instructions tab draws Clients, Files and Pulls in`.
  - `a file block names its clients and its imports`.
  - `only Claude Code files have import links`.
  - `a click on a file lights its client and imports and opens its Details`.
  - `file Details show Read by, Through, Size and the say line; the path and first lines sit under Technical details`.
  - `an outside import says Claude Code may ask before it reads this`.
  - `the tab switch moves clients and swaps the columns`.
  - `under reduced motion it lands at once`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md` and `ROADMAP.md`.** Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frames `I1`, `M8·4` and `M8·5`.
- [ ] **Step 6: Commit** — `Library: the Instructions map`.

### Task 6: The new List

**Files:**
- Modify:
  - `src/kitden/views/library.py` (`show="diff"`; rows for the two tabs: plugin rows with child part rows, hooks under "Your settings", marketplaces as group rows, the instruction file rows);
  - `src/kitden/web/static/js/library.js` (the List rebuilt from the new rows; the old six tabs, the New/All show choice and the category filter go; "Needs attention" stays);
  - `src/kitden/web/static/style.css`, `docs/design.md`, `ROADMAP.md`.
- Test: `tests/unit/test_library.py`, `tests/frontend/library.test.mjs`, `tests/unit/test_page_words.py` (the pins that name removed library.js strings move or go with the code), `tests/unit/test_contrast.py`

**Interfaces:**
- **Consumes:**
  - today's `/api/library` cells and adds;
  - Tasks 1–3's actions (a cell's "+ Add" is today's add; a row's press opens the same Details as the map);
  - `library-notes.md` §7 and frame `L3` for the grid, row heights and the Map ↔ List swap.
- **Produces:**
  - the List as in Decisions ("The List");
  - `show=diff` on the server (Differences);
  - the keyboard rules;
  - the List's hint line.

- [ ] **Step 1: Write the failing tests.**
  - `the List has the two tabs and one column per client`.
  - `a plugin row says Plugin · n items and folds its parts`.
  - `cells say On, Off, Via Claude Code, + Add or nothing`.
  - `Differences shows only rows whose cells differ; a plugin differs when a part differs` (Review Focus, large sample).
  - `Needs attention still filters`.
  - `hooks sit under Your settings; a marketplace row opens its Details`.
  - `the Instructions List has one row per file`.
  - `Up, Down, Right, Left and Enter work`.
  - `old show=new and kind=marketplace links land in their new place`.
  - The pins.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md` and `ROADMAP.md`.** Run all four checks — expected: PASS.
- [ ] **Step 5: Check in a real browser** beside frame `L3`, on the large sample and on the owner-like medium sample.
- [ ] **Step 6: Commit** — `Library: the List in the new look`.

### Task 7: Add missing for plugins and skills, and "In preview" on the add forms

**Files:**
- Modify:
  - `src/kitden/changes/align.py` (`align_steps` with no project: all-projects items one client has and another lacks);
  - `src/kitden/web/app.py` (`project.align` with no project);
  - `src/kitden/web/static/js/review.js` (titles and done words for All projects);
  - `src/kitden/web/static/js/library.js` ("Add missing plugins and skills…" on the List, in a project and in All projects);
  - `src/kitden/web/static/js/offer.js` and `library.js` (the add forms and the add choice show "In preview" with `showInPreview` while their row waits);
  - `docs/design.md`.
- Test: `tests/unit/test_align.py`, `tests/frontend/review.test.mjs`, `tests/frontend/offer.test.mjs`, `tests/frontend/library.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:** today's `align_steps`, its four review groups (`alignGroups`, `alignSection`), and `showInPreview` and `followTray` (details.js).
- **Produces:**
  - `project.align` under All projects for plugins and skills (MCP servers keep their Gateway place);
  - the review title "Add what your clients are missing" and the done words "Added <n> items for all projects";
  - "Nothing is missing." when there is nothing (Review Focus);
  - "In preview" on the add forms and the add choice.

- [ ] **Step 1: Write the failing tests.**
  - `Add missing under All projects lists what one client has and another lacks`.
  - `with nothing missing it says Nothing is missing. and adds nothing` (Review Focus).
  - `Apply and Undo put every file back`.
  - `an add form says In preview while its row waits and goes back after`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update `docs/design.md`.** Run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Library: add what your clients are missing, in any scope`.

### Task 8: Skill rules: the leftovers from Phase 6A

**Files:**
- Modify:
  - `src/kitden/clients/claude_code.py` (read the git root's `.claude/settings.local.json` for a project inside a repository, with the root's value winning; write a project rule to the file Claude Code reads first);
  - `src/kitden/views/library_map.py` (`here` per client; the project rows' "already off" state);
  - `src/kitden/web/static/js/library-details.js` ("Use the shared rule…", "Already off there", "Turn off this copy in Codex…", the reason for a project-only Claude Code skill);
  - `src/kitden/views/words.py` (the NEW_LOCAL_FILE words);
  - `docs/design.md`.
- Test: `tests/unit/test_claude_code_settings.py`, `tests/unit/test_skill_rule.py`, `tests/unit/test_library_map.py`, `tests/frontend/library-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- **Consumes:** Phase 6A's `skill.rule`, `skill_rules_in`, `project_rules` and `in_project`; the "Notes from Phase 6A" list.
- **Produces:** every item in Decisions ("Leftovers from Phase 6A") except the find chip, the count fold and the stale reads, which are Task 9.

- [ ] **Step 1: Check the docs** (code.claude.com/docs/en/settings: the git root local file). Date the claims.
- [ ] **Step 2: Write the failing tests.**
  - `Use the shared rule… removes the project's key and Undo puts it back`.
  - `a project that already turns the skill off is Already off there and cannot be ticked`.
  - `a Codex skill in one project gets Turn off this copy in Codex…`.
  - `another client's project copy does not offer Turn off in this project… for Claude Code`.
  - `a project-only Claude Code skill shows the reason while the user file has skillOverrides`.
  - `a project in a subfolder of a repository reads the root's local file, and the root's value wins`.
  - `the new local file words`.
- [ ] **Step 3: Run** them — expected: FAIL.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run** all four checks — expected: PASS.
- [ ] **Step 6: Commit** — `Library: the last skill-rule notes`.

### Task 9: Map notes, docs and the Library hint

**Files:**
- Modify:
  - `src/kitden/web/static/js/map.js` and `library-map.js` / `gateway.js` (one find-chip rule: count what lights on the shown page);
  - `src/kitden/web/static/js/map.js` (a count fold during a search stays for that search);
  - `src/kitden/web/static/js/store.js` (a failed library-map read is never fresh; an older read never marks newer data fresh);
  - `docs/design.md`, `ROADMAP.md`, `docs/mockup/README.md` (lists library-notes.md).
- Test: `tests/frontend/map.test.mjs`, `tests/frontend/library-map.test.mjs`, `tests/frontend/gateway-page.test.mjs`, `tests/frontend/store.test.mjs`

**Interfaces:**
- **Consumes:** the "Notes from Phase 6A" list.
- **Produces:** the find-chip rule, the count fold, the stale-read rules, and the docs made true.

- [ ] **Step 1: Write the failing tests.**
  - `the chip counts what lights on the shown page, on the Gateway and the Library`.
  - `a count fold during a search stays folded after a redraw`.
  - `a failed map read is read again on the next open`.
  - `an older read never marks newer data fresh`.
- [ ] **Step 2: Run** them — expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Update the docs.** Run all four checks — expected: PASS.
- [ ] **Step 5: Commit** — `Map: one find rule, a fold that stays, fresh reads`.
