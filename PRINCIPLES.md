# Kitden principles

Every change is judged against these. Reviewers read this file.

## What Kitden is for

1. **One picture of everything a coding agent loads:** global and project items, plugins,
   skills, MCP tools and instruction files. Turn each On or Off, move it into a project, and
   tidy up.
2. **Several agents kept aligned:** see duplicates and what loads twice, move or add an item
   between Claude Code, Codex and Cursor, and keep one project the same in all of them.
3. **One local gateway over all MCP servers:** control each tool, and set a strict or
   read-only policy per project.

## What it must always be

- **Super simple and visual.** People should want to press the buttons. The main page shows a
  name, the client and an action; paths, addresses and commands stay behind Details.
- **Fast to open.**
- **Local only and secure.** Everything stays on the computer. A token never leaves it, except
  to the server it belongs to.
- **Safe to change.** Every change to a client's settings goes through preview, Apply with a
  backup, verify and Undo.

## What we do not do

<!-- Draft: the owner edits this list. -->

- No cloud account.
- No telemetry.
- No second way to write a client's settings.
- No option nobody asked for.

## What counts as new

A route, a CLI command, a setting, a page element or a dependency goes to the owner before it
is built. Open an issue and wait for a yes.
