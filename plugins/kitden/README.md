# Kitden plugin

For Claude Code and Codex. Six skills, so an agent can tell you what your coding tools load, why,
and whether your skills fit in the context.

The plugin has no MCP server and nothing that runs by itself: no hooks and no commands. Its
skills run the command `kitden show`, which changes none of your settings.

The plugin does not hold the program. It needs [Kitden](https://pypi.org/project/kitden/) 0.7.2
or later on this computer. When Kitden is missing, the agent asks before it installs anything.
You can also install it yourself:

```bash
uv tool install --python 3.13 kitden
```

Or with Homebrew: `brew install konstantinstarovoytov/tap/kitden`. Kitden runs on macOS and
Linux. It is open source under Apache-2.0, and its code is in the same repository as this plugin.

## What the skills do

| Skill | What it does |
| --- | --- |
| `show-setup` | Answers what each client loads in a project, where an item comes from and why it loads twice. |
| `audit` | Compares what loads with the project you are in and lists what to turn off. It judges by what the project is; Kitden does not tell how often an item is used. |
| `context` | Says whether your skills fit in the client's skill list, and which ones lost their description. |
| `before-install` | Before you add a server, plugin or skill, looks whether a client already has it. |
| `open` | Opens the Kitden page and gives you the link. |
| `install` | Installs or updates Kitden when a skill needs it. It shows the line and asks first. |

The skills change nothing in your settings. To change something, the agent sends you to the
Kitden page, which previews, backs up and can undo every change.

In Claude Code each skill is also a command, such as `/kitden:audit`.

## Try it

- "What MCP servers and skills do you load in this project?"
- "Why does this skill load twice?"
- "Do my skills fit in the context?"
- "Is the github server already set up somewhere?"
- `/kitden:audit`
- `/kitden:context`

## What it reads

`kitden show` reads the settings files of Claude Code, Codex and Cursor on this computer. Claude
Code's files are read from `~/.claude`, or from the folders that `CLAUDE_CONFIG_DIR` and
`CLAUDE_CODE_PLUGIN_CACHE_DIR` name, which can be anywhere on this computer. This
includes the limits Claude Code's settings set for the skill list (`skillListingBudgetFraction`
and `skillListingMaxDescChars`); only the Kitden page, after your Apply, can raise the first,
and Codex's `[skills] max_context_tokens`. For
the context check it also reads what the client sent in your last chats, from the client's own
chat files, the skills the Claude app gives Claude Code, from the app's own folder, and Codex's
model list (`models_cache.json`), for the size of its context window. For Codex it also reads
the skill files of a plugin's newest version, when an update removed the version the chat used.
For a skill built into Claude Code, which has no file, it reads the description an earlier chat
sent, from the newest chat files.
It uses them to size the skill list and keeps none of it. It also reads each skill's description
from its `SKILL.md`, and its `when_to_use` only for its size, and
`kitden show context` prints it, together with the names of the skills that did not fit in your
last chat. When the folder you run it in has no chat, `kitden show context` reads your last chat
in any folder and also prints that folder's path (with `--project` it stays with that folder).
To learn versions and plugins it may run the clients' own
commands, such as `claude --version` and `codex plugin list`. A client you turned off on the
Kitden page is not read, and its commands are not run. The first run can wait up to
15 s for Codex and says so on stderr. The answer (each plugin's id and whether it is on) is kept
in one file in Kitden's own data folder, so a run within the next hour, while Codex's
`config.toml` is unchanged, does not wait. It changes no client settings and does not go
online. Secret values, such as tokens in a server's settings,
are replaced with `[secret]`.
A skill's description is printed as written, so keep secrets out of it. There is no account and
no telemetry.

What `kitden show` prints goes into the chat, so your agent and the company behind it see it,
under their own privacy terms. This includes the folder path above.

The install is the one step that goes online, and only after your yes. The agent uses uv or
Homebrew. With neither, it gives you a link to Kitden's install steps.

## If something goes wrong

- **The agent says `kitden` is not found.** Say yes to the install, or run the install line
  above, then open a new terminal.
- **A skill says Kitden is too old.** Run `uv tool upgrade kitden` or `brew upgrade kitden`.
- **Anything else.** Open an issue at https://github.com/KonstantinStarovoytov/kitden/issues.

## Install and remove

| Client | Install | Remove |
| --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | `codex plugin remove kitden@kitden` |

The Claude Code line needs Claude Code 2.1.275 or later (checked 2026-11-05).

Removing the plugin leaves Kitden and every other setting as they are.
