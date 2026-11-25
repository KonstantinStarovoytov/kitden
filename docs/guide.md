# Kitden guide

What Kitden does, step by step, and where its limits are. The [README](../README.md) shows
the short version.

Kitden can change your client settings. Only add plugins and MCP servers you trust:
they can run code with your permissions. Undo does not reverse actions a tool already ran.

## See what each agent loads

Open **Library** and choose **All projects** or one project. **List → Differences** shows
what differs between Claude Code, Codex and Cursor. Click an item for its **Details**.
On the map, a group of two or more starts folded as a stack of cards. Press a stack to open it;
a big group shows five at a time, with the rest in the stack below. **Collapse** folds it again.
The Gateway's groups work the same way.

| What | How to manage it |
| --- | --- |
| **Plugins and skills** | Use **+ Add**, or drag an item onto another client. Turn it on or off, choose its scope, or remove a copy in **Details**, where the client supports it. A Claude Code skill can also be off in one project only, beside your other skill rules. **Add missing plugins and skills…** fills gaps across clients. |
| **Marketplaces** | Browse their plugins and skills. **+ Add → Add a marketplace…** adds a GitHub source. **Details → More → Commands…** has update and remove commands to copy. |
| **Hooks and instruction files** | See which client loads them and where they come from. **Library → Instructions** shows files and imports, plus commands and agents. With **All projects** it shows the files loaded in every project, and a quiet line names a client that loads none; pick a project to see its own files. A project's `CLAUDE.md` shows Cursor beside Claude Code, and Codex shows no project files in a project marked untrusted. When a client is turned off in Kitden, the tab says so. A Claude Code hook that `disableAllHooks` turns off shows as off. Kitden only reads these; edit them in your editor. |

On the map each client's block says what it loads there: its plugins and skills ("5 plugins ·
62 skills"), or its hooks when a hook is all it has ("1 hook"). On **Instructions** it counts
the client's instruction files ("3 files"); commands and agents are not counted, and a client
that has only those says "Commands and agents only". A client with nothing says "Nothing
loaded".

The preview names the clients and projects affected. Adds on the map go to all projects;
the List offers a project scope where supported. Start a new client session to load a change.

## Choose your clients

If you use only some of Claude Code, Codex and Cursor, tell Kitden. Press
**Choose clients…** at the top right of the **Overview**, the **Library**, the **Gateway** or
the **Context** page. Each of these pages says which clients are turned off. **Details** lists the three clients, each with a
switch. Turn a client off and Kitden stops reading it: it runs none of the client's commands,
and the client leaves the Overview, the Library, the Gateway, **Agents** and `kitden scan`. Turn
it on and it comes back. A toast with **Undo** follows each switch. Kitden keeps at least one
client on, so the last switch stays disabled.

Nothing in a client's own settings changes. If the client still has the `kitden` entry, its row
says so: disconnect it on the Gateway first if you want that gone. A change you made to an off
client stays in **Changes**, but its Undo waits: it says "Turn Codex on to undo this." A preview
you had not applied yet waits the same way. Kitden
keeps your choice in `clients.json` in its data folder, so it holds after a restart. The small
**−** on a Library List column is another thing: it hides that column in this browser only,
Kitden still reads the client, and **Show** brings the column back.

## Check that your skills fit

Open **Context** to see whether each client's skill list fit in its last chat: for Claude Code
that is the chat that last got a full skill list, one that was started or resumed. Claude Code and
Codex let that list use only a small part of the context window. Claude Code then shows some
skills by name only; Codex shortens descriptions and, past that, leaves skills out. Kitden reads
the skill list from the last chat log, plus the settings, skill files and use counts it needs
to size and check that list; it keeps none of it and sends nothing. Estimates for another
window, or for a switch you are about to make, show only while Kitden's rule rebuilds that last
list; a new limit also gets one from a count (below). Claude Code's log does not say the window, so Kitden names it only when one window alone
gives that list. When Claude Code's settings set the limit, with `skillListingBudgetFraction` or
`SLASH_COMMAND_TOOL_CHAR_BUDGET`, Kitden uses that limit, and `skillListingMaxDescChars` for the
length of a description. Cursor gets no verdict, because Kitden cannot see what Cursor sends. Skills
whose descriptions are sent go from grey to orange with the length of their description, so the
few that take most of the list stand out. A skill's **Details** shows its description, with
the part the agent did not get in grey. There you can also
switch it to **On**, **Name only** (Claude Code) or **Off** where the client
allows it; Cursor has no switch. A skill built into Claude Code, such as `dataviz`, is marked
**built-in**: it is not a file, so the Library does not list it, but most have the same switch,
for all projects. A skill of a plugin that Claude Code installed follows its plugin: its Details
say what the plugin holds and offer **Turn off** for the whole plugin. When Kitden has no switch
for a skill, such as one the Claude app adds, its Details say so and why. Your own and built-in
Claude Code skills that are off, and so were not in the last list, wait under **Turned off**,
where you can turn them on again. A skill that a project's own settings set has no switch here.
The change goes through preview, **Apply** and **Undo** like any other. The **Overview** shows a card when a last chat's list
did not fit. `kitden show context`, which the plugin's `context` skill runs, also prints each
skill's description, so your agent sees it too. With no chat in the current folder, it shows the
last chat in any folder and names that folder; with `--project` it stays with that folder.

