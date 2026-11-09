# Kitden guide

What Kitden does, step by step, and where its limits are. The [README](../README.md) shows
the short version.

Kitden can change your client settings. Only add plugins and MCP servers you trust:
they can run code with your permissions. Undo does not reverse actions a tool already ran.

## See what each agent loads

Open **Library** and choose **All projects** or one project. **List → Differences** shows
what differs between Claude Code, Codex and Cursor. Click an item for its **Details**.

| What | How to manage it |
| --- | --- |
| **Plugins and skills** | Use **+ Add**, or drag an item onto another client. Turn it on or off, choose its scope, or remove a copy in **Details**, where the client supports it. **Add missing plugins and skills…** fills gaps across clients. |
| **Marketplaces** | Browse their plugins and skills. **+ Add → Add a marketplace…** adds a GitHub source. **Details → More → Commands…** has update and remove commands to copy. |
| **Hooks and instruction files** | See which client loads them and where they come from. **Library → Instructions** shows files and imports, plus commands and agents. Kitden only reads these; edit them in your editor. |

The preview names the clients and projects affected. Adds on the map go to all projects;
the List offers a project scope where supported. Start a new client session to load a change.

## Add from the catalogs

**+ Add plugins** in Library and **+ Add servers** in Gateway open one catalog: **skills.sh**,
the **official MCP Registry**, the Claude plugins marketplace, any public GitHub repository you
add, and what is already **On this computer**. Click a result to preview it, or drag it onto a client
or the gateway. Skills come from a pinned GitHub commit, plugins use the client's own installer,
and MCP servers go to the Kitden gateway, so every connected client gets them.
See [online sources](discovery.md) for formats and limits.

- **Tokens:** a server asks for exactly the value it needs. Kitden checks it against the server
  before Apply and keeps it in the **macOS Keychain** or the **Linux keyring** only.
- **Browser sign-in:** **Sign in** opens the server's page; Kitden catches the answer itself
  and refreshes it later. A server that allows no sign-in for Kitden asks for an API key instead.
- **Not ready yet:** it waits in the preview; Apply writes the rest. **Details** show each secret
  by name, only its first and last characters, with **Replace** and **Remove**.

## Share a server between your agents

Open **Gateway** to share MCP servers and turn individual tools on or off for each project.
Pick several with a band or Shift-click and drag them in together. Library works on its own.
A server that must start in its own folder starts there in the gateway, so it also works in
Cursor, which has no such setting.

## Review a change. Apply it. Undo it.

Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact
edit; Apply writes it and checks the result. Open **Changes → Undo** to restore it.
If Undo would overwrite newer edits, Kitden stops. Changes also offers **Redo…** and
**See it on the map**.
If an app such as Pen writes a removed server back, the review warns you first and Changes
says it is back.

## Try the sample

```bash
uvx --python 3.13 kitden demo
```

Kitden opens in your browser on temporary sample files. If it does not, open the link printed
in Terminal. Your settings and secrets are not read or changed, even when you press Apply.
The demo starts no real clients or MCP servers. The first run downloads Kitden; the demo
itself stays offline.

1. In **Library → List**, find **superpowers** and press **+ Add** under **Codex**.
2. Review and **Apply**. Codex now has a copy in the sample setup.
3. Open **Changes → Undo** to remove that copy again.

Press **Ctrl+C** in Terminal to stop and delete the sample.

## Install

Requires **macOS or Linux**, **[uv](https://docs.astral.sh/uv/)** and at least one of
**Claude Code, Codex or Cursor**. uv gets Python 3.13 if needed. On Linux, also install
`libsecret-tools` (Debian, Ubuntu) or `libsecret` (Fedora, Arch): Kitden keeps server secrets
in your desktop keyring through it. Install uv with its official installer, then open a new
Terminal window:

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/getting-started/installation/ -->
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install Kitden once, then run `kitden` whenever you need it:

```bash
uv tool install --python 3.13 kitden
```

If the command is not found, run `uv tool update-shell` and open a new Terminal window.
To update, run `uv tool upgrade kitden`, then restart your clients.

With [Homebrew](https://brew.sh) instead, uv is not needed:

```bash
brew install konstantinstarovoytov/tap/kitden
```

To update, run `brew upgrade kitden`. Homebrew builds Kitden and its dependencies from
source, which takes a few minutes the first time.

## Privacy and limits

- The page runs locally at `127.0.0.1`, with a private access link. No account or telemetry.
- Credentials go to the server they belong to, or to a gateway you move that server into.
  Secrets you type or sign in with are kept in the macOS Keychain or the Linux keyring only;
  the page never shows more than their first and last characters. Kitden masks secret fields and known token
  formats in its page and logs.
- Kitden goes online only to reach remote servers, the catalogs you open and the GitHub
  sources you add. Nothing from a catalog runs during search or download.
- Backups stay for 30 days, and the newest 100 changes always keep theirs.
- Undo of plugin removal installs the plugin again, but does not restore its saved options.
- Kitden writes to your home folder, its own data folder, known projects and detected client
  settings folders. The preview shows which files will change. Project settings stay separate
  from the shared setup.

## Let your agent read your setup

In Kitden, choose **Let agents read this setup**. Then ask your agent **"show my setup"**.
Kitden's own tools only read. Servers moved into the gateway add their tools, which do what
those servers do.

Already have the `kitden` command? [Add to Cursor](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=).
The plain link is `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

## Report a bug

Include your Kitden and client versions, steps to reproduce it, and what you expected. Remove
secrets and private paths from screenshots and logs. See [Contributing](../CONTRIBUTING.md).
