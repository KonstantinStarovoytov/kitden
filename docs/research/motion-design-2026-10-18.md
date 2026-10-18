# Motion design review

Date: 2026-10-18. Status: proposal implemented for the owner to look at; not committed yet.
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

Reviewed 2026-10-18 from each project's GitHub page, API and raw files; nothing was installed.

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
