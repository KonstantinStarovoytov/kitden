# Map pages: building the final design

Date: 2026-10-23. Baseline `d8c05cc` (main, with Parts 1–3 of the visual plan built).
Status: written for the owner's review. The plan follows it.

Sources:

- The owner's final design, [visual-redesign-final-2026-10-23.md](../../research/visual-redesign-final-2026-10-23.md),
  with its frames in `design/kitden.pen`. Frames are cited by name, such as "D3".
- The 2026-10-22 design, [2026-10-22-visual-management-design.md](2026-10-22-visual-management-design.md).
  Its Parts 1–3 are built. This design replaces its Parts 4–6; Parts 7 and 8 stay.
- Walkthrough 1, [walkthrough-2026-10-23.md](../../research/walkthrough-2026-10-23.md).
- Two code surveys of 2026-10-23, kept with the plan and not in the repository.

## Why

The owner drew the pages after walkthrough 1. Each page is one tree you can unfold:

- Gateway: clients → gateway → servers → tools.
- Library: clients → plugins and skills by source → what a plugin holds.
- Instructions: clients → files → imports.

A link is the state. Details sits beside the tree and holds the facts and the actions. A List
view shows the same data, for the keyboard and for large setups.

This design turns the frames into three parts that ship one by one. It also says plainly where
the code or the clients cannot do what a frame shows. The three requirements stay: the page is
simple and visual, it opens fast, and it is secure and local.

## Owner decisions (2026-10-23)

- Cells and Details say **"On"**. It replaces Part 2's "Available".
- Tool switches say **"On" and "Off"**, not the frames' "Allowed" and "Blocked": "3 of 4 on",
  "Turn on for all projects…", "On in this project".
- **The Differences filter and Add missing stay, in the List view.**
- **Sign-in (S1) waits.** Everything else is built first. No "Sign in needed", "Sign in…",
  "Signed in there" or "Sign in after Apply" for now.

## Owner decisions (2026-10-24, the mockup)

The owner tried a clickable mockup of these pages, [docs/mockup/kitden-motion.html](../../mockup/kitden-motion.html),
and wants the product to look, move and behave like it, "as close to the mockup as possible, and
not fragile". The owner accepted every call in the
[alignment plan](../plans/2026-10-24-mockup-alignment.md) (D1–D28). Where this design says
otherwise, the mockup wins, with these exceptions:

- **The mockup wins on look:**
  - Inter and JetBrains Mono, shipped as local files.
  - Icons from one icon data module (`static/js/icons.js`), drawn by `icon()` with createElementNS, no innerHTML.
  - The mockup's tokens and sizes, and a small spring overshoot on presses, switches and ports.
  - Details floats over the map.
  - The mockup's lamp meanings, words, grey dotted links that skip the gateway, and timings.
- **The mockup wins on behaviour:**
  - A preview tray holds several changes, with Apply all and Undo all.
  - A click on a preview block takes it out of the tray.
  - Several projects can be ticked at once.
  - A free client drags a wire to the gateway.
  - A project switch keeps the panel and the tray.
  - The Gateway server panel has tool switches; a switch only adds a tray row.
- **Kitden's own rules stay:**
  - A tray row keeps "Show changes", so the full review is one click away.
  - A check shows only after `verified`.
  - Redo and Overview's buttons add a preview; they never write at once.
  - No sign-in words until S1.
  - No word or count Kitden does not know.
  - No switch for one item inside a plugin.
  - Cursor is never a plugin drop target.
  - Import links only for Claude Code.
  - Every action today's pages have stays reachable.
  - Calm only; nothing loops.

The Non-goals "no drag to connect" and "a new font" give way to this. The rest of this design
stands where the mockup is silent.

## What changes from the 2026-10-22 design

