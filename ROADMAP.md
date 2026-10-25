# Kitden roadmap

Last updated: 2026-10-25

What Kitden does today and what comes next. Ideas and bugs:
[open an issue](https://github.com/KonstantinStarovoytov/kitden/issues).

## Done

### Not released yet

- **The mockup's look:** Inter and JetBrains Mono come with Kitden, line icons in every place,
  the mockup's colours in both themes, a new side rail and top bar, and calm motion with one
  shared timing.
- **Gateway map:** blocks glide and unfold in place, links take the pointer (× to remove, by
  keyboard too), and a selected block dims everything off its path. Blocks look like the mockup:
  lamps, ports, the gateway's counts that roll, and on each tool how many projects have a rule of
  their own for it. Changes in the tray show on the map: a connect draws a dashed link, a
  disconnect or a removed entry makes its line leave, and a server moved out waits outside,
  "Moves to" its client; a click on one takes it out. Drag a server from outside onto the gateway:
  the gateway lights and a slot opens; while the move waits the server shows only in the gateway,
  and taking it out glides it back. Drag a server in the gateway onto a client to move it out:
  the client lights and a wire follows the server, or the tip says why that client cannot take it.
  Drag a client that is not connected onto the gateway to connect it: a wire runs to the pointer
  and snaps to the gateway, which lights; a client a plugin connects says why it cannot. A group
  of more than six shows five at a time: "N more" turns to the next five in place. Map | List
  swaps with a short fade, the List has the mockup's columns and rows, and a search dims what does
  not match with a soft blur.
- **Details float beside the map:** on Gateway, Library and Changes, Details float over the right
  of the page as in the mockup; the page keeps its width and the map stays wide. Another block's
  Details swap in place through a quiet skeleton.
- **Server panel:** a server's Details on the Gateway list its tools with a switch each and a
  Whole server switch, as in the mockup. "Move out of the gateway…" picks the client that keeps
  the server; its other actions wait under More.
- **Tool panel and several projects:** a tool's Details on the Gateway say its permission and
  list the projects with a rule of their own, with "Show" to open one. "Turn on|off in some
  projects…" ticks projects in a list (also for a whole server): each tick is its own row in the
  tray, and the map's tool names the projects that wait.
- **Client, gateway, link and outside panels:** a client's Details on the Gateway say what it gets
  through Kitden and what it sets up on its own, with "Connect to the gateway…" or "Disconnect
  from the gateway…"; the gateway's Details list each client with its own button. A click on any
  link opens its own panel; a client's link × disconnects it, and the × on a server a client sets
  up on its own removes that entry. Every action stays, some under More.
- **Preview tray:** every change, from a switch in Details to a drag on the map, waits in one tray
  at the bottom left. Apply all writes them as one change, all or nothing, and Undo all takes them
  back. "Show changes" opens one row's full review.
- **Library:** one page in place of Load map and Discover. Only the clients on this computer get
  a column, and the action sits in the client's cell: "+ Add", or why there is none. A server
  another client has points to the gateway; a marketplace says it comes with its first plugin.
  "Add…" for several clients warns, like "+ Add", when a client would load two of the same name.
- **Add skills:** a client that cannot install a plugin takes its skills instead, in one change
  with Undo. It reads plugins from Codex's marketplaces and the ones Cursor installed itself.
  A skill the client already loads, from its folders or another plugin, is left out.
- **Hide a column:** the "−" on a client's column head hides it on the page, and "Show" brings it
  back.
- **Categories:** filter plugins and skills by category. The category shows quietly in each row.
- **Quick start:** the page has its data in about two seconds. Codex's slow plugin list comes in
  the background, and a line shows what is still read.
- **Rescan:** also checks the client versions, so a client updated while the page runs shows
  its new version.
- **Kitden gateway:** on the Gateway page, pick a project and turn a whole MCP server or single
  tools on or off for it, in every client; its folders and worktrees follow it. Local servers
  move in too, and moving a server the gateway holds again updates it, for a new token. Each
  switch waits in the preview tray and has Undo; no deploy, no account.
- **Overview:** knows the Kitden gateway and says whether it is set up.
- **Add scope:** in a project, the Library says an Add puts the item in all your projects.
- **Kitden's own entries:** no cross-client note for them.
- **True words:** the start link, the agents server, where secrets go, and the sign-in check.
- **Gateway page:** says the gateway controls only the servers in it, and folds a group after
  six rows.
- **Strict mode:** a server can offer only the tools you turned on, for all projects. New tools
  wait as "New · off". Codex's allowed-tools list moves in as strict.
- **Turned off means refused:** a tool you turn off is refused at once, in open sessions too.
  Folders Kitden does not know follow the All projects switches, and the page says so.
- **Reads and writes:** each tool shows a quiet word, from the server or its name.
  "Turn off every writing tool…" is one change, with the token advice.
- **Calls counted:** hover a tool to see how often it was called and when last.
- **Remove a plugin:** "Remove from <client>…" in its Details. Undo installs it again, but not
  its saved options.
- **Remove a skill:** its folder goes to the backup, and Undo puts it back.
- **Remove from the Kitden gateway:** a held server leaves with its switches; open sessions refuse
  its tools at once.
- **Put back:** a held server's entry goes into a client again.
- **Move a server out of the gateway:** its entry goes into one client and leaves the gateway, as
  one change. A Keychain secret is written into that client's file as plain text; the review says
  so. Undo brings both back.
- **Disconnect a client from Kitden:** removes the client's `kitden` entry, so it no longer reaches
  the gateway, and the review says what it loses (the gateway's servers and Kitden's read of the
  setup). Undo puts it back. Adding that entry now reads "Connect … to Kitden".
- **Add an MCP server to another client:** "+ Add" copies the entry; a `${VAR}` reference stays a
  reference where that client reads one.
- **Add into one project:** a skill, or a Claude Code plugin, for that project only.
- **Add missing:** in a project, one change adds what one client loads there and another lacks.
- **Honest Undo:** Undo of a mixed change runs the client's own commands too, and a failed
  Apply says what it could not put back.
- **Versions in the background:** the page reads the clients' versions from a file on disk and
  checks them after it opens, so it never waits for a client to start.
- **Measured start:** a script reports the time to the first usable page and to complete data on a
  large sandbox setup: 0.1 s and 0.2 s on an M4 Max.

### 0.2.0

- **Discover:** search the plugins in the marketplaces already on this computer and add one to
  Claude Code and Codex in one review. Add a marketplace from a folder or a GitHub link.
- **Skills:** copy a skill into a client from Discover, with Undo.
- **Every client the change reaches:** Add and Preview name Cursor when it loads Claude Code's
  plugins and skills.
- **Obot:** register an Obot gateway, see what it holds, connect clients with OAuth, and move
  direct servers into it. "Move all" waits and retries when Obot is busy.
- **MetaMCP:** see what the gateway holds and move direct servers into it with one Apply and one
  Undo.
- **Switch gateways:** move every client to another gateway in one review.
- **Gateway diagram:** a client opens its app, the gateway opens its own page.
- **UX audit fixes:** keyboard focus stays through redraws, every control is at least 24 px,
  success and diff text keep 4.5:1 contrast, a lost Apply or Undo answer is read back, restart
  notes only for changes that happened.
- **Progress you can see:** a busy button shows a spinner in its own place, and Apply counts
  the steps of a long change.
- **New look:** the Kitden house, light and dark Graphite themes, client icons, and calm motion
  that shows what changed.

### 0.1

- One page for Claude Code (with the Claude Desktop Code tab), Codex and Cursor: MCP servers,
  plugins, skills, hooks and marketplaces.
- Things that load twice, each with one fix.
- Turn items on and off with a preview, a backup and Undo.
- Connect clients to a MetaMCP or Obot gateway.
- A read-only "show my setup" MCP server for agents.
- One-line install, a plugin for Claude Code and Codex, and an Add to Cursor link.

## Planned

The two reviews of 2026-10-21 (`docs/research/`) led to one approved design,
[docs/superpowers/specs/2026-10-21-review-follow-up-design.md](docs/superpowers/specs/2026-10-21-review-follow-up-design.md),
and a master plan with one plan per part,
[docs/superpowers/plans/2026-10-21-review-follow-up.md](docs/superpowers/plans/2026-10-21-review-follow-up.md).
The parts, in order:

5. **Secrets have a lifecycle:** gateway secrets in the Keychain; backups say when they hold a
   secret; logins in one place, so OAuth servers move into the gateway too.
6. **The whole picture:** an Instructions tab (CLAUDE.md, AGENTS.md, Cursor rules, commands,
   agents); tool counts.
7. **Linux and Windows.**

## Next

- Copy any command with one click.

## Later

- Skills per project: turn skills on or off for one project, as tools are today.
- A living map with connected comparison and access views. See the
  [visual management UX concept](docs/research/visual-management-ux-concept-2026-10-22.md)
  and the [final design](docs/research/visual-redesign-final-2026-10-23.md) in
  `design/kitden.pen`; prototype and test it before implementation.
- A shared setup for a small team.
