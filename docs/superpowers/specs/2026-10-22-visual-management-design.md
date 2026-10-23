# Visual management: one picture of the setup, then the leftovers, then a tour

Date: 2026-10-22. Baseline `541eb44` (main) plus `e1e505e` (branch `align-listing-fix`).
Status: written for the owner's review; the plan follows it.

Sources: the UX concept
[docs/research/visual-management-ux-concept-2026-10-22.md](../../research/visual-management-ux-concept-2026-10-22.md)
(cited as "concept §N"), the earlier design
[2026-10-21-review-follow-up-design.md](2026-10-21-review-follow-up-design.md) (Parts 1–6 shipped,
5.3 OAuth waits for the owner), the deferred findings of Parts 1–6, and three code surveys of
2026-10-22 (kept with the plan, not in the repository).

## Why

The owner wants Kitden to answer three questions for one person or a small team, without the
developer explaining it:

1. What does each of my agents load, where does it come from, and is it global or for this
   project?
2. What differs between my agents in this project, and how do I add or move what is missing?
3. Which tools can my agents call through the local gateway, and which calls go around it?

Three requirements hold for everything: the page is **simple and visual**, so a person wants to
press the buttons; it **opens fast**; it is **secure and local**, and tokens never leave the
computer except to their own server.

Parts 1–6 built most of the mechanics. What is missing is one clear picture that connects
them: the same item and project on every page, the source and the reason behind every state,
and an honest word for what Kitden does not know. The concept describes that picture. This
design turns it into parts that ship one by one, then clears the deferred findings, then
documents the result as something a person can try, not only read.

The owner moved "Linux and Windows" (old Part 7) to Later and chose this work instead.

## Goals

- **One shared context.** The project and the selected item stay the same across Overview,
  Library and Gateway, in the address too, so a link or Back returns to the same place.
- **True words for what Kitden knows.** "All projects" means the shared baseline; a cell says
  where its state comes from when that matters; Unknown never looks like Missing; a same-name
  item from another source never looks equal; no button is offered that can only fail.
- **Details answers five questions in order** (concept §8): what is it and its state here; why
  and from where; which clients and projects an action affects; what to do next; the technical
  evidence, folded.
- **Compare shows differences.** A Differences filter, Needs review for unsure matches, project
  exceptions under All projects, and an Add missing review in four honest groups.
- **Access shows routes and origins.** Direct routes beside gateway routes, a held server's
  clients, each tool's origin (All projects, this project, a parent project, no rule), the effect
  of strict mode named before Apply, and the limit of what the gateway controls.
- **A setup map** on Overview: sources, item groups and clients in a fixed layout; select a
  client or an item to see its relationships; open the shared Details from there.
- **The deferred findings of Parts 1–6 are fixed or closed with a reason.**
- **Documentation a person can try:** `kitden demo` opens the real page on a built-in sample
  setup, with a short guided tour; the README and a task guide use pictures from the demo.

## Non-goals

- Live context inspection, token estimates, or proof that a session loaded something. Kitden
  reads saved settings and says so (concept §5.4, §13).
- A graph editor: no drag to install, no drag to connect, no free node placement (concept §5.3).
- Automatic sync between clients.
- Linux and Windows (Later), teams (Later), OAuth sign-in (old Part 5.3, waits for the owner).
- A new visual identity. Quiet Den + Graphite, system fonts, both themes (concept §2, design.md).
- Runtime telemetry to make the map look active (concept §11).

## Anti-goals

Failure even if it works:

- A state shown as fact when Kitden does not know it: Unknown shown as Missing, a name match
  shown as the same item, a selected project shown as proof of what a running session uses.
- A green word used as proof that a tool is harmless.
- Moving lines or pulses while idle; a map that rearranges itself; a map that is required to do
  a task (the table route must always work).
- More text on the main pages. Name, client, state, action; the rest in Details.
- Any write that skips preview → Apply with a backup → verify → Undo.
- A demo that touches the real home, runs a real client, starts a real MCP server, reads the
  Keychain or goes online.
- A slower start. The first usable page stays within its budget; the map loads only when shown.

## Constraints

- `AGENTS.md` in full: simple English in code, UI and docs; Russian with the owner; tests on
  sandbox homes; the three checks before each commit; dated facts about other tools;
  `ROADMAP.md` in the same change; release notes per release; short plain commit messages.
- Stack unchanged: Python 3.13, Starlette, MCP SDK 2.3, tomlkit, watchfiles; plain ES modules,
  one CSS file; no framework, no bundler, no library from another site; strict CSP. No new
  runtime dependency.
