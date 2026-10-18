# Portal UI and UX design (proposal)

Visual identity update (2026-10-18): [Quiet Den + Graphite](../../../DESIGN.md) supersedes the original palette and placeholder mark. Layout and behavior guidance below remains historical context.

Status: proposal for the owner, 2026-10-17. Clickable mockup with test data:
[docs/design/portal-mockup.html](../../design/portal-mockup.html). Research behind it:
[design skills and tools](../../research/design-skills-and-tools-2026-10-17.md).

## Who and why

One developer who uses Claude Code, Codex and Cursor every day across many projects. They open the
page when an agent behaves oddly ("why does it see this tool?"), after installing something, or
before changing setup. They want an answer in seconds, then go back to the agent.

The page must answer three questions, in this order:

1. Is anything wrong? (duplicates, things going around the gateway, unknown state)
2. What does each client load here, and where does it come from?
3. How do I change it safely?

**Feel:** a calm, precise control panel. Quiet structure, one accent colour, nothing decorative.

## Problems with the current page

One long scroll with every section at once; a 188-row table with raw paths; machine words
(`mcp_server`, `user`); findings and gateway notes mixed together; sideways scrolling.

## Structure

A narrow left rail with four places, plus one setting:

| Place | Job | Focal element |
| --- | --- | --- |
| **Overview** (home) | "Is anything wrong?" | The heading counts what needs attention; each problem is one card: a short title, one sentence that says why it matters and what to do, and one filled button that names the action. No file paths: they live in the detail panel. Notes that need no action are folded away |
| **Load map** | "What loads where?" | A table: items in rows, the three clients in columns. Tabs for MCP servers, plugins, skills, hooks, marketplaces. Filters: All, Needs attention, Differs between clients |
| **Gateway** | "Do my clients use the gateway?" | A wire per connected client, then the servers not connected to it, one row per server with the clients that have it, in three groups: can move in, must stay on this Mac, comes with a plugin |
| **Changes** | "What did I change? Undo it" | A timeline: Undo on active rows, undone rows greyed out, the whole row opens its details |
| Agents (rail footer, "Let agents read this setup") | Add the read-only MCP server | One card per client |

The rail counts only what needs attention and the changes still in effect.

Two controls are always at the top: **Project** ("No project (global setup)", or one project by
its folder name with the short parent path) and **search** (`/`).

## Key components

- **Socket** (the signature): every client cell shows state three ways at once: a shape (filled =
  loads, hollow = off, square = via gateway, dashed = unknown, faint = not installed), a colour,
  and a word, plus a short scope written after a dot ("Loads · everywhere", "Off · this project",
  "Loads · via Claude Code"). Never colour alone. Slashed = overridden appears only in the detail
  panel, where each definition is shown. The cell is the one signal for its state: no extra badge
  or count repeats it.
- **Detail panel** (right side, opens on row click): the item, where it loads, and a **layer
  stack** per client: every definition in order, which one wins (a neutral tint) and why. A
  warning names the fix ("Cursor loads it twice. Turn one copy off to keep the other."); the
  action that does it is the primary button in the footer, the other actions and Commands… wait
  under More.
