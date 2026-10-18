# Motion design review

Date: 2026-10-18. Status: first pass committed (0d654b0); second pass below. Rules now live in
[docs/MOTION_DESIGN.md](../MOTION_DESIGN.md).
Input: the owner's design research note ("Kitden: a living developer control center") and its
agent prompt. Rules that stay: [DESIGN.md → Motion](../../DESIGN.md#motion).

## What the page is built with

Plain ES modules and one CSS file, served by the local Python server, with a strict
Content-Security-Policy (no CDN, no inline code). There is no React, SwiftUI, Tauri or Electron,
so React libraries (Motion, Motion Primitives, React Bits) do not apply. Motion uses CSS
transitions and keyframes, CSS `linear()` springs, the Web Animations API and View Transitions.
Nothing new is loaded at run time.

## Audit: what was there before this change

| Recommendation | Before | Gap |
| --- | --- | --- |
| Apply: Ready → Applying → Applied | Done: spinner, then a drawn check only after the server reports `verified` | None |
| Undo | Done: toast with a 6 s countdown, the Load map cells morph back | None |
| Issue count 3 → 2 | Done: numbers roll in the rail | None |
| Configuration diff | Plain coloured text, hidden behind "Show file change" | No line tint, no entry, panel could overflow on a long path |
| Client cards | Static list | No hover, no way to see what a client loads |
| Plugin toggle | Only "Turn off in …" buttons | No switch showing the state |
| Error feedback | Error callout | No feedback on the button that failed |
| Duplicates and issue navigation | Finding opens the Load map row and its panel | The eye has nothing to land on |
| Gateway routing | Dashes run along every wire forever | Suggests traffic Kitden cannot see; no hover; no sign of servers going around the gateway |
| Scope switching | The table redraws | Cells jump |

## What was built

| Priority | Interaction | How it behaves | Safety |
| --- | --- | --- | --- |
| P0 | Client cards (Overview) | Hover lifts the icon; click or Enter opens a row with "2 MCP servers · 1 plugin · 2 skills"; each count goes to that Load map tab | Counts come from the Load map data |
| P0 | Plugin switch (item panel) | Shows the real on/off state; press stretches the thumb and opens the review | Never flips before Apply; the Load map shows the new state after the write |
| P0 | Configuration diff | Removed lines red with a left bar, added lines green; lines settle in one after another (18 ms apart) | The text is the server's diff, unchanged |
| P0 | Apply / error | Unchanged success path; a failed Apply shakes the button once (10 px, 360 ms) and keeps the error callout | Success only after `verified` |
| P0 | Undo | Unchanged: cells morph back, toast says what happened | Toast text comes from the server state |
| P1 | Issue navigation and duplicates | Arriving from a finding: the row glows once and the sockets of the clients that load it ping | Light only; no layout moves |
| P1 | Gateway topology | Wires draw once when a connection first appears, then stay still. Hover a client: its route lights, the rest dim. Hover a server row: the clients that load it light. Each client shows "N direct" for servers that go around the gateway | Removed the endless dashes (fake traffic) |
| P1 | Scope switching | Changing the project on the Load map morphs each cell to its state in the new scope | Same morph as after Apply |
| — | Buttons and switches | 80 ms press to 0.98, release on a critically damped `linear()` spring; no overshoot | — |

## Not done, and why

| Idea | Decision |
| --- | --- |
| Per-client accent colours | The vendor icons already carry each client's identity; extra accents would fight the single terracotta accent in DESIGN.md |
| MCP introspection highlight (P2) | Needs the read-only server to tell the page which query ran; a separate feature |
| Client card → elements transform between clients | The page has no per-client view to transform between |
| React libraries, GSAP | Not needed: CSS and the Web Animations API cover every interaction above with no new dependency |

## Recommended tools and skills

Reviewed 2026-10-18 from each project's GitHub page, API and raw files. The owner approved the
LottieFiles skill; it is in `~/.claude/skills/motion-design/` (17 Markdown files and the MIT
license, no scripts). Nothing else was installed.

| Item | What it is | Fits Kitden | Decision |
| --- | --- | --- | --- |
| [LottieFiles motion-design](https://github.com/LottieFiles/motion-design-skill) | Skill text only, 20 files, about 56 KB, MIT | Yes: engine-free timing, easing and pattern tables | **Install** (copy the folder; no scripts) |
| [Impeccable](https://github.com/pbakaus/impeccable) | Skill + detector, 57 files, about 2.2 MB, Apache-2.0 | Partly: `animate.md` fits | Do not install: its launcher downloads a binary and its CLI adds an edit hook to `.claude/settings.local.json`. Link `animate.md` instead |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Skill + data, runs Python, about 3.6 MB, MIT | Partly: a few UX rows | Do not install; rules used below |
| [Motion AI Kit](https://github.com/motiondivision/ai-kit) | Skill + hosted MCP servers, parts paid, no license file | Partly | Do not install |
| [GSAP skills](https://github.com/greensock/gsap-skills) | Skills that write GSAP code, MIT | No: needs the `gsap` library | Do not install |
| [React Bits](https://github.com/DavidHDev/react-bits), [Motion Primitives](https://github.com/ibelick/motion-primitives) | React component libraries | No: need React | Do not use |

Rules taken from them and applied here:

- No overshoot in a serious tool; a calm press is about 0.98; a toggle thumb slides with
  ease-in-out ([LottieFiles state feedback](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/patterns/state-feedback.md)).
- Error: a horizontal shake of 10–15 px over 300–400 ms (same file).
- Stagger only lists, keep the total under 500 ms ([multi-element](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/patterns/multi-element.md); [Impeccable animate](https://github.com/pbakaus/impeccable/blob/main/skill/reference/animate.md)).
  Diff: 18 ms × 14 lines at most = 252 ms.
- Endless motion on decoration is an anti-pattern ([UI UX Pro Max guidelines](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/src/ui-ux-pro-max/data/ux-guidelines.csv), row 12) — the gateway dashes went.
- Animate transform and opacity only; never rely on `transitionend` for the true state.
- Ignored on purpose: the LottieFiles checklist asks for an "ambient layer"; that would be the
  fake activity Kitden rules out.

## Validation

- 418 tests pass; Ruff passes; the two Node lifecycle tests pass.
- New tests: gateway wires never loop; the plugin switch never sets its own checked state.
- Browser, fixture home (no real settings touched): Overview client open/close, plugin switch →
  review → Apply → Load map shows Off → Undo → "previous settings are back"; finding →
  Load map row glow and pings; Gateway draw, route hover and row hover (checked by computed
  opacity); light and dark; 375 px phone layout.
- Fixed on the way: a long file path made the review panel wider than the screen.
- Reduced motion: the existing rule turns every animation off; the wire's resting style is fully
  drawn, the diff lines' resting style is visible, so nothing depends on an animation finishing.
- Performance: only `transform` and `opacity` animate, except the client counts row
  (`grid-template-rows`, one small row at a time).

## Second pass (2026-10-18)

Built on the owner's design brief, one commit per feature.

| Feature | What changed |
| --- | --- |
| 1 Tactile controls | Tabs, filters and rail links press like buttons; fields and the project picker answer hover; the plugin switch shows a pending thumb (half-way) while the preview loads, so it is never on, off or flipped before the review opens |
| 2 Client cards | The client's tile flies from its Overview row to its Load map column (View Transitions, `fly`/`land`); an open row keeps its tint |
| 3 Diff | "Show file change · +2 −1" counts the lines before the diff is opened; the file change folds open and closed instead of popping |
| 4 Apply / Undo | Applied turns the button green with the drawn check; verified and undone toasts carry a check, errors never; places other than the Load map cross-fade to the new state |
| 5 Navigation | One mark slides between the rail links, the Load map tabs and the filters (`glide`); gateway forms fold |
| 6 Topology | Hovering or focusing a client lights its route and the rows below with its direct entries; routes take keyboard focus and say their state; a click leads to the first such row |
| 7 Cleanup | A flag that a verified change resolved shrinks away; one flag per wording (three clients with the same note made three flags) |
| 9 Scopes | With a project open the picker wears the selection tint; the Load map lede rises in while the cells morph |

Fixed on the way: a row with several flags lost its name (the name now keeps 9 characters);
gateway rows on a phone lost their name (the buttons move under it).

Checked in the browser on a sandbox home with 39 MCP servers, 6 plugins, 3 findings and a
registered gateway: light and dark, 375 px, Apply → Undo from the toast and from Changes, the
flight (names set and cleared), route focus (14 rows lit, others at 0.35), no long task over
50 ms. Reduced motion: checked by reading the code paths, not by emulation.

Left for later (P1/P2): per-finding focus from the Overview notes list; MCP introspection
highlight; a client-level topology for projects.

## Review with the motion-design skill (2026-10-19)

Checked the branch against the installed LottieFiles skill: its archetype table, duration table,
quality checklist and troubleshooting list.

| Check | Result |
| --- | --- |
| One archetype, applied everywhere | **Corporate** (200–400 ms, 0–3% overshoot, `(0.2,0,0,1)`-class easing). Every duration on the page sits in 80–380 ms; the only longer ones are the 900 ms scan sweep and the 1.2 s skeleton shimmer, both loops on real waiting |
| Signature easing for 80% of motion | `--spring` (critically damped `linear()`) for everything the hand moves; `--ease-out` for entrances; `--ease-drawer` for the drawer and the flying tile |
| Duration palette of three | Press 80/260 ms, fast 180 ms, panel 320 ms (plus fold 280, flight 340) |
| Entrance longer than exit | Drawer 320 ms both ways; diff lines enter 260 ms, no exit. Acceptable: the drawer is a heavy element, the skill allows equal timing there |
| Never linear for spatial movement | Only the spinner and the shimmer are linear; both are loops, as the skill allows |
| Never opacity-only for a state change | Applied: colour + check draw; resolved flag: scale + opacity; socket morph: dot fill + word blur; switch: thumb position + track colour |
| 1/3 of elements at once; stagger under 500 ms | Entrance 45 ms × at most 6 blocks = 270 ms; diff 18 ms × 14 = 252 ms |
| Error: 10–15 px shake, 300–400 ms, no overshoot | 10 px, 360 ms, `--ease-out` |
| Three motion layers (primary, secondary, ambient) | **Not followed on purpose.** The ambient layer would be fake activity in a tool that edits files; see DESIGN.md → Motion |
| Reduced motion keeps feedback | All animation off; every resting style is the true state; the error callout and the Applied colour stay |

Fixed during the review:

- Plugins whose on/off the page cannot change (Cursor plugins; Codex remote plugins kept in the
  ChatGPT account) now show the same switch as the others, locked and with the reason in its
  tooltip. Before, they showed a badge and the switch looked inconsistent from plugin to plugin.
- Client tiles in the Load map header are 20 px (the header text is 12 px); 24 px looked heavy
  next to it. Lists, chips and panel titles keep 24 / 28 px.

Left as is: the Codex remote plugins are named `app-<id>@openai-curated-remote` because Codex
stores no readable name locally (`codex plugin list --json` repeats the id in `name`).