| Old part | Now |
| --- | --- |
| 4 Compare: the Library matrix, Differences, project exceptions, Add missing | **Part 5.** The Library List view keeps Differences and Add missing in four groups. The "N project exceptions" line becomes the map's "This project" tag. |
| 5 Access: the route diagram, tool origins, honest reviews | **Part 4**, the Gateway map and list. These carry over: tool origin, the effective state, "Use the shared rule…", the strict words and call counts. These go: the route diagram, "+N more" and "Direct, never amber". The writing-tools checklist and the list of rules for lost folders move to Part 7. |
| 6 A setup map on Overview | **Part 6.** Overview gets attention cards and a small "Your setup" tree. There is no separate map page. |

## Goals

- One tree on each page, with the same rules everywhere: small blocks, unfold on click, the link
  is the state, and Details holds the actions.
- The List view answers every question the map answers, by keyboard, and it is the first view of
  a large setup.
- An add or a move started on the map shows a preview on the map. It still goes through
  preview → Apply with a backup → verify → Undo.
- Words say only what Kitden knows. No tool count before a server is added. No "off in one
  project" where the client has no such switch.
- The page opens as fast as today. The only new data at start is a short tool list per held
  server.

## Non-goals

- Sign-in (S1), the "server for chosen clients" frame (Later), and marketplace sources beyond
  this computer, such as the MCP Registry.
- Turning one skill off in one project for Codex or Cursor. Their docs give no such switch
  (checked 2026-10-23).
- A graph editor: no free placement and no drag to connect. A drag only starts a preview (D5).
- Every marketplace plugin on the map.
- A new font. The frames use Inter; the page keeps the system fonts (design.md).

## Anti-goals

These count as failure even if the page works:

- A link or a filled mark that says "on" when Kitden does not know.
- A preview on the map that is not a real preview. The review bar always comes from a preview
  request, and the full review is one click away.
- Starting a marketplace server, or asking one for its tools, before Apply. There is one
  exception, the sign-in check a move already makes: one `initialize` request to a remote
  server's own address, with no secret, sent only after the person picks that server. A move of
  a server the person already uses keeps today's preview, which may read that server's tools.
- A grip or a "+" that promises an add the preview will refuse for a reason Kitden already knows.
- Lines that move while idle, a map that rearranges itself, or a task that only the map can do.
- A slower start.

## Constraints

- `AGENTS.md` in full:
  - simple English in code, UI and docs, and Russian with the owner;
  - tests on sandbox homes, and the checks before each commit;
  - dated facts about other tools;
  - short plain commit messages.
- The stack does not change, and nothing new is added at runtime. The CSP stays strict and no
  library comes from another site, so the map is plain SVG under HTML blocks.
- `docs/design.md` changes in the same commit as the page change it describes. New words are
  pinned in `tests/unit/test_page_words.py`.
- `explain()` and `project_views()` also feed the read-only MCP server. Imports and file lines
  never go into its answers.
- `ROADMAP.md` has an uncommitted edit by the owner. While `git status` shows it, no part edits
  it; each part writes its roadmap lines into its report. A part never edits or stages the
  owner's design and research files.

## Shared pieces

Part 4 builds these; Parts 5 and 6 use them.

**S.1 Words.** One pass through the two word tables (`STATE_WORDS` and `ORIGIN_WORDS`, in
`views/words.py` and `parts.js`):

- **"On"** replaces "Available" everywhere: cells, Details, After chips, Instructions and the
  README.
- **"This project"** is the tag for a rule or definition that only one project has and that
  differs from the shared setup: today's "project override", and a tool or server rule of one
  project.