When some Claude Code skills showed only a name because the list ran out of room, the limit
line on the skill list's bar has a handle. Drag it to the right: a second line, for your next
chats, moves from share to share of the window (1%, 1.1%, 1.2%, 1.3%, 1.4%, 1.5%, 1.7%, 2%,
2.5%, 3%, 3.5% and 4%, the most Kitden offers), and a note beside it says what each step gives,
such as "1.4% · all 20 fit · about 650 more characters per chat". It snaps to the step where
every description fits, which a small mark shows. Let go to add the change to the preview, or
press Esc to leave it. Drag it back to where it started to take the change out. With the
keyboard, Tab to the handle, use the arrow keys and press Enter. Click the line's label (or the
handle, or press Enter on it without moving) for the details: the share of the context window
now, the first share above it at which every description fits (skills you set to Name only or Off
stay as they are), and about how many more characters and tokens every chat then costs, with
**Set to 1.4%** (or the share shown). When your user settings set a share above 1%, drag the
line back to 1% or press **Back to 1%** to take it out again. You can also drag it down to any
share of the list between 1% and the one you have, such as 1.2% from 1.3%; Codex's line does the
same in steps of 500 tokens. After Apply, the last chat keeps
the limit it was sent under, the next chats' line shows the new one, and the page says the
limit changed and what Kitden expects from your next chat. A share in your settings that is not
on the list, such as 4.5% from an earlier Kitden or one you wrote by hand, still works: Kitden
shows it as the limit now, offers the shares of the list above it (none above 4%), and **Back to
1%**.

The line also works when Kitden cannot replay the last chat's list exactly: a newer Claude Code
may choose other descriptions, or a listed skill may have no file Kitden can find. Then Kitden
counts what all descriptions need. A step that has room for all of them says "all 92 fit"; a
step that does not says only "not all fit", because without the replay Kitden cannot tell which
ones it would keep. The details say that it is a count, and how many skills have no description
Kitden can find: those count at the longest a description can be (1,536 characters, or your
`skillListingMaxDescChars`), so the share may be a step higher than you need. A skill built into
Claude Code has no file: when an earlier chat's list sent its description, it counts at that
length, and the details say how many count so. The place of today says how many skills showed
only a name ("1.3% now · 2 of 92 show only a name") when the last chat was sent under today's
limit and no skill joined since. When the limit was changed after the last chat, the cost is
measured from what the list uses at today's limit, not from what that chat used.

The share is for your next chats, so skills you added or turned on after the last chat are
counted too, and the details say how many.

Codex's line works the same way, in tokens: when Codex cut descriptions short or left skills
out, drag it in steps of 500 tokens, up to 10,000, the most Codex allows; it snaps to the
smallest limit at which no description is cut and no skill is left out. Kitden writes
`[skills] max_context_tokens` in your Codex `config.toml` (for all projects), with a backup and
Undo; **Back to the default** takes it out, so Codex uses 2% of the window again. Restart Codex
for it to take effect. Kitden writes `skillListingBudgetFraction` in your user
settings (`~/.claude/settings.json`), for all projects, with a backup and Undo. Your next chat
shows the real list. Kitden does not offer it when `SLASH_COMMAND_TOOL_CHAR_BUDGET` is set, when
a project's own settings file sets the share, when the limit of the last chat is not known, when
everything fits, when by its count everything fits although the chat left descriptions out, or
when even 4% would not fit every description; "How this is counted" then says which. For
Codex: when there is no estimate, when everything fits, or when even 10,000 tokens would not fit
every description.

## Add from the catalogs

**+ Add plugins** in Library and **+ Add servers** in Gateway open one catalog: **skills.sh**,
the **official MCP Registry**, the Claude plugins marketplace, any public GitHub repository you
add, and what is already **On this computer**. Click a result to preview it, or drag it onto a client
or the gateway. Skills come from a pinned GitHub commit, plugins use the client's own installer,
and MCP servers go to the Kitden gateway, so every connected client gets them.
See [online sources](discovery.md) for formats and limits.

- **Tokens:** a server asks for exactly the value it needs. Kitden checks it against the server
  before Apply and keeps it in the **macOS Keychain** or the **Linux keyring** only. A secret
  longer than about 1,970 bytes does not fit the macOS Keychain: Kitden says so and changes
  nothing.
