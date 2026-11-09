# Do your skills fit?

Date: 2026-11-09. The owner's choices come from chats on 2026-11-06 to 2026-11-08. The rest
are the writer's calls, marked "(call)". The prototype is `design/kitden-context.html`, and
every state is in `design/kitden-context-states.html` (both untracked, open them in a
browser). Older concepts are in `design/kitden-context-concepts.html`.

## Why

Every chat starts with a list of the user's skills. The agent reads that list to pick a
skill. Each client lets the list use only a small part of the context window. When the list
is too long, the client quietly drops or cuts descriptions, and the agent may never pick
those skills. Nobody sees this happen. Kitden already shows what each client loads, so it can
show whether the list fits and help fix it with the switches Kitden already writes.

The owner's top rule for this screen: never deceive the user. A number either comes from what
the client really sent, or it is an estimate that Kitden has just checked against what the
client really sent. Anything else is not shown.

## Goals

1. For Claude Code and Codex, show what the client really sent in the user's last chat: which
   skills kept their description, which showed only a name (Claude Code), which were cut short
   or left out (Codex).
2. Show an estimate for another window size, and for changes the user is about to apply, only
   while Kitden's copy of the client's rule rebuilds the last real list exactly.
3. Let the user change a skill's state on this screen. The change goes into the normal tray
   (preview → Apply with a backup → verify → Undo).
4. For Cursor, say plainly that Kitden cannot tell, and still list the skills.

## Non-goals

- Changing a client's limit (`SLASH_COMMAND_TOOL_CHAR_BUDGET`, Codex
  `skills.max_context_tokens`). The screen names the limit and where it comes from, but does
  not offer to change it. (call)
- Measuring the rest of the window (system prompt, tools, MCP, the chat). The only source is
  Claude Code's own `/context`, which means starting `claude -p "/context"`; the owner left it
  out of the first version (2026-11-09). The bar still labels that part "Rest of the window".
- Exposing the result to agents through Kitden's MCP tools. (call)
- Windows. Linux works if the log folders are the same; tests do not promise more.

## Anti-goals

- A verdict with no source. No "fits" or "does not fit" for a client whose rule or log Kitden
  cannot read.
- Showing an old result as new. Every result names the date of the chat it comes from.
- Reading or keeping chat text. Kitden reads only the skill list part of a log, keeps none of
  it on disk, and sends nothing anywhere.
- Starting a client, or a chat, to get data.

## What the screen shows

The layout is the prototype's "Zoom + Two sides" (owner's pick, 2026-11-06). Top to bottom:

1. **Title** "Do your skills fit?" and a lede that says what it is for, in one line per client:
   "Every chat starts with a list of your skills. The agent reads it to choose the right skill.
   Claude Code lets this list use 1% of the context window." (Codex: 2%. Cursor: "does not
   publish a limit for this list.") The owner asked that the page be obvious at first look,
   with no extra words.
2. **Client chips** at the top: Claude Code, Codex, Cursor. A lamp on each chip shows its
   verdict for the main window: green fits, amber does not, grey unknown.
3. **Window cards**, one or two per client. The first is the last chat's window and is marked
   "Last chat · Nov 6" (a fact). The second is the other common window, marked "Estimate".
   Each card says its result on its face, so the user never has to switch to find the problem.
   Codex also shows a card for a limit set in `config.toml` when there is one.
4. **Verdict**, one sentence. Facts say "was"; estimates say "would" and start with
   "Estimate:" ("After Apply, estimate:" while the tray holds changes from this screen).
5. **Zoom picture.** The whole context window as a thin bar; its 1% (or 2%) opens into the
   skill list bar below. Each piece is one skill, as wide as its characters. A white line
   marks the limit with its size ("Limit: 8,000 characters"). The part past the line is
   hatched amber and labelled "Over the limit: not sent" (Codex: "cut off"); room left is
   labelled "Free". The rest of the window is labelled "Rest of the window".