- `docs/design.md` governs look and motion; each part updates it where it changes the page.
- About 78 exact-string checks in `tests/unit/test_page_words.py` pin today's words. A part that
  changes a word changes its test and `docs/design.md` in the same commit.
- `explain()` and `project_views()` also feed the read-only MCP server; a change to their output
  is checked there too (file lines never go to agents: Part 6 ruling).
- The owner has an uncommitted edit in `ROADMAP.md`. Until the owner commits it, no part edits
  or stages `ROADMAP.md`; each part's report gives the lines instead. Every commit stages files
  by name.

## How it works

Eight parts, in order. "My call" marks a choice the owner did not make; the owner can change
any of them.

### Part 1. A sample setup and a safe demo mode

The base for everything after it: the fixtures the concept asks for (§12), the safe place where
the owner walks the new pages, and later the tour.

**1.1 Sample setups.** One builder, `src/kitden/demo/`, writes a synthetic home in three sizes
(concept §12):

- `small`: one client (Claude Code), a few servers, skills and plugins, one project.
- `medium`: Claude Code, Codex and Cursor, about 60 items, five projects (one missing, one not
  trusted by Codex), a project override, a shared skill folder read by two clients, a same-name
  server from two different sources, an unreadable source file, a Kitden gateway with two held
  servers (one local, one remote) with cached tools, an unknown tool hint, a project rule and a
  parent-project rule, instruction files.
- `large`: hundreds of items, long names, more than ten projects (reuses the generator in
  `scripts/measure-start.py`, which moves into the builder so there is one copy).

Every secret in a sample is a fake value of the form `DEMO_SECRET_*`; the security sweep checks
none shows on any page. My call: the sample data is generated by code, not copied files, so the
wheel ships it (the wheel ships only `src/kitden`) and the tests can use the same builder.
`tests/fixtures/` stays as it is (it pins real client versions).

**1.2 Demo mode.** `kitden demo [--size small|medium|large]` builds the sample in a new
temporary folder, serves the page on it, opens the browser, and deletes the folder on exit. In
demo mode:

- no real client command runs: a demo runner answers the few commands the sample needs (for
  example `claude mcp add-json` and `claude mcp remove`, applied to the sample files) and refuses
  any other with "Not part of the demo.";
- no MCP server starts: tool lists come from the sample's tool cache, and a move into the Kitden
  gateway uses a canned tool list;
- no Keychain: the stand-in stores values in the demo folder;
- no network: marketplace links and registered gateways are refused with a plain sentence;
- client versions are the sample's, not this computer's; `CODEX_HOME` and the real `/Applications`
  are not read;
- the page shows a quiet "Demo" tag in the shell and every change goes through the same
  preview → Apply → verify → Undo, inside the demo folder.

