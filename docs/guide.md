# Kitden guide

What Kitden does, step by step, and where its limits are. The [README](../README.md) shows
the short version.

Kitden can change your client settings. Only add plugins and MCP servers you trust:
they can run code with your permissions. Undo does not reverse actions a tool already ran.

## Start on the Overview

The page opens on **Overview**. Its first line says how many things need your attention, and in
which clients. Under it stand cards in two groups:

- **Needs attention:** something that costs you now. The most costly comes first: a skill list
  that did not fit in the last chat, then a change that came undone, then other problems such as
  a file Kitden could not read (its **Copy path** gives the file's path), and last a plugin or
  skill a client loads more than once.
- **Can improve:** something you may want. One card says how many servers can move into the
  gateway, and its **Open in Gateway** opens the Gateway's List; a server outside the gateway is
  a normal setup, not a fault. A client the gateway does not reach yet has a card with
  **Connect**, which adds that change to the preview.

Each card has one button. Most add a change to the preview, which you review and **Apply**; some
open the page where you fix it. When Context suggests a limit, the skill list card's button adds
that limit, and its line says what it costs. **Keep one…** on a copies card opens the item in the
Library with its **Details**, which list each copy with its folder; **Keep this one…** beside a
copy removes the others. It shows only where every client still has the item afterwards: keeping
Cursor's own copy would delete Claude Code's folder, so only Claude Code's copy has the button.
Where no copy can stay alone, the card has no button and says why: Cursor also reads Claude
Code's and Codex's skill folders; turn off **Include Third-Party Plugins, Skills, and Other
Configs** in Cursor Settings → Agents → Third-Party Imports to load each skill once. A card leaves once its change is applied, and comes back if you undo it.
The skill list card moves to **Can improve** instead: it says the limit is set and that a new chat
shows the new list. With no limit to suggest, its line gives the reason Context gives.
Four or more cards of one kind fold into one row ("35 skills load more than once"); **Show**
opens them.

**Show 5 notes (nothing to fix)** under the cards opens the notes: facts worth knowing that need
no change. **Your setup**, beside the cards, is a small map of your clients and the Kitden
gateway; point at a card to see on it what the card is about.

## See what each agent loads

Open **Library** and choose **All projects** or one project. **List → Differences** shows
what differs between Claude Code, Codex and Cursor. Click an item for its **Details**.
The search box at the top, "Search skills, plugins, servers and tools…", searches your whole
setup from any tab: a server or a tool opens the Gateway with the matches, anything else the
Library. In the List, **+** in a client's column adds the item there (point at it for what it
adds); **Add missing plugins and skills…** shows only when one client lacks something another has.
On the map, a group of two or more starts folded as a stack of cards. Press a stack to open it;
a big group shows five at a time, with the rest in the stack below. **Collapse** folds it again.
When you select a client, a stack that holds some of its items shows those in front and says how
many are that client's ("3 of 55"). The Gateway's groups work the same way.

| What | How to manage it |
| --- | --- |
| **Plugins and skills** | Use **+ Add**, or drag an item onto another client. Turn it on or off, choose its scope, or remove a copy in **Details**, where the client supports it. A Claude Code skill can also be off in one project only. A plugin that a project turns on, but that is not installed on this computer, shows as unknown. **Add missing plugins and skills…** fills gaps across clients. |
| **Marketplaces** | Browse their plugins and skills. **+ Add → On this computer → Add a marketplace…** adds one from a GitHub repository or a folder. **Details → More → Commands…** has update and remove commands to copy. |
| **Hooks and instruction files** | See which client loads them and where they come from. **Library → Instructions** shows files and imports, plus commands and agents; pick a project to see its own files. Kitden only reads these; edit them in your editor. |

