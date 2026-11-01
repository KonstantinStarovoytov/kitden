# Add button, group drag and sign-in

Date: 2026-11-01. Owner's choices from a chat and a mockup review the same day.

## Why

Finding and adding MCP servers and plugins from the registries is a main feature, but today it
hides behind a small "+ Add" beside a map caption. Moving servers into the gateway one by one is
slow when several clients each have a few. And a server that needs sign-in is simply refused,
so the owner hits a dead end instead of a next step.

The map stays the main place to manage everything. All three parts must use the same signals,
words and motion as the rest of Kitden, so the app feels like one thing.

## Goals

1. An obvious, calm way to open the catalog from the map.
2. Select several servers with the mouse and drag them onto the gateway together.
3. When a server needs access, Kitden finds out what kind (browser sign-in or a token), asks for
   exactly that, and checks it before Apply.
4. One signal language: one look for "needs you", one for "refused", one for "works", one for
   "waiting". Fix today's drift where it touches these flows.

## Non-goals

- A separate catalog page or tab. The catalog stays the panel beside the map.
- Group selection of servers already in the gateway (dragging them out together). Later, if asked.
- Group selection in Library. Later; the same engine should make it easy.
- Changing how the catalog panel itself searches or lists rows.

## Anti-goals

- A loud button that fights the map (the owner rejected a filled action-color button).
- Asking the owner for a header name, or any field that can be filled wrong. A plain token is one
  field.
- A "refused" dead end. A server that needs access is a step, not a failure.
- Writing a secret anywhere but macOS Keychain, or writing any client file outside
  preview → Apply → verify → Undo.

## Order of work

Each part ships on its own, in this order: 1 Add button, 2 group drag, 3a token step,
3b browser sign-in. 3b is the largest and riskiest.

## Part 1. Add button (chosen: A2 + B)

- **Header button.** "+ Add servers" in the Gateway page header, left of Map / List, the same
  height as Map / List (28 px). It is the existing soft-accent button `.btn.add` (accent text and
  edge, clear fill, `--route-soft` on hover), not a new variant. It looks pressed while the panel
  is open, as "+ Add" does today. Press motion is the shared button press.
- **Slot card.** At the end of the Servers column, a card the size of a server block: a "+" tile,
  "Add a server", and the small line "From the catalog". Grey dashed edge (`--wire-strong`), no
  fill, the same "empty" look as `.empty`, so it never reads as a preview. On hover and while a
  server is dragged over it, it takes the accent drop look. It enters with the map like any block.
- Both open the same add panel. The small "+ Add" beside the Servers caption goes.
- Library gets the same pair: "+ Add plugins" in its header and a slot card at the end of the
  plugins column. *(My call: the owner approved this as a guess.)*

## Part 2. Select several servers, drag them together

- **Marquee.** Pressing on empty map space and moving 5 px draws a selection rectangle (solid
  1 px `--route` at 40% on `--route-soft`; not dashed, because dashed means preview). It follows
  the pointer exactly, with no easing. Releasing or Escape fades it out in 120 ms.
- Servers in "Outside the gateway" that the rectangle touches take the selected look
  (`.block.selected`: accent edge, `--route-soft`). Nothing else is selectable by the rectangle.
- Shift- or Cmd-click adds or removes one server. Escape or a click on empty space clears.
  Selection follows the "one active element" rule: a group selection replaces any open Details.
- **Drag.** Pressing any selected server and moving drags the whole group. The originals go to
  .4. Their ghosts gather under the pointer into a stack (up to 3 visible layers, 4 px offset)
  with a small accent count pill, "3 servers". The gateway lights and one "Drop to add" slot opens
  per group (Remote, Local), as for one server today.
- **Drop.** Each ghost flies onto its slot. Each server becomes a preview block, one tray row each.
  A server that two clients both have (neon in Codex and Neon in Cursor, same address) enters
  once. Blocks grow 45 ms apart, total delay capped at 360 ms.
