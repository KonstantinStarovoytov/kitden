# Online sources

In Library, open **+ Add** for plugins and skills. In Gateway, open **+ Add** for MCP servers.
**Catalogs** opens first; **On this Mac** browses local sources. Pick a visible source button,
search, then open a result. Filters and sources use buttons, not drop-down menus.
**Source details** shows the source, available version and the skill text or MCP configuration.
Choose clients explicitly and Preview. Back to search keeps the query and results. Nothing changes in a client until Apply. Undo uses the same
backups and checks as a local add.

## Sources

- **skills.sh:** public skill search, including source repositories and install counts.
- **Official MCP Registry:** active, latest server versions. Results include the full publisher
  name; being listed is not a safety guarantee. Search returns up to 100 entries.
- **Claude plugins:** the official GitHub marketplace. Individual plugins such as Superpowers
  are not preset catalogs. You can explicitly add their repositories as your own sources.
- **Your GitHub sources:** add `owner/repo` or a public GitHub repository URL. Kitden finds
  `SKILL.md` files, marketplace entries and standalone Claude plugins. For MCP, it reads
  `server.json` and `.mcp.json` files in the source.

Opening the catalog loads an initial selection. Switching sources or filters reloads it.
Search results stay visible while an item opens in the adjacent details panel.
Use Sources beside Search to add, edit or remove custom GitHub sources. Removing a source
keeps installed items; Undo removal restores the source. Built-in catalogs stay available.

Search runs on catalog open or when requested. Adding a source saves a Kitden preference, not a client
marketplace. Installing its plugin adds the needed marketplace in the same preview.
Private repositories, arbitrary website catalogs and API-key-protected catalogs are not
supported in this first version. Smithery and Glama are not separate providers yet.

## Installation limits

- Skills are fetched from a specific GitHub commit, including their supporting files. A skill
  that needs files outside its folder is refused. Symlinks and unsafe archive paths are refused.
- Plugins use the client's own installer. Marketplace plugins follow that marketplace's
  version resolution at Apply; Kitden does not claim to pin their transitive dependencies.
- Standalone Claude plugins get a local marketplace wrapper around a cached snapshot.
- MCP supports complete streamable HTTP endpoints and npm packages with declared versions.
  Required credentials, additional arguments, OAuth and other package transports need separate
  setup; the page explains when it cannot add one. Optional credentials can be left out.
- A new server goes to the Kitden gateway. Connect your clients to that gateway to use it.
- A matching installed name is shown as Installed; the preview still checks for conflicts and
  refuses an existing destination. A name alone does not prove two sources are the same.
- The normal demo stays offline. Use your own setup to search the internet.

Catalog data and cached files stay under Kitden's data folder, in `discovery/`. Search snapshots
are kept so saved previews can be read again after a restart. No catalog code is run during
search or download. Skill files may contain scripts; review them before applying an install.

## References

Checked **2026-10-29**:

- [skills CLI search](https://github.com/vercel-labs/skills/blob/main/src/find.ts): public
  `/api/search`. The separately documented `/api/v1` requires Vercel OIDC.
- [MCP Registry API](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md):
  `/v0.1/servers`, `search`, `version=latest`, active status and cursor pagination.
- [GitHub trees](https://docs.github.com/en/rest/git/trees): recursive trees and truncation.
- [Registry server schema](https://github.com/modelcontextprotocol/registry/tree/main/docs/reference/server-json):
  transport declarations, package versions and required input fields.