- **"Only this project"** is for an item that only one project has (today's "this project"). The
  item sits under the group "Only this project", and its Details says "Only this project ·
  <folder>".
- "this project" changes meaning, so the rename goes through the tables, and both words are
  pinned in one commit. A plain find-and-replace would swap the two meanings.
- **Tool words:**
  - "On", "Off", "N of M on", "On in this project";
  - "Turn on for all projects…", "Turn off in one project…";
  - "Use the shared rule…", or "Use <folder>'s rule…" when the rule it falls back to belongs to a
    parent project.
- **"Via Claude Code"** keeps today's meaning: Cursor does not have the item yet and will get it
  once Claude Code has it. The cell shows a hollow mark.
- **Cursor loading an item through Claude Code.** Cursor's cell says "On" with a filled mark. The
  route goes in the hover text, and the map draws a faint link. L3 draws "Via Claude Code" here,
  but walkthrough 1 (F5) asked to keep the route out of the cell, and "On" is the true state.
- **Where an item applies** now shows by tags and groups:
  - Part 2's scope word on every cell of a project view ("· all projects", "· this project")
    goes. Cells that follow the shared setup carry nothing, and the scope bar says so.
  - In a project view, a cell whose state comes from the project's own settings carries the
    short accent tag "This project". On the map, the block carries it when any client's state
    does.
  - Items only that project has sit under the group "Only this project".

  This still answers walkthrough 1's F3, client by client.

**S.2 Tokens.** `style.css` gains `--dim`, `--preview-fill` and `--preview-line`, with the
values of the frames' `kd-dim`, `kd-preview-fill` and `kd-preview-line`. Every other `kd-*` token
maps to a token that exists.

`kd-faint` fails 4.5:1 as text in both themes, so it is used only for icons, grips and hollow
marks. Text that a frame paints `kd-faint` uses `--ink-3`. In the light theme, `kd-ok` text keeps
today's success text color. `tests/unit/test_contrast.py` keeps holding 4.5:1.

**S.3 Details beside the page.** On Gateway, Library and Changes, in a window 1024 px wide or
more, Details is a 320 px column beside the map or the list instead of a modal drawer:

- no scrim, and the page stays usable;
- Escape closes it, and focus goes back to the block that opened it;
- in a narrower window, and on Overview, it stays today's drawer.

Its layout follows the frames:

- the kind and Close;
- the title and the id;
- a Facts block of labels and values;
- one explanation sentence;
- stacked actions;
- "Technical details ›", folded, at the bottom.

Part 3's order (`DETAILS_ORDER`) stays: the Facts carry the state, where it comes from and the
clients it affects, and the explanation sentence is the Why. A review opens in the same column.

**S.4 The map core.** One module, `map.js`, holds:

- a pure layout that turns a tree model, the open block and the width into block positions and
  links;
- a renderer that draws HTML blocks over one SVG of links.

The rules:

- **Columns and blocks.** Columns sit at fixed x positions. Blocks are 150–200 px wide and
  34–54 px high (the Components frame). A folded block shows its count.
- **Unfold.** One block per column is open at a time. Opening a block draws its links, then fades
  its children in 15 ms apart, with no extra delay after the sixth. The whole unfold takes at most
  300 ms. With reduced motion, the end state shows at once.
- **The link is the state.** On is a link and a filled mark. Off is no link and a hollow mark.
  The map shows no state word; Details says it.
- **Selection.** Selecting a block lights its path from every client that reaches it, and opens
  Details. (D3 lights only Claude Code although Codex reaches the tool too.)
- **Keyboard.** Every block is a button, in reading order, column by column. Enter opens or
  selects; Escape clears.
- **Width.** In a wide window, children unfold to the right. Under 1024 px, or with Details open
  under 1280 px, they unfold down inside the parent on a rail, and the gateway is a small house
  tile (N1).
- **Rest.** Nothing moves while idle. A link draws once when it appears; after an Apply, only after
  `verified`.
- **Long names** are cut with "…" (`cutName`). The full name is in the hover text and in Details.

**S.5 Map or List.** A Map | List switch sits in the page head, and the address keeps the choice
(`view=map|list`). With no choice in the address, a page opens in List when its middle column
would hold more than 15 blocks: servers on the Gateway, plugins and skills in the Library.
Otherwise it opens in Map.

List is a tree grid:

- group rows, and rows that fold;
- the arrow keys move, Right opens a row and Left closes it;
- Enter opens Details.

**S.6 Find.** On a map page, the top search finds things on that page (F1):

- matches light up, and everything else dims to 35%;
- a folded parent opens to show a matching child;
- a chip says "N matches", and Escape clears.

On Overview and Changes the search keeps today's behavior.

**S.7 Project picker and scope bar.** A menu replaces the native select (P1):

- "Find a project…" at the top;
- "All projects", with "What applies in every project";
- then each known project, with its count of own rules ("1 own rule") when it has any, and no
  paths.

Arrows, Enter, Escape and typing to filter all work.

Under the page head a scope bar says either "Shared setup · project overrides stay separate"
with All projects, or "Project <name> · N rules differ from the shared setup". The scope bar
counts the page's own rules; the picker shows the total.

**S.8 Apply on the map (A1–A3).** A preview started on the canvas, by a drag or a marketplace
result, shows on the map:

- a preview block (a `--preview-line` border on `--preview-fill`) and preview links;
- a review bar on the canvas, with the title and its scope, one outcome line, Cancel, Apply, and
  "Show changes", which opens the full review in Details.

While applying, the Apply button counts the steps ("Applying 2 of 3") and the bar says what is
being written ("Writing Claude Code's settings. A backup is kept."). Cancel stays visible but
waits.

Only after `verified` does the block turn solid. The new link then draws once, and a toast offers
Undo.

An error stays in the bar until the next action. It says "Nothing was changed." when no file was
written or the engine put every file back. "Try again" makes a new preview, and focus goes to it.

A review opened from Details follows the same steps in the Details column.

## Part 4. The Gateway map and list

Frames: D1–D5, G1, P1, F1, R1, N1, T1 and A1–A3, with S.1–S.8.

**4.1 Probe first.** This is the design's "Before code" step.

1. Build the map core (S.4) and draw D1 and D2 from today's `/api/gateway-view`, on the medium
   sample with direct servers added up to 20.
2. Measure the time to the first usable view and to complete data, against today's Gateway page
   on the same sample and the same machine:
   - `scripts/measure-start.py` also times `/api/gateway-view`;
   - the page sets a performance mark when the map is drawn, which the controller reads in a
     browser on both versions.
3. The probe passes when drawing the map takes under 50 ms on the 20-server sample, and the
   layout of the large sample takes under 16 ms in a node test. If it does not pass, the part
   stops and the owner gets the numbers.

**4.2 Data.** No new request at start.

`/api/gateway-view` gains, for each held server:

- a short tool list: name, title, state, hint, `origin` and `origin_from`;
- the count of tools that are on, along the picked project's chain.

A tool's state includes its server's switch: a tool of a server that is off is off, and its
Details says "Server off".

Origins come from old Part 5 Task 1: all projects, this project, a parent folder, on by default,
or new and waiting (strict). Old Part 5's `columns` rule also comes in: the Code tab of Claude
Desktop counts as Claude Code.

Each project gets a count of its own rules, for the picker and the scope bar. With All projects
picked, a held server that is off for all projects but on in some says "On in N projects".

A registered gateway (Obot or MetaMCP) is its own gateway block, under Kitden's, with its
server count. It unfolds to its servers, without tools, and its Details keeps today's actions.

**4.3 Gateway List (G1).**

- Groups: each gateway's "Remote" and "Local" servers, then "Outside the gateway · calls skip
  Kitden's rules".
- Columns: Name; Used by (client tiles); Tools ("3 of 4 on"); Action. The action is ›, or
  "Move in…" on an outside row that a move can take.
- Under an open server, its tools: a mark, the name, and the tag "Read" or "Write" from the hint.
- Part 5 adds "Add missing servers…" here, once the four-group review exists (5.4). Until
  then, today's Add missing stays on the Library's MCP servers tab.
- There is no Differences filter here. The "Used by" tiles show who has each server, and "Add
  missing servers…" covers what is missing.

**4.4 Details.**

- **Tool.** Facts: Server (name · Remote or Local), State ("On", "Off", "On in this project" or
  "Off · server off"), Comes from, Reported ("Read only", "May write" or "Not reported"),
  Clients, and Calls ("12 calls · last today 14:02"). Then the explanation sentence. Actions:
  - turn on or off for all projects;
  - turn on or off in one project, with a project choice in the column that starts from the
    picked project (walkthrough F10);
  - "Use the shared rule…" when the project has its own rule.
- **Held server.** Facts: Kind, State, Tools ("N of M on"), Clients, and Projects with their own
  rules. Today's actions move here: on and off for all projects or in one project; Strict, whose
  review names the tools it keeps on and says a new tool waits (old 5.4); "Turn off every writing
  tool…" (unchanged); Refresh tools; Remove and Put back; and the Keychain actions.
- **Outside server.** The per-client Details that the Library's MCP rows have today: "+ Add to
  <client>…", Remove, and "Move into the gateway…" (or "Remove direct entry…" when no gateway can
  take it). It is built from the gateway-view rows and `/api/explain`, not from the 225 KB
  `/api/map`.
