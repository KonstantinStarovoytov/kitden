# Library: one page for what you have and what you can add

Date: 2026-10-20. Sketch the owner approved: https://claude.ai/artifact/RiUXBuAMAXD93vcwFbhMdh

## Why

Today Kitden has two pages for the same things. **Load map** shows what each client loads.
**Discover** shows plugins and skills you can add. The owner finds an item, opens it, and often
can do nothing with it: 85 skills on the Load map have no action, and 16 of 32 plugins have
none (9 from Codex, 5 from Cursor). What the owner wants is simple: "I have a plugin in one
client, let me use it in another." The page must be clear and obvious, with no dead ends.

Not everyone has all three clients. Columns for a client that is not on this computer are
noise. A client that is installed but not used is noise too.

## Goals

- One page, **Library**, in place of Load map and Discover.
- The action sits in the client's cell: "+ Add" in the Codex column adds to Codex.
- No dead ends. Every cell and every Details panel either has an action, or says in one line
  why not and what to do instead.
- Columns only for clients Kitden finds on this computer.
- The owner can hide a found client's column with "−" and bring it back.
- Categories stay: as a filter, and as quiet text in the row.

## Non-goals

- Copying an MCP server from one client to another. The gateway is the way to share servers.
- Adding hooks from anywhere.
- New marketplaces or catalogs. Library uses only the marketplaces already on this computer.
- Removing a plugin. Turning it off covers it for now; ROADMAP lists it under Later.
- Installing a plugin into Cursor. Cursor keeps installs in its own database, and Kitden never
  writes it.
- Changing Overview, Gateway, Changes or Agents, except links that pointed to Load map or
  Discover.

## Anti-goals (it fails even if it works)

- A busy page: more labels, badges or buttons than today's Load map row.
- A label that sits on a column border or in the middle of a row.
- A "+ marketplace" note in every cell, as if each add needs extra work.
- Any change to a client's settings outside preview → Apply with a backup → verify → Undo.

## The page

Top to bottom:

1. Title "Library" and one line: "What each client loads, and what you can add to it."
2. Kind tabs with counts, as on the Load map: MCP servers, Plugins, Skills, Hooks, Marketplaces.
3. On the Plugins and Skills tabs: a three-way choice **On this Mac · Can add · All**, and a
   category picker "All categories ▾". Other tabs show only what is on this Mac, so they have
   neither.
4. When something is hidden: one quiet line "Hidden: Cursor · Show".
5. When an add will bring in a marketplace first: one line above the table, once, for example
   "Codex gets the claude-plugins-official marketplace the first time you add one of its
   plugins." Never in the cells.
6. The table: an item column, then one column per shown client.

With **All**, rows come in two groups: "On this Mac" first, then "Not on this Mac yet".

## Columns

- A column for each client whose scan status is "found". Claude Desktop's Code tab stays
  inside the Claude Code column, as today.
- No client found: no table, an empty state that points to Overview (Overview already lists
  each client and says when one is missing).
- Each column header has a small "−" button ("Hide Cursor"). It hides the column on this page
  only. It does not change any client, the scan, warnings, Overview or Details.
- The choice is kept in this browser (localStorage, read and written inside try/catch). Another
  browser or phone shows all found clients until hidden there too.
- "Show" on the "Hidden: …" line brings back every hidden column.
- The last shown column cannot be hidden: its "−" is not drawn.
- A row that exists only in hidden clients is left out of the table and the counts.

## Rows

- Line 1: the name, then small gray text right after it: the category, and the source
  (marketplace) only when two rows share a name. Example: "figma  Design · openai-curated".
- Line 2: the description, one line, cut with "…".
- Everything sits left in the item column. No pills, nothing at the column border.
- Categories come from the marketplace entry, as Discover does today. A skill from a plugin
  shows its plugin's category. Skills of your own, MCP servers, hooks and marketplaces have none.
- Today 372 of 386 plugins here have a category; "Development" alone has 150.

## Cells

Each cell shows a state or one action. A button in a cell opens the review (preview) for that
one client straight away.

