# Kitden roadmap

Last updated: 2026-10-21

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
- **Quick start:** the page has its data in about two seconds. Codex's slow plugin list comes in
  the background, and a line shows what is still read.
- **Kitden gateway (in progress):** `kitden mcp` also offers the tools of the servers moved into
  it, only those turned on for the session's project. Moving servers in comes next.

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

## Next

- Copy any command with one click.
- Linux and Windows.

## Later

- Remove a plugin.
- A living map: clients → config files → servers, plugins, skills → gateways.
- A shared setup for a small team.
