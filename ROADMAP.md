# Kitden roadmap

Last updated: 2026-10-22

What Kitden does today and what comes next. Ideas and bugs:
[open an issue](https://github.com/KonstantinStarovoytov/kitden/issues).

## Done

### Not released yet

- **Library:** one page in place of Load map and Discover. Only the clients on this computer get
  a column, and the action sits in the client's cell: "+ Add", or why there is none. A server
  another client has points to the gateway; a marketplace says it comes with its first plugin.
  "Add…" for several clients warns, like "+ Add", when a client would load two of the same name.
- **Add skills:** a client that cannot install a plugin takes its skills instead, in one review
  with Undo. It reads plugins from Codex's marketplaces and the ones Cursor installed itself.
  A skill the client already loads, from its folders or another plugin, is left out.
- **Hide a column:** the "−" on a client's column head hides it on the page, and "Show" brings it
  back.
- **Categories:** filter plugins and skills by category. The category shows quietly in each row.
- **Quick start:** the page has its data in about two seconds. Codex's slow plugin list comes in
  the background, and a line shows what is still read.
- **Kitden gateway:** on the Gateway page, pick a project and turn a whole MCP server or single
  tools on or off for it, in every client; its folders and worktrees follow it. Local servers
  move in too, and moving a server the gateway holds again updates it, for a new token. Each
  switch is one review with Undo; no deploy, no account.
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
  "Turn off every writing tool…" is one review, with the token advice.
- **Calls counted:** hover a tool to see how often it was called and when last.
- **Remove a plugin:** "Remove from <client>…" in its Details. Undo installs it again, but not
  its saved options.
- **Remove a skill:** its folder goes to the backup, and Undo puts it back.
- **Remove from the Kitden gateway:** a held server leaves with its switches; open sessions refuse
  its tools at once.
- **Put back:** a held server's entry goes into a client again.
- **Add an MCP server to another client:** "+ Add" copies the entry; a `${VAR}` reference stays a
  reference where that client reads one.
- **Add into one project:** a skill, or a Claude Code plugin, for that project only.
- **Add missing:** in a project, one review adds what one client loads there and another lacks.

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

4. **Fast to open, and measured:** versions read in the background with a disk cache; a script
   that reports time to the first usable view and to complete data.
5. **Secrets have a lifecycle:** gateway secrets in the Keychain; backups say when they hold a
   secret; logins in one place, so OAuth servers move into the gateway too.
6. **The whole picture:** an Instructions tab (CLAUDE.md, AGENTS.md, Cursor rules, commands,
   agents); tool counts.
7. **Linux and Windows.**

## Next

- Copy any command with one click.

## Later

- Skills per project: turn skills on or off for one project, as tools are today.
- A living map: clients → config files → servers, plugins, skills → gateways.
- A shared setup for a small team.
