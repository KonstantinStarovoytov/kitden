# Privacy

Kitden runs on your computer. There is no account and no telemetry. Kitden's author receives
nothing from it.

## What Kitden reads

- The settings files of Claude Code, Codex and Cursor on this computer.
- For the context check, what the client sent in your last chats, from the client's own chat
  files. Kitden uses it to size the skill list and keeps none of it.
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
  tap on GitHub) for the latest version number. The request carries only the Kitden version.
  This also happens when Kitden cannot update itself, and then the page shows the command to run.

## The plugin and your agent

The plugin's skills ask your agent to run `kitden show`. The answer goes into the chat, so your
agent and the company behind it see it, under their own privacy terms. Secret values, such as
tokens in a server's settings, are replaced with `[secret]` first. `kitden show` changes nothing
and does not go online.

## Questions

Open an issue at https://github.com/KonstantinStarovoytov/kitden/issues.