**1.3 A write boundary for every change.** The change engine refuses at preview any step whose
path is outside the home folder, Kitden's data folder, the found clients' own settings folders
(Codex's `CODEX_HOME` can sit elsewhere) and the known project folders ("Kitden
writes only in your home folder and your known projects."). Known projects come from the
clients' own settings and can sit on another disk, so they stay allowed. This guards the demo
(whose projects are inside the demo home) and real use alike. My call.

**1.4 First walkthrough, on today's page.** Once demo mode works, the owner may try the seven
tasks of concept §12 on the current page in `kitden demo` (about 15 minutes; the agent prepares
a one-page script). The results go to `docs/research/walkthrough-<date>.md` and settle, before
Part 2, the words that are still a guess: "Loads" or "Available", On/Off or Allowed/Blocked for
tools. Concept §12 asks to compare with the current interface; this is that baseline. If the
owner skips it, the words below stand. My call: two short walkthroughs (here and 6.5) instead
of a separate prototype, because the demo is the same page built for real and words are cheaper
to settle before Part 2 than after it. All state words stay in one table
(`parts.js STATE_WORDS` and its Python twin) so a later rename is one change.

Done: `kitden demo` opens in under two seconds on `medium`; a test runs the demo app with a
`Popen` and socket guard and drives an Add, a tool switch and Undo; the security sweep passes on
all three sizes.

### Part 2. Shared words, scope and selection

The language every later part uses (concept §4, §6.2).

**2.1 All projects.** The picker's empty choice reads "All projects" (not "Global"). Cells,
Details and reviews use the same two phrases: "all projects" and "this project". The file-scope
word "global settings" stays only inside Details' technical evidence.

**2.2 Origin in one short label**, only where it changes a decision (concept §4): a cell in a
project says "· this project" when the item comes from the project, "· project override" when a
project item wins over an all-projects one (from `load_map`'s winners), and "· all projects"
when it comes from all projects. Walkthrough 1 (F3): with only the project words shown, the owner
could not tell what is Atlas's own, so in a project view every cell says where it applies. With
All projects picked, cells carry no scope word (it would be the same on every row).

**2.2a One fact per slot** (walkthrough 1, F5). The cell's quiet word says only where the item
applies. How the client gets it ("through Codex's folder", "from a plugin", "through the Kitden
gateway") goes to the hover text and to Details, never into the same slot.

**2.3 States.** The cell words are "Available" and "Off" (walkthrough 1: the owner chose
"Available"; the page keeps "Based on saved settings"). "Available" also replaces "Has it" on the
Instructions tab, so one word means one thing everywhere. Three states become distinct:

- **Unknown** when the source was not read (a file that failed to parse, a client whose scan
  failed): its cells say Unknown with the reason, never "—" or "+ Add". A failed client keeps its
  column, marked "Could not read". While the page runs, Kitden keeps the last good read of each
  source in memory: when a file that read well before now fails, its items stay, marked "From
  the last good read at 14:02" (concept §9). On a first read there is nothing to keep, so the
  Library says "Could not read <file>; its items are not shown." above the table, and Overview
  keeps its card. My call: in memory only, not saved to disk.
- **Needs review** when a same-name entry comes from another source and Kitden cannot tell they
  are the same (reusing `align._not_same` evidence: command, args, URL, skill real path).
- **—** stays for "not there, after a good read", with "+ Add" where an add is possible.

No "+ Add" is shown where the preview would refuse it (the unreadable file case, the same-name
case, a cell whose target client cannot take it). The other way round too (walkthrough 1, F6):
a cell Kitden can fill always shows "+ Add", and Details offers the same add; an item that exists
only in this project adds into this project.

**2.3a Notes that do not overstate** (walkthrough 1, F7, F8). Overview's notes never call two
entries from different sources "set up in more than one client": that is "Same name, another
source". Every note row shows the clients it is about. Notes are grouped by item: one row per
name, with its notes inside.

**2.4 Every add names its scope before the click.** With All projects picked, the add's review
title and lede say "for all projects". A removed or unknown project is never silently replaced
by All projects: the page says "This project is no longer on the list." and keeps the user where
they were.

**2.5 Selection in the address.** The hash carries `sel=<kind>:<name>` on every page. Library
opens that row's Details; Gateway opens that server's Details; the map selects that item. Moving
between pages keeps project and selection (concept §3). Back and a copied link return to it.
`#map` stays the old redirect to the Library; the map lives on Overview (Part 6).

Done: a test walks Overview → Library → Gateway with one selection and project and checks the
address, focus and Details each time; the page-words tests carry the new words.

### Part 3. One Details panel and one change flow

Concept §8 and the §9 states.

**3.1 Details order**, the same for every kind:

1. Kind, name, and its state here (today's lede).
2. Why: the deciding source and rule, in one or two plain lines (built from `explain.why()`,
   `shadowed`, origin), then the per-client sections. When one folder serves several clients,
   the Why says so in those words ("One folder, read by Codex and Cursor"): walkthrough 1, F1.
3. **Affects:** before any action, the clients and projects the lead action would change, for
   example "Changes Codex and Cursor (Cursor reads Codex's folder). All projects." (from the same
   reader logic the review uses: `_readers`, `CURSOR_IMPORT`). A Remove button that reaches more
   than one client names them all ("Remove from Codex and Cursor…"): walkthrough 1, F1.
4. The lead action and the rest under More (as today).
5. **Technical details**, folded: paths, commands, file keys, the instruction preview.

**3.2 Links that keep context:** "Compare across clients" (Library, that row), "Manage tools"
(Gateway, that server), "Show on the map" (Overview map, that item). Each keeps project and
selection.

**3.3 The review leads with the outcome.** One sentence that names the change, the target scope
and the clients, then "Other projects are unchanged." only when the steps guarantee it (every
step in one project's files, or a project rule), then the After chips, then the folded file
changes. The lede no longer promises Undo for every change: it says "A backup is kept." and the
known Undo limit when one applies (for example a plugin's saved options).

**3.4 States** (concept §9):

- Cancel returns to the Details the review came from, with focus where it was.
- When a rescan finishes while a review is open and a file in the change has changed, the
  review says "Settings changed since this preview." and offers "Preview again" before Apply.
- No clients found: say which clients Kitden looks for and where, and offer `kitden demo`.
- Partial scan and a failed source: a quiet line per source still loading or failed, next to
  the place it affects; the rest of the page works.

Done: node tests for the Details order and the Affects line; a test for a stale review; page
words updated.

### Part 4. Compare: differences you can act on

Concept §6. The Library matrix stays the main working surface.

**4.1 Differences filter.** Beside Installed / New / All: "Differences" shows only rows whose
cells differ between the found clients in the picked context (one Loads and one —, Off vs Loads,
Needs review, Unknown). It is a hash filter like the others.

**4.2 Project exceptions under All projects.** A row whose item is changed by a project (a
project override or a project-only item with the same name) shows a quiet "2 project
exceptions" link that opens Details listing them (concept §4). Changing an all-projects item
never removes a project override; the review says so when one exists.

**4.3 Add missing in four groups** (concept §6.3), in one review grouped by client. It follows
the tab (walkthrough 1, F4): on Skills it reads "Add missing skills…" and lists only skills; the
review says which kind it covers.

1. **Will add**: the checkboxes, each with its target scope and the reason it is missing
   ("Claude Code has it; Codex does not").
2. **Already there another way**: items a client gets through a plugin, a shared folder or
   another client, and items it has turned off on purpose, each with that reason; nothing to do.
3. **Needs your decision**: same-name items from different sources, with a "Compare" link to
   their Details; never added silently.
4. **Kitden cannot add**: with the target client and the reason, one per line.

It keeps today's rule: an add that would make a duplicate starts unchecked; with nothing
checked, Apply waits.

Done: tests for each group on the `medium` sample; the review leads with "Adds N items to
<project>"; the Differences filter is in the hash and the node tests.

### Part 5. Access: routes, origins and honest limits

Concept §7.

**5.1 Route summary.** The Gateway diagram draws the Kitden gateway's clients, its held servers,
and each direct route as its own quiet line labelled "Direct" (not amber: direct is not a
fault). Plugin-provided and Claude Desktop entries count. Every node is reachable by keyboard;
lines draw once and rest (as today). The fixed limit line stays: "The gateway controls only the
servers in it. Direct entries and terminal tools are outside it."

**5.2 Server rows** show the clients that reach them through the gateway.

**5.3 Tools with origin.** Each tool row keeps its switch and hint word and gains one quiet
origin word: "All projects", "This project", "From <parent folder>", or, when no rule decides,
"On by default" or, in strict mode, "New · waits" (in strict mode a tool with no rule is a new
tool). The effective state
includes the server switch (a tool of a server that is off shows off, with that reason).
"Use <parent>" (remove this project's rule) is offered whenever the project has its own rule,
even one equal to the inherited value. My call: the switch words stay On and Off; the origin
word carries the "why".

**5.3a The tools panel names its own scope** (walkthrough 1, F10). The owner turned a tool off
for all projects while meaning one project: the switches followed the top picker unseen. The
tools panel gets its own scope choice in place, "For: All projects ▾" (all projects and each
known project), starting from the top picker's project; changing it redraws the switches for
that scope. Every tool review's title starts with the scope ("All projects: read_file off").

**5.4 Reviews that do not overstate.**

- "Turn off every writing tool…" becomes a checklist: tools that write or may write are checked,
  each with the source of its hint; tools whose behaviour is unknown are listed unchecked under
  "Not sure"; the token advice stays.
- Turning strict on names the tools it keeps on ("Keeps on: read, list, search.") and says new
  tools wait. The Strict row itself stops saying "Only tools you turned on are offered" (strict
  mode turns on the known tools for you, so that overstates): it says "Only tools that are on
  are offered; a new tool waits."
- Both say a call already running is not stopped.

**5.5 Sessions and projects.** With a project picked, one quiet line: "A session gets these
switches only when it runs in this project's folder." With All projects: today's line about
unknown folders. Rules for a project that is no longer on the list show in a quiet "Rules for
folders Kitden no longer finds" group, each with Remove (a rule step).

**5.6 Call counts** become keyboard reachable (a small "12 calls" text with the last time,
not only hover).

Done: tests for origin per tool (own, parent, global, none, strict), the effective state with
the server off, the writing-tools checklist, strict's kept list, the removed-project rules;
the diagram's keyboard path.

### Part 6. The setup map

Concept §5. It lives on Overview (my call: concept §14 leaves this open; Overview is the entry
point and the map is its picture). A "List | Map" switch in the Overview header shows the map;
the choice is remembered on this computer. The map's code loads only when first shown
(dynamic `import()`), so the start does not slow down.

**6.1 Layout.** Three fixed columns: **Sources** (groups such as "Claude Code all projects",
"Shared skills folder", "Plugin superpowers", "Project website", "Kitden gateway"), **Items**
(grouped by kind with counts: "12 skills", "9 MCP servers"), **Clients** (the found ones). The
first view fits a normal desktop window without panning. No lines are drawn until something is
selected.

**6.2 Selection.** Select a client: its sources and item groups light, the rest go quiet. Select
an item group: it opens to its items (one group open at a time). Select an item: lines draw from
its source(s) to it and from it to the clients that have it, each line labelled once with its
meaning: defines, contains, available to, overrides, routes through. Details opens beside it.
Search on the Overview goes straight to an item. Keyboard: Tab moves between nodes, Enter
selects, Escape clears.

**6.3 Data.** One new endpoint, `/api/setup-map?project=`, returns source groups, item groups,
items with their source group and clients, and typed relations. It is built from the inventory
already in memory (`effective_view`, `shadowed`, `plugin_of`, `via_gateway`, `skill_readers`).
No command runs, no server starts. A shared folder read by two clients shows as one source with
two "available to" lines, never as two copies; a real duplicate shows only when the findings say
so.

**6.4 Large setups and narrow windows.** Groups stay closed until opened; a group with more than
30 items shows the first 30 and "Show all". Under 900 px wide the map becomes a stacked list
(source → items → clients) with the same selection. Motion: a selected line draws once; nothing
moves while idle; reduced motion shows it at once.

**6.5 The owner's second walkthrough.** After this part, the owner runs `kitden demo` and
tries the seven tasks of concept §12 again, now on the new page, and compares with the first
walkthrough (1.4). The agent prepares the script and records the results in
`docs/research/walkthrough-<date>.md`. Fixes that follow go into Part 7 before the deferred
findings. Concept §12 says to keep the map only if it helps: if the owner finds it does not,
Part 7 hides the "Map" switch (the code stays behind it) and the tour skips the map stop. The
owner can skip this walkthrough.

Done: the map endpoint answers in under 150 ms on the `large` sample (measured in
`scripts/measure-start.py`, added as a third number); the first usable time stays within budget;
node tests for the layout and the selection; a page test that the table route answers every map
question without the map.

### Part 7. Leftovers

Clear what Parts 1–6 deferred, after the walkthrough's fixes. Each item is checked against the
current code first; an item that is already fixed or no longer applies is closed with one line.

Known items (the full raw list is kept with the plan):

- **Picture gaps (client facts, checked against current docs with the date):** whether Cursor
  reads `.cursor/agents`, `.claude/agents` and `.cursor/commands`; Claude Code reading `AGENTS.md`
  when there is no `CLAUDE.md`; agents named by their `name:` front matter.
- **Live page:** the watcher also watches known project folders (their `.mcp.json`,
  `CLAUDE.md`, `.claude/`, `.cursor/rules`), with a cap on how many folders.
- **Safer writes:** after a direct write to `~/.claude.json`, check and restore only the edited
  entry, so Claude Code's own update is never lost.
- **One rule for "loads twice":** Add missing's twice check and the review's After words use the
  same reader logic, project skills included.
- **Keychain sentences:** "may keep the new value" for an item whose own write failed; a token
  that ends in a newline moves correctly.
- **Gateway:** a tool turned off mid-session stays refused when the rules file breaks (fall back
  to the last good rules, not the start rules); the Changes line for a batch says on or off.
- **Page:** a folded group can fold back; the start reads shared data once, not twice; the
  gateway card offers set-up for every client that lacks it; Ctrl+C during a cold start does not
  wait for a client's version command.
- **Docs and tests:** `tests/fixtures/README.md` matches the fixtures; the smaller test and
  wording items from the Part 1–6 ledgers.

Done: each item fixed with a test, or closed with a reason in the part's report.

### Part 8. Documentation you can try

**8.1 The tour.** In demo mode only, a "Tour" button in the shell starts seven short stops that
follow concept §12: the Overview and its map; a skill shared by two clients; a server that a
project overrides (Claude Code ranks a user skill above a project skill, so the override example is
a server); Compare and its Differences; Add missing for one project (a real Apply
inside the demo); the Gateway with a direct route, a parent-project rule and a new tool that
waits; Undo. Each stop is one sentence and one highlighted place (the existing `.arrive` light),
with Next, Back and Close; keyboard and reduced motion work; nothing is fetched from outside.
The tour's text lives in one module, `tour.js`, loaded only in demo mode.

**8.2 README** rewritten around the owner's three questions and three requirements, each with a
picture from the demo (light and dark) and one line on how to try it: `uvx kitden demo`. It
stays the PyPI page, so pictures use full raw.githubusercontent links, as today.

**8.3 A task guide**, `docs/guide.md`: "I want to…" sections (see what loads where; find what
differs in a project; add what is missing; keep a server behind the gateway; block a tool for one
project; undo a change), each with the steps, a small diagram (Mermaid, which GitHub draws) and
the matching tour stop.

**8.4 How the pictures are made.** `docs/development.md` gains a short recipe: `kitden demo
--size medium`, the window size, the theme, which stops to capture. No personal paths ever
appear, because the demo home is synthetic.

**8.5 Release notes** `docs/releases/v0.3.0.md` for everything since 0.2.0 (Parts 1–6 of the
earlier design and Parts 1–8 here), in the format of v0.2.0.

**8.6** `docs/design.md` gets the map, the origin words, the new states and the tour; the
release hand check in `docs/development.md` gains the walkthrough tasks.

Done: the tour runs end to end in a test on the demo app (each stop's target exists); README,
guide and design.md words are checked by `tests/unit/test_docs_words.py`; the release notes file
exists.

## Order

1 → (walkthrough 1) → 2 → 3 → 4 → 5 → 6 → (walkthrough 2) → 7 → 8. Part 1 comes first
because every later part tests on its samples and both walkthroughs need it. Parts 2 and 3 set the words and the panel the
others use. Part 4 and 5 are independent of each other but share Part 2's words; run them in
order to keep reviews small. Part 6 needs 2–5. Part 7 needs the walkthrough. Part 8 describes
the finished page. Each part ships on its own.

## Left to the builder

- Exact copy of new sentences, within the rules above and design.md's voice.
- The layout numbers of the map (column widths, spacing), within design.md tokens.
- How the demo runner fakes each client command it supports.
- The order of tasks inside a part.

## Acceptance, from concept §14

The work is done when, on the `medium` and `large` samples:

- the three views tell one story about the same project and item;
- a person can trace an item's source and name the affected clients;
- a person can say an action's scope before Apply;
- differences, shared sources and real duplicates look different;
- gateway permissions and direct routes are clear without a security lecture;
- Unknown or stale information never shows as absent or as a guarantee;
- every change has a supported operation, a true preview and an honest Undo;
- everything works without the map, by keyboard, in both themes, and the start stays fast.

## Every concept recommendation, and where it lives

| Concept | Here |
| --- | --- |
| §3 three views, no second navigation, context kept | 2.5, 3.2, 6 |
| §4 All projects, origin labels, exceptions, action target, session ≠ project | 2.1, 2.2, 2.4, 4.2, 5.5 |
| §5.1–5.2 grouped map, two levels, search, relationship meanings | 6.1–6.3 |
| §5.3 selection, Details, links, no editing by drag | 6.2, 3.2, Non-goals |
| §5.4 large setups, deterministic layout, counts honest | 6.4, 6.3 |
| §6.1 matrix, Differences, Add missing, no summary cards | 4.1, 4.3 |
| §6.2 Available/Off/Missing/Unknown/Needs review, no Add that can only fail | 2.3 |
| §6.3 matching evidence, four outcome groups, no silent copies | 2.3, 4.3 |
| §7.1 routes, Direct not a fault, no fake traffic | 5.1 |
| §7.2 server rows, permission vs behaviour | 5.2, 5.3 |
| §7.3 writing-tools review, strict mode stated, running calls | 5.4 |
| §7.4 inherited setting, parent named, unknown sessions | 5.3, 5.5 |
| §8 Details order, links, review outcome first, honest Undo, pending/cancel | 3.1–3.4 |
| §9 states table | 2.3, 2.4, 3.4, 5.5 |
| §10 visual, keyboard, narrow, motion, performance | 6.4, 5.1, Part 1 Done, Part 6 Done |
| §11 facts the model needs | 2.2, 2.3, 4.2, 5.3, 6.3 |
| §12 prototype fixtures, scenes, test with the owner | 1.1, 6.5, 8.1 |
| §13 delivery boundaries, outside scope | Order, Non-goals |
| §14 completion criteria | Acceptance |