| Row | Client has it | Client can get it | Client can't take it, but… | Nothing possible |
|---|---|---|---|---|
| Plugin | Loads / Off (as today) | "+ Add" | "Add skills" (see below). Cursor and a Claude Code plugin: "Via Claude Code" (Cursor loads Claude Code's plugins) | "—" with the reason on hover and in Details |
| Skill | Installed / Via Claude Code / Via plugin | "+ Add" (copies the skill) | Skill needs its plugin: "Add the plugin" (opens that plugin's add review for this client) | "—" with the reason |
| MCP server, Hook, Marketplace | as the Load map today | — | — | as today |

"Add skills" is new. A client that cannot install a plugin can still use the skills inside it:

| Plugin from | Add skills to | Copy goes to | Also read by |
|---|---|---|---|
| Codex only | Claude Code | `~/.claude/skills` | Cursor, when Include Third-Party Plugins is on |
| Codex only | Cursor | `~/.cursor/skills` | nobody else |
| Cursor | Claude Code | `~/.claude/skills` | Cursor, when Include Third-Party Plugins is on |
| Cursor | Codex | `~/.agents/skills` | Cursor |

Cursor's own plugins sit in `~/.cursor/plugins/cache/<marketplace>/<plugin>/<version>/`; their
skills are in `skills/*/SKILL.md` there (checked on this Mac 2026-10-20: glean has 19,
superpowers 14, runlayer 3). When a plugin has several version folders, use the newest. The skill
list today reads only Claude Code and Codex marketplaces; it learns to read this cache too, so
Cursor's plugin skills also appear as rows on the Skills tab.

When the copy is also read by Cursor, and Cursor has the plugin itself, the review says so:
Cursor reads that folder too. Kitden's scan then shows what Cursor really loads.

A plugin with no skills inside (or none that work alone) has no "Add skills": its cell is "—",
and the reason says it has no skills to copy, or that they need the rest of the plugin.

"Add skills" is one review, one change, one Undo, copying every self-contained skill of that
plugin into that client. The review lists skills it leaves out and why. Skills the client
already has (matched by name, as the skill list does today) are skipped, not refused. When the
client has all of them, the cell shows "Skills added" instead of the button.

The same plugin name from two marketplaces makes two rows (figma from claude-plugins-official
and figma from openai-curated). If a client already has one, "+ Add" on the other stays, and the
review warns before Apply that the client will load both. Today's "loads it twice" warning
shows on both rows.

## Details

One Details panel for every row. It joins what the two pages show today:

- what each client loads and from where, with the on/off switches (Load map);
- description, what is inside, author, homepage (Discover);
- actions in the footer: the same rules as today's `footerActions`, plus "Add…" with client
  checkboxes to add to several clients in one review (today's Discover form).

A row with no possible action says why in one line at the top of Details.

## Search and filters

- The top search box searches the Library: names on every tab, and names and descriptions for
  plugins and skills (today's Discover scoring).
- Search keeps the current tab and choice. When the choice hides matches, one line says so:
  "3 more not on this Mac · Show all".
- Load map's "Needs attention" stays, as a small toggle shown only when there is something to
  attend to.
- Load map's "Differs between clients" goes away: the columns show it already.

## What moves

- The nav shows "Library" where "Load map" and "Discover" were.
- Old addresses keep working: `#map` opens Library on "On this Mac", `#discover` on "Can add".
- Overview's links to items open them in Library.
- "Add a marketplace…" moves to the Marketplaces tab.
- `+ Add` in a project view adds for the user (all projects), as Discover does today, and the
  review says so.

## Constraints

- Every change: preview → Apply with a backup → verify → Undo. "Add skills" too.
- Main page: name, client, action. Paths, addresses and commands stay in Details.
- Look and motion follow docs/design.md; update its table section for the new row and cells.
- Tests use sandbox homes. Run `uv run pytest -q`, `uv run ruff check .` and
  `node --test tests/frontend/*.test.mjs` before each commit.
- Update ROADMAP.md, README screenshots and text in the same change set.
- Check in a browser on a sandbox home (fixtures plus the public marketplace copies), never the
  real home folder.

## Calls I made (the owner can change them)

- Library opens on "On this Mac" (today's Load map view); the sketch showed "All".
- "Differs between clients" is removed.
- A cell's "+ Add" goes straight to the review for that client; adding to several clients at
  once lives in Details.
- Hidden columns are kept per browser, not on the server.
- Category text comes before the source on the name line.
- MCP servers get no "+ Add"; sharing them goes through the gateway.
- After "Add skills", copied skills are matched to the plugin by name; no extra record.
- A same-name plugin from another marketplace can still be added; the review warns.

## Left to the builder

- Data shape: one new endpoint or the current three (`/api/map`, `/api/catalog`, skills).
- How rows from the map and the catalog are matched (plugin id `name@marketplace`, skill name).
- Exact cell words for "Off" and the tooltips, within the anti-goals.
- Column widths for one, two or three clients.
- Keyboard: today's row focus and `tabKeys` rules apply to the new controls.