- **Review panel**: the same right-side surface. Title says the change in words ("Turn off
  superpowers in Claude Code"), then the result per client in sockets ("After: Claude Code ● Off
  · Cursor ● Loads once"), the masked diff and the client command folded under "Show file
  change", and an "After you apply" checklist (restart, reload). Buttons: one Cancel, Apply.
  Nothing is written before Apply.
- **Undo toast** after Apply: what changed, what to do next, and an Undo button. Undo is also in
  Changes. No "Are you sure?" dialogs: every change has a backup.

## Visual system

| Decision | Value | Why |
| --- | --- | --- |
| Density | 4 px grid; 13 px text; 34 px rows; 12–16 px padding | A working tool, read at a glance |
| Type | System UI font; monospace only for names, paths and diffs | Native and offline (no CDN); mono marks things you can copy |
| Scale | 11 / 12 / 13 / 17–18 px; hierarchy by weight and colour more than size | Calm, dense |
| Depth | Borders only, low-opacity lines; one shadow for the side panel | Structure without noise |
| Colour | Neutral greys; one accent for the gateway route; green = loads, amber = needs attention, red only in diffs | Colour always means something |
| Themes | Light and dark, following the system, with a switch | Both are first-class |
| Motion | See "Motion" below | Stylish where it explains something; instant where it would slow you down |
| Clients | Neutral monograms CC, CX, CU, not brand logos | No brand look-alikes |

## Motion

Owner request (2026-10-17): modern, stylish animation. Rule (Emil Kowalski's design engineering
skill): animate only where it explains a change; never slow down things done many times a day.

| Moment | Animation | Why |
| --- | --- | --- |
| Theme switch | The new theme spreads in a circle from the button (View Transitions) | Rare action; a moment of delight |
| Apply | Button: "Apply" → spinner "Applying…" → a check draws "Applied"; then the panel leaves | Shows progress and success in place |
| The change lands | The changed cell's dot drains or fills, its words blur across, a soft ping; counters roll (3 → 2) | You see the effect where it happened |
| Undo toast | Slides up; a thin line counts down the undo time and pauses on hover | Shows how long Undo is offered |
| Gateway | Dashes flow along each client's wire into the gateway | Shows that traffic goes through one place |
| Tabs | One underline glides to the chosen tab | Keeps your place |
| Page change | Short fade with a small rise | Soft, not slow |
| First visit to a page | Cards rise in, 45 ms apart, once | Calm entrance; later visits are instant |
| Side panel | Slides in with an iOS-like curve; its sections follow 40 ms apart | Spatial: it comes from the right |
| Rescan | A thin line sweeps under the top bar | Something is happening |
| Hover, filters, keyboard (Esc closes the panel) | Instant or colour only | Done many times a day |

Values: ease-out `cubic-bezier(0.23, 1, 0.32, 1)` for entering, ease-in-out
`cubic-bezier(0.77, 0, 0.175, 1)` for moving; most moves 180–320 ms. Only `transform`,
`opacity` and small SVG strokes animate. With "Reduce motion" turned on, movement stops and only
fades remain.

## Words

Plain verbs and places: "Loads", "Off", "Overridden", "Via gateway", "Unknown"; scopes
"everywhere", "this project", "this Mac", "plugin", "account". A server outside the gateway is
"not connected to the gateway" (flag: "Not via gateway"). Paths shortened with `~`, full path
in the detail panel, never on the Overview. Every warning says why it matters and what to do.
Changes names plugins by their short name; a stopped change says why ("Can't undo: the file
changed after this"). No counters that repeat a fact shown elsewhere (item counts, "around",
"×2", "Tested" pills).

## States and rules

- Every list has loading, empty, dense and error states (empty example: "No hooks in any client").
- Long names truncate with the full name on hover and in the detail panel.
- Keyboard: `/` search, Enter opens a row, Esc closes the panel, focus returns to the row.
- URL keeps the place, tab, filter and project, so links and Back work.
- Contrast checked in both themes; status never by colour alone.
- Strict Content-Security-Policy stays: no inline scripts or styles, no CDN.

## How it gets checked

On fixture data only: axe-core accessibility checks, screenshot comparison of each place in both
themes, and no CSP errors in the console.

## Not in this step

Charts, a command palette, team or account features, editing gateway tools (the gateway does
that), a mobile layout beyond "does not break".

## Polish after the design review (2026-10-18)

The [design review](../../research/design-and-install-review-2026-10-18.md) scored the first
build 3/3/3/2/3 on simple, easy, intuitive, no noise and modern. Feature 004 applied its Part A:
the Overview cards, the panel's primary action, the review's result line, the remove list, and
the Gateway, Changes and wording fixes. The sections above describe the page after that work.

## Calls I made (owner to check)

- Four places in a rail rather than one long page.
- Overview leads with problems, not with counts.
- Undo instead of confirmation dialogs.
- System font and borders-only depth.
- Taste-skill and Impeccable are not used to build it; the rules come from Vercel's guidelines and
  the interface-design method.
