# Privacy

Kitden runs on your computer. There is no account and no telemetry. Kitden's author receives
nothing from it.

## What Kitden reads

- The settings files of Claude Code, Codex and Cursor on this computer. This includes the limits
  Claude Code's settings set for the skill list (`skillListingBudgetFraction`,
  `skillListingMaxDescChars`). Kitden uses them to size the skill list and keeps none of it.
  When you set the skill list limit on the Context page and press Apply, Kitden writes
  `skillListingBudgetFraction` in Claude Code's user settings (`~/.claude/settings.json`, or
  `settings.json` in the folder `CLAUDE_CONFIG_DIR` names), or for Codex
  `[skills] max_context_tokens` in its `config.toml`, with a backup you can undo.
- For the context check, what the client sent in your last chats, from the client's own chat
  files, and the skills the Claude app gives Claude Code, from the app's own folder. For Codex, also
  its model list (`models_cache.json`), for the size of its context window, and the skill files of a
  plugin's newest version when the chat's version was removed by an update. For a skill built into
  Claude Code, which has no file, the description an earlier chat sent, from the newest chat files.
  Kitden uses them to size the skill list and keeps none of it. The page, `kitden show context`
  and `kitden scan` all do this check. `kitden scan` prints in your terminal one line about each
  skill list, the names of the first five skills that did not fit, and nothing else from the chats. When the folder you run
  it in has no chat, it reads the client's last chat in any folder and also prints that folder's
  path. `kitden show context` does the same, unless you give `--project`.
- A skill's description, from its `SKILL.md`. The page shows it in the skill's Details, and
  `kitden show context` prints it (see "The plugin and your agent"). Its `when_to_use` is read
  only for its size. Kitden keeps none of it.
- Versions and plugin lists, from the clients' own commands.
- A client you turned off in Kitden is not read, and none of its commands are run.

## What stays on your computer

- The page runs at `127.0.0.1` behind a private link.
- Secrets you type or sign in with are kept in the macOS Keychain or the Linux keyring only,
  and so are the secrets in a moved server's env, headers and arguments.
  The page shows no more than their first and last characters.
- Backups of changed files stay in Kitden's own data folder.
- What each server in the Kitden gateway says it does, in its own words (its description, else
  its instructions), is kept in `gateway-about.json` in the same folder. What a catalog or the
  Official MCP Registry says of a gateway server (its description and the keys it requires) is
  kept in `gateway-catalog.json`. Only their owner can read them.
- The versions Kitden finds for each client are kept in one small file, `versions.json`, in
  Kitden's own data folder. The page and `kitden scan` write it. `kitden scan` changes no
  client settings.
- Which clients you turned off is kept in one small file, `clients.json`, in the same folder
  (for example `{"off": ["codex"]}`). It is Kitden's own choice, not a client's settings, and it
  changes nothing in any client's files.
- The answer of `codex plugin list` is kept in `codex-plugins.json` in the same folder, so a
  repeat `kitden scan` does not wait for Codex. It holds only each plugin's id and whether it is
  on, and it is used again only for one hour and only while Codex's `config.toml` is unchanged (a plugin
  switched in Codex on another computer does not change that file). Kitden writes it when the
  page, `kitden scan` or `kitden show` asks Codex, and only when Codex answered.

## When Kitden goes online

- To reach the remote servers you add. In a server's Add access… form, Kitden asks that server,
  with no value, what access it takes.
- To read the catalogs you open and the GitHub sources you add.
- When you press **Rescan**, to ask the Official MCP Registry about each server in the Kitden
  gateway: one search per server, which carries the server's name. Kitden keeps what the
  registry says of it (its description and the keys it requires). Automatic rescans do not ask.
- To install or update Kitden, after your yes.
- At most once a day, when the page opens, to ask PyPI (or, for a Homebrew install, the Homebrew
  tap on GitHub) for the latest version number. The request carries the Kitden version;
  as with any web request, PyPI or GitHub also see your IP address.
  This also happens when Kitden cannot update itself, and then the page shows the command to run.

## The plugin and your agent

The plugin's skills ask your agent to run `kitden show`. The answer goes into the chat, so your
agent and the company behind it see it, under their own privacy terms. Secret values, such as
tokens in a server's settings, are replaced with `[secret]` first. The one exception is
`kitden show context`: it prints each skill's description as written in its `SKILL.md`, and
Kitden does not replace anything in it. Keep secrets out of a skill's description. It also prints
the names of the skills that did not fit in your last chat. When the folder you run it in has no
chat, it also prints the path of the folder of your last chat, which is often a project name.
`kitden show` changes no client settings and does not go online.

## Questions

Open an issue at https://github.com/KonstantinStarovoytov/kitden/issues.