- **Cancel.** A drop elsewhere, Escape or lost focus flies all ghosts back together (180 ms) and
  keeps the selection.
- A server that needs access is not refused here. It goes into preview in the "needs access"
  state (Part 3).

## Part 3. Access: sign-in or token

### What Kitden decides on its own

For each server, Kitden works out what it needs:

1. The registry entry (`server.json`) says which headers it needs, their names and descriptions.
2. Otherwise Kitden asks the server: an answer of 401/403 means it needs access; a
   `WWW-Authenticate` header or the server's OAuth metadata means browser sign-in is possible.
3. If it needs access and has no sign-in, Kitden offers one token field sent as
   `Authorization: Bearer`.

The owner never picks the kind and never types a header name.

### The "needs access" state (same everywhere)

- A preview block or catalog row that needs access shows the amber lamp (`--lamp-warn`) and the
  words "Needs sign-in" or "Needs token". The same words on the map card, the catalog row and the
  tray row. Today's grey "Needs token" in the catalog becomes amber too.
- It has one button: **Sign in** or **Add token**.
- It can still be dragged and dropped. It waits in preview.
- **Apply** says what will happen: "Apply 2 · neon waits for sign-in". The ready changes apply;
  the waiting one stays in preview and in the tray, amber, no shake. This line uses amber, not the
  accent used today for problems in the dock.

### Token

- **Add token** opens a field under the card (or in the catalog row's details, as today).
- One field per value the server needs, labelled with the server's own description (for example
  "Neon API key"). Optional values fold under "More values". The header name shows only under
  Details.
- A plain `Authorization` token: the field takes the token alone. Kitden adds "Bearer " and
  removes it if pasted.
- Kitden checks the token against the server right away, before Apply: "Checking…" with the busy
  ring, then:
  - **Token works**: green lamp, a short green check, and the server is ready.
  - **Refused**: the reason stays under the field (amber icon, plain words, `role="alert"`),
    focus goes back to the field, the field row shakes once (the shared shake).
- On Apply the token goes to Keychain; the gateway entry holds only the Keychain reference, as
  today. Undo removes the entry and the Keychain item.

### Browser sign-in

- **Sign in** opens the server's sign-in page in the default browser. The card says
  "Waiting for browser…" with the busy ring and a Cancel.
- Back from the browser, the card turns to a normal preview with the green "Signed in" lamp and
  check. If it fails or is cancelled: the reason stays on the card, with "Try again".
- Mechanism: the MCP authorization flow (OAuth 2.1 with PKCE). Kitden is the OAuth client and
  catches the redirect on its own local page. Client registration, refresh and storage follow the
  MCP spec and the `mcp` Python SDK's OAuth client support. **The builder checks the current MCP
  authorization spec and SDK API and writes the date checked next to each claim.**
- Tokens from sign-in live in memory until Apply, then go to Keychain. The gateway reads them
  from Keychain and refreshes them. Undo removes them. *(My call.)*
- If a refresh later fails, the server's card in the gateway shows "Needs sign-in" (amber) with
  **Sign in** again, instead of "could not reach".

## One signal language

| Meaning | Look | Words |
|---|---|---|
| Works / on | green lamp | On, Token works, Signed in |
| Off | grey lamp | Off |
| Waiting in preview | dashed accent block or ring | In preview |
| Needs you | amber lamp or triangle | Needs sign-in, Needs token, Needs attention |
| Refused / failed | amber icon + plain words that stay, one shake of the thing refused | "{name} did not accept this token." |
| Busy | busy ring after 150 ms, in place of the button or beside the words | Checking…, Waiting for browser…, Applying 2 of 5 |
| Selected | accent edge + `--route-soft` | |
| Empty place to add | grey dashed, no fill | Add a server |

Fixes that come with this work, because the new flows touch them:

1. **Refused has one look.** Today it is accent in the dock, grey under the token field and red in
   forms. It becomes amber icon + words everywhere these flows reach (dock, token field, add
   forms). Red stays only for the page-level "Kitden itself broke" banner. *(My call.)*
