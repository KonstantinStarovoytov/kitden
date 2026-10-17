# Design skills and tools for the agentsetup page

Reviewed on 2026-10-17. Stars and dates come from the GitHub API on that day. **Fact** = checked in
the repository or its README. **Proposal** = our recommendation; nothing here is decided yet.

What we design: a local, dense developer page. It has tables of MCP servers, skills and plugins
for three clients, findings, diff previews, Apply and Undo. It is not a marketing page. It runs
with a strict Content-Security-Policy: no CDN, no inline scripts or styles, no frontend framework.

## Skills (rules and taste for the agent)

| Skill | Stars | What it is (fact) | Fit for our page (proposal) |
| --- | --- | --- | --- |
| [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines) (Vercel) | 1,000 (skill repo 32,559) | About 190 short rules: keyboard and focus, empty, dense and error states, `tabular-nums`, dark mode, confirm or undo for destructive actions, filters in the URL | High. Works in all three agents |
| [interface-design](https://github.com/Dammyjay93/interface-design) | 5,815 | "For interface design — dashboards, apps, tools, admin panels. Not for marketing sites." Density, tokens, native controls; saves decisions to a system file; design review command | High. The only popular skill scoped to tools |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | 46,968 | Mostly motion. `break-ui` feeds worst-case data (long names, zero items, huge counts) | High for `break-ui`, low for the rest |
| [Impeccable](https://github.com/pbakaus/impeccable) | 82,309 | One skill, 24 commands, 59 detectors; "Operate" mode for product screens; `harden`, `onboard`, `audit`, `quieter`, `distill` | Medium. Strong content, but see risks |
| [frontend-design](https://github.com/anthropics/skills) (Anthropic) | 181,753 (repo) | One page: plan tokens, avoid common AI defaults, guidance for error and empty copy | Medium. Aims for a distinctive look |
| [taste-skill](https://github.com/Leonxlnx/taste-skill) ("Tasty") | 98,390 | Art direction from 247 gallery sites. Its FAQ: the default skill is not for dashboards; use the minimalist or soft variant for product UI | Low for the default; the minimalist variant only as a visual reference |
| [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 136,830 | Search over catalogues of styles, palettes and UX rules | Low. Trend catalogue |

Already installed on this computer (fact): the whole taste-skill set in `~/.claude/skills`, and
`impeccable`, `emil-design-eng`, `apple-design`, `prototype` and motion skills in
`~/.codex/skills`.

## Tools (seeing and checking the page)

| Tool | Stars | Account or network (fact) | Fit (proposal) |
| --- | --- | --- | --- |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) (Google) | 53,721 | No account. Usage statistics on by default (`--no-usage-statistics`); performance tools may send URLs to CrUX (`--no-performance-crux`) | High, with both flags. Shows CSP errors in the console |
| [agent-browser](https://github.com/vercel-labs/agent-browser) (Vercel Labs) | 44,140 | No account. Embedded axe-core "works offline and under strict CSP"; screenshot diff against a baseline | High as an automatic check |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) (Microsoft) | 14,304 | Local, no account | High; the no-telemetry option |
| [axe-core](https://github.com/dequelabs/axe-core) (Deque) | 7,658 | Offline | High for accessibility checks |
| [DESIGN.md](https://github.com/google-labs-code/design.md) (Google) | 28,401 | Offline spec plus `lint` (tokens, contrast) | Medium. A place to write our design rules down |
| Built-in browser of this Claude session | — | Already available | High for the first design pass: screenshots and page checks with no install |
| v0, 21st MCP, shadcn MCP, Google Stitch, Figma MCP | — | Accounts, cloud generation, or React and Tailwind output | Avoid: privacy and stack mismatch |

## Risks (fact)

- **Impeccable** installs hooks into Claude Code, Codex and Cursor; downloads a binary to
  `~/.impeccable`; calls a "roll" API at impeccable.style; telemetry is on unless
  `IMPECCABLE_NO_TELEMETRY=1`.
- **Vercel's installer** is `curl … | bash`, and its skill fetches the rules from GitHub on every
  run. A pinned copy avoids both.
- **taste-skill v2** runs Node scripts, starts Chrome and downloads images from public archives.
  Its `minimalist-ui` and `redesign-existing-projects` skills may trigger on "polish this page" and
  push a landing-page look onto the tool.
- Same-name copies of popular skills exist in other repositories. Install only from the original.
- Any screenshot loop sends images to the model provider. Run design reviews on the fixture
  sandbox, never on the owner's real setup.

## Proposed way of working

1. Write our design rules in one file in the repository (DESIGN.md style), based on a pinned copy
   of the Vercel guidelines and the `interface-design` method.
2. Design with mockups in the built-in browser on fixture data, guided by those rules.
3. Stress-test tables with Emil Kowalski's `break-ui` ideas (long names, empty lists, many items).
4. Check every screen automatically: axe-core accessibility, a screenshot diff, and no CSP errors.
5. Keep taste-skill and Impeccable as reading material unless the owner decides to install them
   after reviewing their hooks, scripts and telemetry.