- **Client block.** Facts: version and the `kitden` entry's state. Actions: "Set up in
  <client>…", turning that entry back on when the client has it off, and "Open <client>".
- **Gateway block.** Facts: clients, servers and rules. Actions: "Move all N…" and "Add another
  gateway…" (Obot or MetaMCP).

No action today's Gateway page has is lost. Each one moves into one of these Details.

**4.5 Gateway map (D1–D4, R1, N1).**

- **Columns:** Clients, Gateway, Servers, Tools.
- **Clients** say "Connected" or "Not connected", from the `kitden` entry. On a first run they
  say "Found · <version>".
- **The gateway node** shows its counts of clients and servers. On a first run it is a
  preview-style slot, "No gateway yet", with "Set up…" (R1).
- **Held servers** are grouped Remote and Local, and folded with their tool count. A group with
  more than 6 servers shows 5 and a block "N more", which opens List at that group.
- **Outside servers** are in their own group with "In <client>", joined to each client that has
  one by a faint amber elbow line.
- **Grips.** A grip shows only on an outside row that a move can take, by the checks the preview
  runs without the network: not a plugin's server, not one in a project's own file, no `${…}`
  value. OAuth is found only at preview, and the bar then says why.
- **In a project,** a tool rule of its own carries the tag "This project". So does an outside
  server whose definition the project replaces with its own (the `docs` override in Atlas). A
  held server that only this project turns on carries "Only this project".