- **Browser sign-in:** **Sign in** opens the server's page; Kitden catches the answer itself
  and refreshes it later. A server that allows no sign-in for Kitden asks for an API key instead.
  A sign-in too long for the macOS Keychain is not saved; give the server a token in a header
  instead, if it takes one.
- **Not ready yet:** it waits in the preview; Apply writes the rest. **Details** show each secret
  by name, only its first and last characters, with **Replace** and **Remove**.
- **A key added later:** when a catalog says a server in the gateway now needs a key it does not
  have, the map shows **Needs key** and **Add access…** comes with the key's name filled in.
  Kitden learns this when you add the server from a catalog, find it there again, or press
  **Rescan** (it then asks the Official MCP Registry about each server by its name).

## Share a server between your agents

Open **Gateway** to share MCP servers and turn individual tools on or off for each project.
Pick several with a band or Shift-click and drag them in together. Library works on its own.
An agent that calls a tool that is off, by a switch, a project rule or strict mode, is told
"<name> is turned off in Kitden."
A server that must start in its own folder starts there in the gateway, so it also works in
Cursor, which has no such setting.
A server's secrets, in its env, headers or arguments such as `--api-key=…`, go to the macOS
Keychain or the Linux keyring; the gateway's settings keep a reference. If a server moved in by
an earlier Kitden still has one in plain text, its **Details** offer **Move secrets to the
Keychain…**.

## Review a change. Apply it. Undo it.

Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact
edit; Apply writes it and checks the result. Open **Changes → Undo** to restore it.
If Undo would overwrite newer edits, Kitden stops. Changes also offers **Redo…** and
**See it on the map**.
If an app such as Pen writes a removed server back, the review warns you first and Changes
says it is back.

## Look first, from the terminal

```bash
uvx --python 3.13 kitden scan
```

Kitden is not installed and no page opens. `scan` reads your agents' settings and, for the
folder you run it in, what they sent in your last chat. With no chat in that folder, it reads
your last chat in any folder and names that folder. It changes none of them. It asks each agent
for its version, and Codex for its plugin list, and keeps the versions and the plugin list in
two small files in Kitden's own data folder. If Codex has to be asked, it says so on stderr and
waits up to 15 seconds. A run within the next hour, with unchanged Codex settings, does not
wait; after an hour Kitden asks again, because a plugin switched in Codex on another computer
does not change your settings file. It prints one block for each agent, with the problem first:
whether the skill list fit in that chat, and the names of the skills that did not fit (Claude
Code and Codex). Under it, one line says what the agent has on this computer, such as `On this
computer: 2 plugins, 4 skills`. The two skill numbers can differ, and a line under it says why:
the first counts the skills Kitden found, in all your projects; a chat's list has one project's
skills, plus the ones the agent adds, such as the skills built into Claude Code. The Claude
Desktop app's Code tab loads what Claude Code loads, so it has one line under Claude Code, with
the MCP servers that only the app has. Skills you set to Name only are not listed. A Codex
skill whose plugin update changed its description after the chat is not counted as cut: the
line says Kitden cannot tell for it. When Kitden cannot tell at all (Cursor, or no chat yet),
the line says why. Then one line names the warnings and counts the notes, which need no fix;
`kitden show findings` prints them all. The last line says what to do: turn off the skills you
do not use when some did not fit, or fix a warning, in `kitden open`. Before Kitden is
installed, run these with `uvx --python 3.13` in front. A client you turned off in Kitden is
not read and gets one line, `Codex: turned off in Kitden`; `kitden scan --json` lists it with
`"status": "off"`. `kitden scan --json` prints everything the page shows.

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
minutes after its last tab closes, unless a change is still being written. Open it again
after that and Kitden starts a fresh one.

`kitden serve` runs the page in the terminal instead. It stays until you press **Ctrl+C**;
closing the tab does not stop it. Only one page runs for a home folder, so `kitden` while
`kitden serve` runs opens that page.

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

The short version for the plugin and the program is in [Privacy](../PRIVACY.md).

- The page runs locally at `127.0.0.1`, with a private access link. No account or telemetry.
- Credentials go to the server they belong to, or to a gateway you move that server into.
  Secrets you type or sign in with are kept in the macOS Keychain or the Linux keyring only;
  the page never shows more than their first and last characters. Kitden masks secret fields and known token
  formats in its page and logs.
- Kitden goes online only to reach remote servers, the catalogs you open, the GitHub
  sources you add, and the Official MCP Registry when you press **Rescan**. Nothing from a
  catalog runs during search or download.
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

On GitHub, choose **New issue**, then the **Bug** form. It asks for your Kitden and client
versions, the steps to reproduce it, and what you expected. Remove secrets and private paths
from screenshots and logs. See [Contributing](../CONTRIBUTING.md).
