# Privacy

Kitden runs on your computer. There is no account and no telemetry. Kitden's author receives
nothing from it.

## What Kitden reads

- The settings files of Claude Code, Codex and Cursor on this computer.
- For the context check, what the client sent in your last chats, from the client's own chat
  files, and the skills the Claude app gives Claude Code, from the app's own folder. For Codex, also
  its model list (`models_cache.json`), for the size of its context window, and the skill files of a
  plugin's newest version when the chat's version was removed by an update. Kitden uses them to size
  the skill list and keeps none of it. The page, `kitden show context` and `kitden scan` all do
  this check; `kitden scan` prints one line about each skill list in your terminal and nothing else
  from the chats.
- Versions and plugin lists, from the clients' own commands.

## What stays on your computer

- The page runs at `127.0.0.1` behind a private link.
- Secrets you type or sign in with are kept in the macOS Keychain or the Linux keyring only.
  The page shows no more than their first and last characters.
- Backups of changed files stay in Kitden's own data folder.

## When Kitden goes online

- To reach the remote servers you add.
- To read the catalogs you open and the GitHub sources you add.
- To install or update Kitden, after your yes.
- At most once a day, when the page opens, to ask PyPI (or, for a Homebrew install, the Homebrew
  tap on GitHub) for the latest version number. The request carries the Kitden version;
  as with any web request, PyPI or GitHub also see your IP address.
  This also happens when Kitden cannot update itself, and then the page shows the command to run.

## The plugin and your agent

The plugin's skills ask your agent to run `kitden show`. The answer goes into the chat, so your
agent and the company behind it see it, under their own privacy terms. Secret values, such as
tokens in a server's settings, are replaced with `[secret]` first. `kitden show` changes nothing
and does not go online.

## Questions

Open an issue at https://github.com/KonstantinStarovoytov/kitden/issues.
