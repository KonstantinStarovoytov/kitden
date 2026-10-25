# Visual redesign: final design

2026-10-23. Design file: `design/kitden.pen`. Builds on
[visual-management-ux-concept-2026-10-22.md](visual-management-ux-concept-2026-10-22.md).
Ready to hand over for a prototype; not built yet.

## Frames

| Row (y) | Frames |
|---|---|
| −1300 | Components, Note · Rules |
| 0 | O1 Overview, C1 Changes |
| 1100 | D1 folded, D2 server open, D3 tool selected, D4 one project |
| 2200 | D5 drag a server in, D6 add from a marketplace |
| 3300 | L1 skill selected, L2 one project, L4 add from a marketplace |
| 4400 | A1 applying, A2 added, A3 failed |
| 5500 | G1 Gateway list, L3 Library list |
| 6600 | P1 project picker, F1 find in the map, S1 signing in, R1 first run |
| 7700 | N1 narrow window, T1 light theme, I1 Library Instructions tab |
| 8800 | Later: server for chosen clients |

Each row has a note beside it. Older pages and variants A, B, C sit at x +10000 as "Archive · …".

## Rules

- **One tree on every map page.** Gateway: clients → gateway → servers → tools. Library:
  clients → plugins and skills by source → what a plugin holds. Instructions: clients →
  files → imports.
- **Small blocks.** A server is the size of a client. A folded one shows its count.
- **Unfold on click.** Tools appear as small blocks, each on its own link. One server open.
- **The link is the state.** On: a link and a filled mark. Off: no link, a hollow mark.
  No word on the map; Details says it.
- **Direct routes stay visible.** A server a client sets up on its own is joined to that
  client by a faint amber line: its calls skip Kitden's rules.
- **Details holds the actions**, including "… in one project…" and "Use the shared rule…".
- **Words.** A rule only one project has: "This project". A server or skill only one project
  has: "Only this project".
- **Adding.** "+ Add" beside a column caption opens a search of the marketplaces on this
  computer. A result, or a dragged server, shows a preview on the map; Apply makes it real.
- **After Apply.** Steps count in the button. Only after `verified` the block turns solid,
  the new link draws once, and a toast offers Undo. An error stays and says nothing changed.
- **Motion.** An unfold takes at most 300 ms: links draw, then blocks fade in 15 ms apart,
  no extra delay after the sixth. Reduced motion shows only the end state.
- **Width.** Wide: tools unfold to the right. Narrow, or Details open on a small screen:
  down inside the server on a rail, the gateway as a small house (N1).
- **Scale.** Remote and Local fold into one block with a count. Past about 15 servers the
  List view is the main view (G1, L3).

## Components and tokens

The Components frame holds the client, server, outside, tool, plugin and item blocks, the
Add button, client chip, group caption, review bar and toast. Map frames use them as
instances.

Every color is a `kd-*` token with a dark and a light value; T1 is D3 with the light theme.
They map to `style.css`: canvas, panel, panel-raised, inset, ink, ink-2, ink-3, route
(accent), route-soft (select), action, lamp-on (ok), lamp-warn (warn). New: `kd-dim`,
`kd-preview-fill`, `kd-preview-line`.

## What the build needs beyond the page

1. **Marketplace servers (D6).** List MCP servers from the marketplaces Discover already reads.
2. **Gateway sign-in (S1).** The gateway keeps the login in the Keychain; this is plan part 5.
3. **Instructions (I1).** Read import lines from CLAUDE.md; plan part 6.
4. **Skills per project (L2).** Already in Later in ROADMAP.md.

## Later

- **Server for chosen clients.** The gateway knows projects, not clients. Each client entry
  would need its own flag for `kitden mcp` and the rules a third key. Kept as an idea.
- **Marketplace sources beyond this computer**, such as the MCP Registry, only if asked.

## Before code

Build the tree in HTML on a fixture home with 20 servers. Measure time to the first usable
view and to complete data, and compare with the current pages on the same fixtures and
hardware, as ROADMAP.md asks.
