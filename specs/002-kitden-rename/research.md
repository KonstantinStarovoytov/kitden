# Research: Kitden name and one-command page

Reviewed: 2026-10-18. Status: decisions for this feature.

## R1. Rename approach

- **Decision**: Move `src/agentsetup` to `src/kitden` with `git mv`, rename imports, the package
  name, the console script, the MCP server name, the session cookie and the theme key. Version
  0.2.0. No alias for the old command.
- **Rationale**: One name everywhere (FR-001). `git mv` keeps file history. An alias would keep the
  old name alive in configs and in PyPI searches.
- **Alternatives**: keep `agentsetup` as a second console script (rejected: the old name is
  another project's PyPI package); a thin compatibility package (rejected: nothing installs it).

## R2. Several steps on one file in one change

- **Decision**: Let the change engine accept several steps on the same file when their keys
  differ. Apply them in order on a working copy of that file; back up the file once; verify each
  step's key and the final bytes; restore the original bytes if any step fails. Undo also works
  through the steps of one file in reverse order on one working copy.
- **Why it is needed**: "Update to Kitden" removes the `agentsetup` entry and adds the `kitden` entry
  in the same settings file. Today the engine refuses that ("edited twice in one change"), and its
  entry-level Undo computes each step from the same file contents, so the second write would undo
  the first.
- **Rationale**: One change means one review, one Apply and one Undo (FR-006, SC-002). All safety
  rules stay: preview, stale check, backup, verify, restore, exact Undo.
- **Alternatives**: two separate changes (rejected: two Undos in the right order); replacing the
  whole `mcpServers` table (rejected: rewrites entries the product does not own); a new "rename
  key" edit (rejected: more editor code than ordering the steps).

## R3. One page per home folder

- **Decision**: The page holds an exclusive lock on `<data folder>/page.lock` for its whole life
  (`fcntl.flock`, non-blocking). A second `kitden serve` or a background start that cannot take the
  lock exits and opens the running page. The operating system releases the lock when the process
  ends, so a crash never leaves a "running" page behind.
- **Rationale**: Reliable stale detection without process-id guessing.
  [Python fcntl](https://docs.python.org/3/library/fcntl.html#fcntl.flock).
- **Alternatives**: process id in a file (rejected: ids are reused); probing ports (rejected:
  another program may use the port).

## R4. Page record

- **Decision**: After the server listens, write `<data folder>/page.json` with the port, process id,
  start time and start link token. File mode 0600 in the 0700 data folder. Remove it on shutdown.
  `kitden open` reads it only when the lock shows a page is running.
- **Rationale**: The start link token is reusable for the life of the page, so the running page can
  be reopened. A user-only file is the same trust boundary as the client settings the product
  already reads. Jupyter uses the same pattern: per-process connection files in a runtime folder,
  kept only for the life of the process
  ([Jupyter runtime files](https://docs.jupyter.org/en/latest/use/jupyter-directories.html#runtime-files)).
- **Alternatives**: an unauthenticated "reopen" endpoint (rejected: any local process could get a
  session).

## R5. Starting in the background

- **Decision**: `kitden open` starts `kitden serve --background` with the same Python executable,
  `start_new_session=True`, no stdin, and output to `<data folder>/page.log`. It waits up to 5 s for
  a new `page.json`, then opens the browser and prints the link.
- **Rationale**: The calling agent or terminal gets control back at once, and the page survives the
  terminal closing. [Python subprocess](https://docs.python.org/3/library/subprocess.html#subprocess.Popen).
- **Alternatives**: a login service (rejected: constitution VI); `os.fork` (rejected: unsafe with
  threads).

## R6. Stopping when no tab is open

- **Decision**: Open tabs hold the page's event stream (`/api/events`). In background mode a timer
  checks every 30 s; when there has been no event stream for 10 minutes and no change is running
  (the write lock is free), it asks uvicorn to stop (`Server.should_exit`). The idle clock starts at
  launch, so a page that never got a tab also stops.
- **Rationale**: The event stream already exists and ends when a tab closes. uvicorn 0.x exposes
  `should_exit` on its `Server` object for a graceful stop (checked in the installed source).
- **Alternatives**: page heartbeats (rejected: duplicates the event stream); stopping the moment the
  last tab closes (rejected: a reload would kill the page).

## R7. Data folder copy

- **Decision**: On start of any command, when `Library/Application Support/agentsetup` exists and
  `Library/Application Support/kitden` does not, copy it with permissions (`shutil.copytree`,
  `copy2`) to a temporary sibling, rewrite the old root to the new root inside every
  `changes/*/change.json` (backup paths are stored as absolute paths), then rename the temporary
  folder into place. The old folder is never changed. If both exist, use the new one and print one
  line that the old one was left.
- **Rationale**: Copying never loses data, and a still running old page keeps its folder. Rewriting
  the backup paths makes Undo independent of the old folder. The final rename makes the copy
  all-or-nothing.
- **Alternatives**: move (rejected: an old page still running would lose its folder); reading backups
  relative to the store root (better long term, but changes stored records; can come later).

## R8. Old entries and cookies

- **Decision**: An old entry is a user-level MCP item named `agentsetup` in Claude Code, Codex or
  Cursor whose summary `command` ends with `/agentsetup` and whose `args` are `["mcp"]`. The action
  `setup_server.update` builds, per client, a remove step for the old entry and an add step for
  `kitden` with the absolute path of the installed `kitden` command. The session cookie name
  includes the port (`kitden_session_<port>`), because browsers share cookies across ports of one
  host ([RFC 6265, section 8.5](https://www.rfc-editor.org/rfc/rfc6265#section-8.5)).
- **Rationale**: Only entries this product made are touched (FR-007). The cookie fix stops pages for
  different home folders from logging each other out (FR-011), which happened during the redesign.
- **Alternatives**: match by name only (rejected: could change a stranger's server).