6. **Two sides.** Two columns of skill pills: "Description sent" and "Name only" (Codex:
   "Full description" and "Cut short"; Cursor: "The agent can pick it" and "Only when you
   ask"). The pills use the same marks as the bar. Hovering a pill lights its piece on the bar
   and the other way round.
7. **Details** for a clicked skill, in the usual floating panel: its size, its source, its
   state switch and one sentence on what the switch does ("Name only frees 1,538 characters.
   The agent no longer sees when to use it.").
8. **"How this is counted"**, folded: where the last list came from, the rule and its client
   version, the date the rule was checked, and what is not measured.

The words, states and numbers on every tile of `kitden-context-states.html` are the target.
The yellow "Example: …" bar in the prototype exists only in the mockup; the product never shows
an invented state.

### Where it lives

A screen of its own, not a third view beside Map | List: those show the same setup in two
ways, and this answers a different question (owner, 2026-11-09). The owner named two places:
on the Overview, without getting in the way of anything there, or as its own tab. The writer's
call takes both, each where it fits:

- **Its own place in the rail**, after Library, named "Context" (owner, 2026-11-09: a noun
  like the others, and it still fits when the rest of the window is measured later). It has
  the same top bar; the project picker decides which chat is read (see "Which chat"). (call:
  the place in the rail)
- **On the Overview, only when something is wrong:** one card per client whose last chat
  showed names only, cut descriptions or left skills out ("27 skills were cut short in your
  last Codex chat"), with "Show…" opening Context on that client. No card when everything fits,
  and none for Cursor, so the Overview gains nothing to read on a good day. (call)

The prototype shows it as its own rail item, Context. The older concepts file still draws it
under Library; only the prototype and the states page are the target.

### Switches per client

| Client | States | Written as | Exists in Kitden |
|---|---|---|---|
| Claude Code | On, Name only, Off | `skillOverrides.<name>`: `"name-only"` or `"off"` | Off only |
| Codex | On, Off | `[[skills.config]]` with `enabled = false` | Yes |
| Cursor | none on this screen | — | — |

- Claude Code's `skillOverrides` does not touch plugin skills (docs checked 2026-10-26). A
  plugin skill shows no switch here, and its Details say to turn the plugin off in the
  Library. (call)
- Name only and Off go through the same files, scopes and project rules as today's Off
  (`claude_code.py`, `library-rules.js`); Name only is one more value, not a new mechanism.
- Cursor's "Only when asked" is the skill's own `disable-model-invocation` line. Changing it
  edits the skill file, which other clients may share, so Cursor gets no switch here. (call)
- Claude Code also has `"user-invocable-only"` in `skillOverrides`, and a skill file can say
  `disable-model-invocation: true`. Such a skill is shown with its state as it is ("Only when
  you ask"), in the column the real list puts it in; the builder confirms where with a test
  chat, and the rule check covers it. Choosing another state is a normal reviewed change that
  shows the old value, so nothing is overwritten unseen. (call)
- Name only is also shown outside this screen as a fact: in the skill's Library Details and
  in what `show_setup` and `explain_item` return. The Library's Map and List keep showing the
  skill as On, which it is. (call)
- Clicking a pill and choosing a state adds a row to the tray. The bar, columns and verdict
  redraw at once as "After Apply, estimate", naming both sides of a swap: "xlsx gets a
  description. skill-creator loses its description." (the loser is lit amber).
- Apply's toast says: "Applied N changes. The backup is in Changes. Your next chat will show
  the real list."

## Where the facts come from

All checked on one Mac, Claude Code 2.1.311 and the Codex app, 2026-11-06 to 2026-11-08.

### Claude Code

- **Last list.** Each chat is a JSONL log under `~/.claude/projects/<folder>/<session>.jsonl`;
  a chat's subagents log under `<session>/subagents/`, which Kitden skips. The sent list is
  an entry with `attachment.type == "skill_listing"`. Seen on 2026-11-09 (Claude Code
  2.1.309): the entry has `timestamp`, `version` (the client's), `entrypoint`
  (`claude-desktop` for the app), `cwd`, `isSidechain`, and an `attachment` with `content`
  (the list as the agent saw it), `names`, `skillCount`, `digests` and `isInitial: true`.
  One chat held four such entries, each a full list (`names` as long as `skillCount`). The
  last full one counts. An entry with `isInitial` not true was never seen, so Kitden treats it
  as a shape it does not know. The model is `message.model` on the chat's assistant entries.
  Kitden reads only these fields.
- **Which chat.** The newest top-level log, by its last write, that holds a full list and is
  not a sidechain. A log with no list yet (a chat just opened) is skipped for the next older
  one. Runs that are not a person's chat (`claude -p`, the Agent SDK) are skipped by their
  `entrypoint`; the builder confirms those values with a test run. With a project picked, only
  that project's logs count; with All projects, any, and the screen names the project. (call)
- **Date.** The `timestamp` of the list entry, not of the file.
- **Surface.** The terminal and the Claude app send different lists (61 and 64 skills on
  2026-11-07; `code-review` had a longer description in the terminal). The screen names the
  surface from `entrypoint` ("in the Claude app", "in the terminal"); an unknown value is not
  named.
- **Rule** (read from the 2.1.311 binary, checked 2026-11-06 and 2026-11-07):
  - Limit = window × characters per token × 1%. Characters per token: 4 for models up to the
    4.6 family, 3 for newer ones. 1M on Opus 5.5 is 30,000 characters; 200K on an older
    model is 8,000.
  - Each description is cut at 1,536 characters (docs).
  - If everything fits, everything is sent. If not, built-in skills and Name only skills keep
    their entry, and the rest keep descriptions in order of `usageCount × max(0.5^(days/7),
    0.1)` (uses from `~/.claude.json`, halved every 7 days since last use) until the limit.
    The rest show only a name.
  - Names count with their plugin prefix. Built-in skills may push the list over the limit
    on their own.
  - Two test chats with `SLASH_COMMAND_TOOL_CHAR_BUDGET` at 8,000 and 12,000 (2026-11-07)
    matched the rule skill for skill.
- **Window.** From the chat's model. Kitden keeps a small dated table of model → window and
  characters per token; a model not in it, or one offered with two windows that the log
  does not tell apart, gets the fact but no estimate. (call)
- **Limit setting.** `SLASH_COMMAND_TOOL_CHAR_BUDGET` sets the limit. Kitden reads it from
  `env` in Claude Code's settings files. A value set in the shell is out of Kitden's sight;
  "How this is counted" says so. (call)

### Codex

- **Last list.** Chat logs are JSONL files under `~/.codex/sessions/YYYY/MM/DD/`. Seen on
  2026-11-09 (Codex app, `cli_version` 0.163.0-alpha.11): the first entry is `session_meta`
  with `timestamp`, `cwd`, `originator`, `source`, `thread_source` (`user` for a person's
  chat), `cli_version` and `context_window` (only an id, not a size); `turn_context` entries
  carry `model`. The sent list is the `<skills_instructions>` text inside a `response_item`
  message with role `developer`. A skill's `file:` path is relative to a root alias defined in
  the same block (``- `r2` = `/abs/path` ``, checked 2026-11-09). Kitden reads only these.
- **Which chat.** As for Claude Code: the newest log by its last write that holds a list and
  has `thread_source` `user`. One thread can run for days, so the date is the list entry's.
- **Compressed logs.** 110 of 114 logs here are `.zst`, but only older ones; the newest are
  plain. Kitden reads plain files and does not open `.zst` (Python 3.13 has no zstd in its
  standard library). (call)
- **Rule** (from `codex-rs/ext/skills/src/render.rs`, checked 2026-11-06): the list may use 2%
  of the window, at about 4 bytes per token. Each line pays for its name and path. When too
  long, Codex cuts every long description to one shared length; when even that fails, it
  removes all descriptions and drops skills.
- **Window.** `session_meta.context_window` holds only an id. The window comes from Codex's
  `models_cache.json`: `models[].slug` of the chat's model → `context_window` (checked
  2026-11-09). That was 272K for the default model on 2026-11-06. The 2% applies to 272K, not
  the 258,400 in the logs: only that rebuilds the real list size (5,440 tokens).
- **Limit setting.** `skills.max_context_tokens` in `config.toml`, up to 10,000 tokens
  (Codex docs). When set, it is the limit.
- The real list of 2026-10-30: 27 of 58 descriptions cut to 366–370 characters; the rule gave
  the same 27.

### Cursor

No published limit and no log found that shows the sent list (checked 2026-11-06). The screen
says "Kitden cannot see what Cursor sends, so it cannot tell if your skills fit." and lists
the skills from files, split by "Only when asked".

## The check that guards every estimate

Before showing any estimate for a client, Kitden runs its rule on the last chat's window and
compares the result with the last real list: the same skills sent in full, the same skills
name-only or cut, the same cut length. (call: compare skill sets and states, not byte counts.)

What the rule runs on (call):
- the skill names from the log, not the skills on disk now;
- each sent text from the log; the full size of a skill that showed only a name, from its
  file on disk. A name-only skill with no file Kitden can find (one only the app has) means
  no check, so no estimate;
- for Claude Code's order, use counts from `~/.claude.json` as they are now (Kitden cannot see
  older ones), aged from the chat's own timestamp, not from today.

- **Match:** estimates show.
- **No match:** the fact stays; estimate cards and the "After Apply" preview turn off, and the
  screen says "Kitden cannot check its estimate against your last chat, so it shows none."
  This covers a client update that changed the rule, skills or use counts that changed since
  that chat, and a skill Kitden cannot size. The words do not guess which one. (call)
- **Everything fit:** then any limit at or above the list's size rebuilds it, so the check
  cannot prove the limit. "All 64 skills were sent" stays a fact; the room left and the other
  window are estimates from the window table and say so ("Estimate: about 2,710 characters
  left"). (call)

## States

From `kitden-context-states.html`. Each must be reachable in tests with fixture logs.

| Client | State | What the screen says |
|---|---|---|
| Claude Code | Everything fits | "In your last chat on Nov 6, all 64 skills were sent with their descriptions." Then "Estimate: about 2,710 characters left before the limit." |
| Claude Code | Too many | "In your last chat on Nov 7, 46 of 61 skills showed only a name. The agent may not have used them." |
| Claude Code | Rule no longer matches | The fact, and "Kitden cannot check its estimate against your last chat, so it shows none." |
| Claude Code | No chat yet | "No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code sent." Skills from disk, no verdict. |
| Claude Code | Log format changed | "Kitden cannot read chat logs of Claude Code 2.2.0 yet, so it shows no result and no estimate." |
| any | No skills | "There is nothing to fit." |
| Codex | Cut short | "In your last chat on Oct 30, 27 of 58 descriptions were cut to 366–370 characters. The agent saw only their start." |
| Codex | Everything fits | "…all 58 skills were sent with full descriptions. 3,224 tokens were left before the limit." |
| Codex | Skills left out | "…Codex removed every description and left 14 of 58 skills out of the list. The agent did not see them at all." |
| Cursor | No verdict | "Kitden cannot see what Cursor sends, so it cannot tell if your skills fit." |

"Log format changed" means the newest chat log is from a client version newer than the
ones Kitden knows, and its list entry is missing or has a shape Kitden does not know. Kitden
then does not fall back to an older log: that would show an old result as new. A log with no
list at all from a known version is just skipped (see "Which chat"). (call)

## Constraints

- Follow `docs/design.md` for look and motion, and the owner's motion choices (calm motion,
  one active element, the tray).
- Main view: names, client, action. Paths, rule numbers and log names go behind Details and
  "How this is counted".
- Reading must stay fast: read only the newest log per client (and per project), stream it,
  stop at its end; never read every log.
- Tests use sandbox homes with small fixture logs written for the tests (never copies of real
  chats). Each state above has a test.
- Every changing fact (rule, characters per token, window table, file paths) carries its
  check date in the code, as the repo already does.
- Update ROADMAP.md and `docs/guide.md` when it ships.

## Left to the builder

- The parser for each log, and how it detects a format it does not know.
- How the rule code is split per client, and how the window table is kept.
- How the new page is wired into the rail, the router and the address (`#context?sel=client:<id>`).
- Motion details within `docs/design.md`.

## Decided with the owner on 2026-11-09

- The rest of the window (`/context`) is left out of the first version.
- The screen is its own place, not a Library view; see "Where it lives".