**4.6 Drag a server in (D5).** Drag an outside block onto the Servers column. A slot, "Drop to
add", opens in its group. Dropping shows the same preview as "Move into the gateway…" (the
`gateway.move` action into Kitden), through S.8. "Move in…" in the List and "Move into the
gateway…" in Details do the same by keyboard.

Done:

- node tests for the layout (20 and 157 servers), lighting, folding and the narrow layout;
- page tests for the List keyboard path and the Details facts, and one that a drag's preview
  equals the Move preview;
- the probe's numbers in the part's report;
- the words pinned, and design.md's Gateway section rewritten.

## Part 5. The Library map, list and marketplace adds

Frames: L1–L4 and D6, with S.1–S.8.

**5.1 Read what the map shows.** These are also bugs today. Each task checks first.

- **Claude Code's project local settings.** Read `<project>/.claude/settings.local.json`:
  - its `enabledPlugins`; local wins over project, and project over user;
  - `skillOverrides` in every settings file (user, project and local). A skill set to `"off"`
    shows Off.

  Checked 2026-10-23 against code.claude.com/docs/en/settings and /en/skills. The docs do not say
  whether `skillOverrides` merges key by key across files. Kitden reads it key by key, as
  `enabledPlugins` merges: the most specific file that sets a skill's key wins. The code comment
  says that this part is not checked.