2. **Hint lines use one pattern:** "Click to preview · drag onto the gateway." (no final period,
   as Overview and Changes do). Catalog foot, Library panel foot and map hints follow it.
3. **The map's drop slot** keeps the dashed accent look (it is a preview being made); the new
   "Add a server" card is grey dashed (a place). Dashed accent always means preview.

## Motion

All from today's Calm rules (docs/design.md, Motion); no new tokens.

| Moment | Motion |
|---|---|
| Header button press | shared press (80 ms in, 260 ms spring out) |
| Slot card | enters with the map; hover is a color fade (180 ms) |
| Marquee | follows the pointer; fades out 120 ms |
| Selection | color fade 180 ms |
| Ghost stack | each ghost moves to the stack 200 ms `--calm`, 25 ms apart; count fades in 120 ms |
| Drop | ghosts fly onto slots 200 ms; blocks grow 45 ms apart, cap 360 ms; tray rows the same |
| Cancel | all ghosts fly back together, 180 ms |
| Needs access | lamp color fade 400 ms; the button fades in 200 ms; no pulse |
| Waiting | busy ring after 150 ms; nothing else moves |
| Works / Signed in | check draws 320 ms, lamp fades to green 400 ms |
| Refused | words rise 4 px in 200 ms and stay; one shared shake |
| Partial Apply | the number in the button rolls; the waiting row stays |

Reduced motion: everything lands at once; color and words still change; no shake.

Sources behind these choices (checked 2026-11-01): motion.dev best practices, Emil Kowalski,
impeccable `animate.md`, LottieFiles motion-design. Where they differ from Kitden (springs,
bigger shakes, waiting pulses), Kitden's rules win.

## Settled after the builder check

All of these are my calls, not the owner's; the owner can overturn any of them.

1. **Group drag before Part 3.** Until 3a ships, a group drop takes the servers that are ready
   and leaves one that needs access in place with today's inline reason. 3a then turns that into
   the "needs access" preview.
2. **Partial Apply.** A waiting change is left out of the Apply batch. The batch keeps one backup,
   one verify and one Undo for what it applied; "Applying 2 of 5" counts only those. The waiting
   change stays in the tray and applies with a later Apply.
3. **Local servers.** Secret env values from the registry (`environmentVariables`, which the
   catalog already reads) are part of 3a: same fields, same check where one is possible, same
   Keychain storage. A local server cannot be checked before it runs, so its fields say
   "Checked when the gateway starts it" and Apply's verify does the check.
4. **Sign-in a server does not let Kitden do.** If the server offers sign-in but Kitden cannot
   register as its client (no dynamic registration), and the server lists no token: amber
   "Needs sign-in", with the reason "{name} does not let Kitden sign in yet. It may take an API
   key; see its docs." and a token field. No dead end, no fields to guess.
5. **Refresh and redirect.** The gateway refreshes sign-in tokens and writes the new ones back to
   Keychain. The redirect is a path on the Kitden page itself (the page's own address and port),
   so no extra listener; the builder checks this against the current spec.
6. **Same server in two clients.** "Same" means the same address and the same headers or env. The
   first selected entry is the one moved; every client's own entry is removed, each as its own
   tray row with its own Undo, as a single move does today. Entries that differ stay two servers.
7. **Keychain shape.** Sign-in tokens use the existing `<server>/<key>` scheme with fixed keys for
   the access token, the refresh token and the expiry.

## Left to the builder

- Exact copy within the patterns above.
- Hit testing for the marquee and how it scrolls with the map.
- How the token and sign-in checks are routed between the page and the server (one endpoint or
  two), within the existing API style.
- Tests: sandbox homes and the fake Keychain, plus a local fake MCP server for token and OAuth
  flows. Never a real account or a real token.

Docs to update with each part: docs/design.md (patterns, words, motion rows) and ROADMAP.md.