A thing has the same switch wherever it shows, with a line that says where it holds ("Claude
Code · all projects"). A skill has **On**, **Name only** (Claude Code) and **Off**. A plugin has
**Turn off for all projects…** or **Turn on for all projects…**, and with a project picked **Turn
off in this project…** or **Follow all projects…**. Where a client has no switch, the place where
it would be says why: Codex has no **Name only**, Cursor has no switch for one skill (add
`disable-model-invocation: true` to its `SKILL.md` to keep its description out), and hooks are
only shown. In the Library's List, an empty cell with a reason shows a small **?**; point at it.
A skill set to **Name only** says **Name only** in the List and in its **Details**, not **On**.
With **All projects** picked, a state that a project's own settings change names that project:
**On · Off in atlas**, and "Claude Code loads this skill in every project except atlas". A Codex
skill that only one project has has one control, for that copy: **Turn off this copy in Codex…**
in the Library, and "Codex · this copy in atlas" on Context.

On the Library map, point at a link: its **×** removes a plugin from that client, or turns a skill
off there, and its hover says which.

When a client loads one plugin or skill more than once, its row counts the copies ("Cursor loads
it 3 times"), the same number as the Overview's card. Removing one copy says how many stay ("Cursor:
Loads twice").

**From your Claude account** holds the plugins you or your organization turned on for your Claude
account, which the Claude app gives to Claude Code. **Turn off** changes Claude Code's own
setting, so the plugin stays in your account; to remove it from your account, use the Claude app
or claude.ai. A plugin your organization requires has no switch. Plugins the terminal gets from
your account are not read yet.

A Codex server with `enabled = false` shows on the **Gateway** as **Off in Codex**, with **Turn on
in Codex for all projects…** in its **Details**.

The preview names the clients and projects affected. While a change waits in the preview, every
row and card that shows the thing says **in preview** with a dashed ring: a switch, a removal, an
add or a move into the gateway, in each client's cell the change reaches (Cursor's too, when it
gets a plugin through Claude Code). On **Context**, what the preview adds to a client waits under
**Added · in preview**. Start a new client
session to load a change.

## Choose your clients

If you use only some of Claude Code, Codex and Cursor, press **Clients** at the bottom of the left
bar (while a client is not installed, **Choose clients…** also stands at the top right of each page). A client that is not on this
computer says **Not installed**. Turn a client off and Kitden stops reading it: it runs none of
the client's commands, and the client leaves the Overview, the Library, the Gateway, **Let agents
read this setup** and `kitden scan`. Turn it on and it comes back. Kitden keeps at least one client on.

Nothing in a client's own settings changes. A change you made to a client that is now off stays
in **Changes**, but its Undo waits until you turn the client on again. Kitden keeps your choice in
`clients.json` in its data folder. The small **−** on a Library List column only hides that column
in this browser.

## Check that your skills fit

Every chat starts with the list of your skills, and that list has a small limit: 1% of the
context window in Claude Code (or the share your settings set), 2% in Codex. Past it, Claude Code
sends some skills by name only, and Codex shortens descriptions and then leaves skills out. The
agent may never reach for those skills.

Open **Context**. For Claude Code and Codex it reads the last chat's log and says how many skills
went in whole. With **All projects**, the window card names the folder of that chat. Kitden keeps
none of the log and sends nothing. Cursor gets no verdict, because Kitden cannot see what Cursor
sends.

**The fix is under the verdict:** the suggested limit, what it costs in every chat, and its **Set
to …** button. When even 4% of the window would not fit every description, Kitden suggests 4% and
says how many skills would still show only a name; when Claude Code's built-in skills take most of
the list, the line under it says how much. When Kitden offers no new limit, the same place says why:
then set some skills to **Name only** or **Off**. A skill's **Details** name the same fix, and so
does the last line of `kitden scan`.
The strip at the top is the whole context window. Kitden measures only the skill list in it, not
the system prompt, MCP tools, instruction files, hooks or the chat.

**The groups** sort the skills by where they come from, with the Library's names: each plugin,
**Your skills**, a project's skills, the plugins from your Claude account, and **Built into Claude
Code** or **Built into Codex**. A skill removed since the last chat is not on the page and no longer
counts. Each header says how many skills the group has, how much of the list they take, and how
many showed only a name. The groups you can turn off come first. A plugin's header has its **Turn
off** switch; the bar and the estimate count it at once, before you apply it. A group without a
switch says why when you open it.

**A skill's Details** are the Library's own, with the same actions in the same order, and Context
adds its facts: the size, the description, with the part the agent did not get in grey, and for
Claude Code how often you used the skill and when you last did, so you can tell which ones you do
not use. The switch there is the Library's: **On**, **Name only** (Claude Code) or
**Off**. A skill of a plugin follows its plugin. A skill you turned off stays in its group, struck
through, so you can turn it on again, in Claude Code and in Codex. When the last chat was in
another project than the one picked, its pill says where: **Off in atlas**.

**The limit line.** When skills showed only a name, the line on the bar has a handle. Drag it to
the right, from 1% up to 4% of the window; a note says what each step gives ("1.1% · all 20 fit ·
about 650 more characters per chat"), and it snaps to the step where every description fits.
Claude Code's rule can leave more skills with only a name at a larger share (long descriptions in,
short ones out); the line skips such a step. Let
go to add the change to the preview, or press Esc. With the keyboard: Tab to the handle, then the
arrow keys, Home or End, and Enter. Click the line's label for the details and **Set to …**;
**Back to 1%** takes a higher share out again. For Codex the line moves in steps of 500 tokens, up
to 10,000, and **Back to the default** takes it out.

Kitden writes `skillListingBudgetFraction` in your Claude Code user settings
(`~/.claude/settings.json`, or the folder `CLAUDE_CONFIG_DIR` names), or `[skills]
max_context_tokens` in Codex's `config.toml`, for all projects, with a backup and Undo. Restart
Codex after it. Kitden has not yet checked on a real chat that Claude Code and Codex follow the
value it writes: your next chat's list on Context shows whether they did. Kitden does not offer a
limit when `SLASH_COMMAND_TOOL_CHAR_BUDGET` is set, when a project's own settings set the share,
or when the last chat's limit is not known; the page says which.

**When your setup changed after the last chat,** the last chat stays as it was, and two lines
under it say what Kitden expects now:

> Your skills changed after this list was sent. Start a new chat to see the new list.
>
> **Estimate:** On a 1M window, 23 of 96 skills would show only a name. The agent may not use them.

The bar, then named **Skill list now, estimate**, shows that estimate. When Kitden can only count
the descriptions, not rebuild the list, it says "about 3 of 92" and cannot name them. When it
cannot estimate at all, it says why. **How this is counted** has the details.

`kitden show context`, which the plugin's `context` skill runs, prints the same verdict and each
skill's description, so your agent sees it too.

## Add from the catalogs

**+ Add** in Library and **+ Add servers** in Gateway open one catalog: **skills.sh**,
the **official MCP Registry**, the Claude plugins marketplace, any public GitHub repository you
add, and what is already **On this computer**. Click a result to preview it, or drag it onto a client
or the gateway. Skills come from a pinned GitHub commit, plugins use the client's own installer,
and MCP servers go to the Kitden gateway, so every connected client gets them.
See [online sources](discovery.md) for formats and limits.

- **Tokens:** a server asks for exactly the value it needs. Kitden checks it against the server
  before Apply and keeps it in the **macOS Keychain** or the **Linux keyring**. A secret
  longer than about 1,970 bytes does not fit the macOS Keychain: Kitden says so and changes
  nothing.
- **Browser sign-in:** **Sign in** opens the server's page; Kitden catches the answer itself
  and refreshes it later. A server that allows no sign-in for Kitden asks for an API key instead.
- **Not ready yet:** it waits in the preview; Apply writes the rest. **Details** show each secret
  by name, only its first and last characters, with **Replace** and **Remove**.
- **A key added later:** when a catalog says a server in the gateway now needs a key it does not
  have, the map shows **Needs key** and **Add access…** comes with the key's name filled in.

## Share a server between your agents

Open **Gateway** to share MCP servers and turn individual tools on or off for each project.
Pick several with a band or Shift-click and drag them in together. An agent that calls a tool
that is off is told "<name> is turned off in Kitden."

- **Strict mode:** in a server's **Details → More**, **Turn strict mode on…** turns off every tool
  without a rule of its own, and the tools the server adds later start off. Then turn on only the
  tools you want.
- **Calls:** a tool's **Details** say how often agents called it through the gateway and when last
  ("12 calls · last today 10:02"). Kitden counts only calls that go through the gateway.

A server outside the gateway has an on/off switch only in Codex. Kitden has no switch for one in
Claude Code (its `/mcp` panel turns one on or off per project) or Cursor, and the **Details** say
so. In the gateway every server gets a switch.

If the gateway already has a server of that name, moving another one in works only when it is
the same server. A different server of that name is refused until you keep one. A server's
secrets, in its env, headers or arguments such as `--api-key=…`, go to the macOS Keychain or the
Linux keyring; the gateway's settings keep a reference. If a server moved in by an earlier Kitden
still has one in plain text, its **Details** offer **Move secrets to the Keychain…**.

## Review a change. Apply it. Undo it.

Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact
edit; Apply writes it and checks the result. Open **Changes → Undo** to restore it.
If Undo would overwrite newer edits, Kitden stops. When a newer change to the same setting is
still applied, undo the newer one first. When **Apply all** fails, the tray names the change that
did not go through, and why; Kitden puts every file back. Changes also offers **Redo…** and
**See it on the map**.
If an app such as Pen writes a removed server back, the review warns you first and Changes
says it is back. Reloading or closing the page drops what waits in the preview, so the browser
asks first.

## Look first, from the terminal

```bash
uvx --python 3.13 kitden scan
```

Nothing is installed and no page opens. `scan` reads your agents' settings and, for the folder you
run it in, your last chat; with no chat there, your last chat in any folder, and it names that
folder. It changes none of your settings.

It prints one block for each agent, with the problem first: whether the skill list fit, and the
skills that did not. Under it one line says what the agent has on this computer, such as `On this
computer: 2 plugins, 4 skills`. The last lines count the warnings and notes and say what to do
next. `kitden show findings` prints every note, and `kitden scan --json` prints everything the page
shows.

When Kitden has to ask Codex for its plugins, `scan` says so and waits up to 15 seconds.

## Try the sample

```bash
uvx --python 3.13 kitden demo
```

Kitden opens in your browser on temporary sample files. If it does not, open the link printed
in Terminal. Your settings and secrets are not read or changed, even when you press Apply.
The demo starts no real clients or MCP servers. The first run downloads Kitden; the demo
itself stays offline.

1. In **Library → List**, find **superpowers** and press **+** under **Codex**.
2. Review and **Apply**. Codex now has a copy in the sample setup.
3. Open **Changes → Undo** to remove that copy again.
4. Open **Context**: in the sample's last Claude Code chat, four skills showed only a name.

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
To update, use the Update button on the page. Or run `uv tool upgrade kitden` and restart your clients.

With [Homebrew](https://brew.sh) instead, uv is not needed:

```bash
brew install konstantinstarovoytov/tap/kitden
```

To update, use the Update button on the page, or run `brew upgrade kitden`. Homebrew builds
Kitden and its dependencies from source, which takes a few minutes the first time.

## Open the page again, and how it stops

Closing the tab does not end Kitden. Run `kitden` or `kitden open` to open the same page
again: if a page is already running for your home folder, Kitden opens that one, and if not,
it starts one in the background and opens it. A page started that way stops by itself 10
minutes after its last tab closes, unless a change is still being written.

`kitden serve` runs the page in the terminal instead. It stays until you press **Ctrl+C**.

### If Claude Code uses another folder

With `CLAUDE_CONFIG_DIR` set, Kitden reads and writes Claude Code's files in that folder instead of
`~/.claude`. With `CLAUDE_CODE_PLUGIN_CACHE_DIR` set, it reads plugins from there. Start Kitden with
the same variable as Claude Code:

```bash
CLAUDE_CONFIG_DIR=~/.claude-work kitden
```

Kitden does not see a variable set in the `env` of a settings file.

## Stop using Kitden

What you add with Kitden lives in each agent's own settings, in that agent's own format.
Plugins, skills and servers outside the gateway keep working without Kitden.

1. Open **Gateway** and drag each server out of the Kitden gateway onto the agents that
   should have it. Review and **Apply**. **Changes → Undo** of the move does the same.
2. Still in **Gateway**, open each agent's **Details** and press **Disconnect from the
   gateway…**. Review and **Apply**. This takes the `kitden` entry out of that agent.
3. Uninstall: `uv tool uninstall kitden` or `brew uninstall kitden`. The plugin has its own
   [uninstall commands](../plugins/kitden/README.md).

Kitden's own data folder, with its backups, stays until you delete it:
`~/Library/Application Support/kitden` on macOS, `~/.local/share/kitden` on Linux.

## Privacy and limits

What Kitden reads, keeps and sends is in [Privacy](../PRIVACY.md). In short:

- Credentials go to the server they belong to, or to a gateway you move that server into.
- Secrets Kitden keeps are in the macOS Keychain or the Linux keyring: tokens you type, sign-ins,
  and the secrets of a server you move into the gateway. The page shows no more than their first
  and last characters. Moving a server out of the gateway writes its secrets into that client's
  file as plain text, and the review says so.
- Kitden does not look for tokens that sit in plain text in a client's own settings. A server
  you move into the gateway takes its secrets to the Keychain or keyring.
- A backup keeps a changed file as it was, secrets too, in Kitden's data folder, readable only
  by you. Backups stay for 30 days, and the newest 100 changes always keep theirs.
- Undo of plugin removal installs the plugin again, but does not restore its saved options.
- Kitden writes to your home folder, its own data folder, known projects and detected client
  settings folders. The preview shows which files will change.

## What stays the same from 1.0

Kitden is 0.x today, so any of this may still change; the release notes say when. From 1.0,
these change only in a new major version:

- **The commands:** `kitden` (the same as `kitden open`), `kitden serve`, `kitden demo`,
  `kitden scan`, `kitden show` with `setup`, `findings`, `item`, `projects` and `context`, and
  `kitden mcp`, with the options `kitden <command> --help` lists.
- **The tools of `kitden mcp`:** `show_setup`, `list_findings`, `explain_item` and
  `list_projects`. A gateway tool offered under its own name keeps that name while its server
  stays in the gateway, so a server added later cannot take it.
- **Where Kitden keeps its data:** `~/Library/Application Support/kitden` on macOS,
  `~/.local/share/kitden` on Linux. There `gateway.json` holds the gateway's servers and rules,
  `clients.json` the clients you turned off, and `changes` with `changes.log` each change and its
  backups. Secrets are Keychain or keyring items of the service `kitden`.
- **What Kitden writes in a client:** only that client's own settings, in its own format. The
  gateway entry is named `kitden` and runs `kitden mcp`.
- **Undo after an update:** `gateway.json`, `clients.json` and each change record say their
  format (`"version": 1`), and files from an earlier Kitden, which have none, read the same. A
  change made by one 1.x version can be undone by a later 1.x while its backup is kept: 30 days,
  and the newest 100 changes always.

What may still change in 1.x: the page, its tabs and words; the text `kitden scan` prints; the
JSON of `kitden scan --json` and `kitden show`, which can get new fields; the other files in
Kitden's data folder, which it keeps for itself; and how Kitden reads a client when that client
changes its own files ([what Kitden relies on](clients.md)).

## Let your agent read your setup

In Kitden, choose **Let agents read this setup**. Then ask your agent **"show my setup"**.
Kitden's own tools only read. Servers moved into the gateway add their tools, which do what
those servers do.

Already have the `kitden` command? [Add to Cursor](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=).
The plain link is `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

## Report a bug

On GitHub, choose **New issue**, then the **Bug** form. It asks for your Kitden and client
versions, the steps to reproduce it, and what you expected. Remove secrets and private paths
from screenshots and logs. See [Contributing](../CONTRIBUTING.md).