- **What an installed plugin holds.** Run `catalog._inside()` on the installed folder: Claude
  Code's `installPath`, Codex's cache and Cursor's plugin folders. Cache the result by folder
  signature. It gives the plugin's skills, commands, agents, hooks and MCP servers, by name.

**5.2 Tabs.** The Library has two tabs, "Plugins and skills" and "Instructions" (Part 6).

- MCP servers move to the Gateway, which shows outside servers and their per-client Details
  (4.4).
- Hooks show as items under their source, with the kind word "Hook".
- Marketplaces are the source captions. A caption opens the marketplace's Details (update,
  remove), and the add panel has "Add a marketplace…".
- Old links (`kind=mcp_server`, `kind=hook`, `kind=marketplace`) land in the new place.

**5.3 The tree.** Clients → sources ("<marketplace>", "Your skills", "Your settings", "Only this
project") → plugins and skills → what a plugin holds.

- **What shows.** Only what is on this computer and present in some client. A marketplace plugin
  that no client has shows only in the add panel and as a preview.
- **Plugin meta** counts what the plugin holds ("4 items"). It never says "N of M on": a part
  follows its plugin, because Claude Code has no switch for one skill inside a plugin (checked
  2026-10-23).
- **Links.** A client is linked to each plugin or skill it loads. A faint line means Cursor
  loads it through Claude Code. The "Via Claude Code" state (not loaded yet) draws no link. In a
  project, the tag "This project" marks an item whose state there comes from the project's own
  settings.

**5.4 Library List (L3).**

- **Rows and cells.** One row per source group, plugin and skill. A plugin folds and has child
  rows for its parts. There is one column per client. A cell says "On", "Off", "Via Claude Code",
  "+ Add", or nothing.
- **Filters.** Installed | Differences (hash `show=diff`). "New" and "All" give way to the add
  panel, and so does the category filter. The "Needs attention" filter stays, because Overview
  links use it.
- **Differences** shows the rows whose cells differ between the found clients: On next to empty,
  Off next to On, Needs review, Unknown, or a cell kept from the last good read. A plugin row
  differs when any of its child rows differs.
- **Add missing.** "Add missing plugins and skills…" opens one review in four groups, as old 4.3
  set them out: Will add, Already there another way, Needs your decision, and Kitden cannot add.
  It works in a project and in All projects. "Add missing servers…" on the Gateway List uses the
  same review.

**5.5 Skill and plugin actions (L1, L2).**

- **Claude Code, a skill not in a plugin:**
  - "Turn off for all projects…" sets `skillOverrides.<name> = "off"` in `~/.claude/settings.json`.
  - "Turn off in one project…" sets the same key in `<project>/.claude/settings.local.json`. It is
    offered only while the user settings have no `skillOverrides`, unless the docs confirm (with a
    date) that it merges key by key.
  - "Use the shared rule…" removes the project's key.
- **Claude Code, a skill inside a plugin:** "Turn off <plugin> in this project…" sets
  `enabledPlugins` in the project's local settings. Details says why one skill cannot be turned
  off on its own.
- **Codex:** "Turn off for all projects…" adds `[[skills.config]]` with its `path` and
  `enabled = false` in `config.toml`. There is no project switch, and Details says so.
- **Cursor:** no switch. Details says "Cursor has no switch to turn off one skill."
- Every all-projects change says when a project keeps its own rule (`project_keeps` from old
  Part 4). A project file that has its own `skillOverrides` is named in that review too: "<folder>
  has its own skill settings; it may keep this skill on."

**5.6 Add from a marketplace (L4, D6).** "+ Add" beside the middle column's caption opens the add
panel in Details. The panel has:

- a search over the marketplaces on this computer;
- a filter by marketplace;
- results grouped by marketplace.

What the results are:

- **In the Library:** plugins and skills, from today's catalog and skill catalog.
- **On the Gateway:** the MCP servers declared by marketplace plugins whose folder is on this
  computer (`mcpServers` in `plugin.json`, or `.mcp.json` / `mcp.json`). A result says Remote or
  Local, and "In the gateway" or "Added" when it is already there.

A result never shows a tool count: Kitden learns a server's tools only by asking the server, and
it never does that before Apply. Clicking a result, or dragging it onto the map, shows the preview
on the map (S.8).

Which clients an add reaches:

- **A click** previews an add to every client that can take the item, in the scope that Part 2's
  add rules give for the picked project.
- **"Show changes"** opens the full review, which keeps today's client choice (`offer.js`), so a
  client can be left out there.
- **Dragging a result onto one client block** adds a plugin or skill to that client only. A
  gateway server always goes into the gateway, which every connected client reaches. A drop on a
  client that is not connected yet also connects that client.
- **By keyboard,** Enter on a result is the click.

For a remote server, the preview makes the sign-in check a move makes (`needs_sign_in`): one
`initialize` request to the server's own address. Unlike a move, it sends no headers at all. A
local server is never started.

**A new action, `gateway.add`,** builds the Kitden gateway's entry from the marketplace entry, the
way a move does. Secrets go to the Keychain, as in a move. It refuses, with the reason:

- a server that signs in with OAuth ("signs in with OAuth; it waits for sign-in");
- SSE or WebSocket;
- any `${…}` value, a relative path, or a bundle;
- a name the gateway already holds, or one a client has directly (it offers Move instead).

The demo marketplace gains two servers it can add: one at an address and one that runs a
command.

Done:

- tests for each read fix on sandbox homes, and for each action's steps and Undo;
- the four groups on the medium sample;
- `gateway.add`'s refusals;
- node tests for the tree layout and Differences;
- design.md's Library section rewritten.

## Part 6. Instructions, Overview and Changes

**6.1 Instructions (I1).** This is the Library's second tab: clients → files → imports.

- **Files.** They are grouped "All projects" and "Only this project · <folder>", one block per
  file path, with the clients that read it. Cursor's rules fold by folder. I1 captions the
  project group "This project", but a project's files are items only that project has (S.1).
- **Imports.** Claude Code's `@path` imports are read from its CLAUDE.md files and shown under
  "Pulls in". A path is relative to the file, and `~` works. Imports nest up to four hops. Code
  spans and fenced blocks are skipped. (Checked 2026-10-23, code.claude.com/docs/en/memory.)
- **An import outside the project** says "Claude Code may ask before it reads this."
- **AGENTS.md.** Claude Code reads AGENTS.md when a project has no CLAUDE.md (v2.1.277 and later,
  same check), so "Read by" names Claude Code too.
- **Codex and Cursor** have no imports (checked 2026-10-23).

The tab only reads. Details shows the size ("42 lines"), "Compare across clients" and the
Technical details fold (the path and the first lines). Imports go to the page only, never into
the MCP server's answers.

**6.2 Overview (O1).** The title is "Your setup, connected.", with a lede that gives the counts.

On the left are the "Needs attention" and "Can improve" cards, one per item. Each card has an
icon, the name, one line on why, the client tiles and one action. A server that skips the gateway
gets its own card, up to three; after that, one card, "N more servers skip the gateway", opens
the outside group of the Gateway List. Notes with nothing to fix stay folded ("Show N notes").

On the right, "Your setup" is a small fixed tree:

- client blocks with their versions, with "not tested" marked;
- a Kitden gateway block ("N servers · M tools") and a Library block ("N plugins · M skills");
- links for what each client uses, faint for "Via Claude Code";
- under it, "N projects · K have their own rules".

A block opens its page. A client opens the Library with that client's items. There is no
sign-in card until S1.

**6.3 Changes (C1).** One timeline per day ("Today", "Yesterday", then the date). Each change has
a dot on the rail, its time, title and client tiles, a state word and Undo. Undone and cancelled
rows step back.

Details opens in the column. Its Facts:

- Project;
- State: "Applied and checked", "Undone", or "Not applied: the file changed first";
- Backup: "Kept · Undo puts it back";
- Takes effect, per client, such as "Codex: start a new session";
- Clients;
- History: "14:02 Preview → 14:02 Applied → 14:02 Checked".

Its actions are Undo and "See it on the map". "See it on the map" opens Gateway or Library with
the item selected, or says "This item is no longer there." when the change removed it.

**6.4 Walkthrough 2.** The owner may try the seven tasks again on the new pages. The agent writes
the script and records the results, which feed Part 7.

Done:

- tests for import reading (relative paths, `~`, hops, fenced blocks, loops);
- page tests for the Overview cards and tree, and for the Changes timeline and Details;
- "See it on the map" for a removed item;
- the walkthrough 2 script.

## Order

4 → 5 → 6 → (walkthrough 2) → 7 → 8. Part 4 builds the shared pieces, and Parts 5 and 6 use
them.

- **Part 7** also takes the writing-tools checklist (old 5.4), the rules for folders Kitden no
  longer finds (old 5.5), the deferred items from the Parts 1–3 ledgers, and any frame these parts
  leave out.
- **Part 8's tour** follows the new pages:
  - the Gateway map with a tool selected;
  - the Library with a skill two clients share;
  - a project view with "This project";
  - Add missing in the List;
  - Undo on Changes.

## Calls the owner did not make

The owner can change any of these:

1. Hooks become items under their source, marketplaces become source captions, and MCP servers
   live on the Gateway only. The frames give hooks and marketplaces no place.
2. Add missing covers plugins and skills in the Library List, and outside servers in the Gateway
   List.
3. Marketplace plugins that no client has show only in the add panel. Drawn on the map, the
   official marketplace alone would be over a hundred blocks.
4. A plugin's meta counts its parts and does not say "N of M on".
5. "Turn off in one project" is offered only for Claude Code skills that are not in a plugin. A
   skill inside a plugin offers turning the plugin off in that project.
6. Cursor's cell says "On" when Cursor loads an item through Claude Code. L3 draws "Via Claude
   Code" there; that word keeps today's meaning (Cursor will get it once Claude Code has it).
   Walkthrough F5 asked to keep the route out of the cell.
7. Every client that reaches a selected tool lights up, not only one as in D3.
8. Details docks at 1024 px and wider. The drawer stays below that and on Overview.
9. List opens first past 15 blocks. The choice stays in the address and is not saved.
10. The system fonts stay, and `kd-faint` is used only for things that are not text.
11. A held server's Details holds strict mode, Remove, Put back, the Keychain, Refresh tools and
    the writing-tools batch. No frame shows it.
12. A registered gateway (Obot, MetaMCP) is its own gateway block.
13. With All projects picked, a held server that only some projects turn on says "On in N
    projects".
14. Marketplace results show no tool count.
15. Previewing a remote marketplace server makes the one sign-in check a move already makes.
    Without it, most hosted servers would be added and then fail.
16. A click in the add panel adds to every client that can take the item; the full review can
    leave a client out; a drag onto a client adds to that client only.
17. In a project, a cell whose state comes from the project carries "This project"; other cells
    carry no scope word.
18. `skillOverrides` is read key by key, like `enabledPlugins`. The docs do not say; the comment
    says "not checked".
19. Client blocks and the gateway block open Details with the Gateway actions no frame shows.
20. The Gateway List has no Differences filter.

## Left to the builder

- Exact copy, within design.md's voice. Use the frames' copy where it fits.
- Layout numbers, within the frames' sizes.
- The demo marketplace's new servers.
- The order of tasks inside a part.
