# Portal UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one long page with the approved four-place portal (Overview, Load map, Gateway, Changes, plus Agents) with its motion, keeping every existing action working.

**Architecture:** New read models live in Python under `src/agentsetup/views/` and are served as JSON (tested with pytest). The page becomes small ES modules under `src/agentsetup/web/static/js/` that only render those models with `textContent`. The mockup `docs/design/portal-mockup.html` is the visual reference for every pixel and motion value; copy its tokens and component CSS, not its test data.

**Tech Stack:** Python 3.14, Starlette, pytest; plain HTML, CSS and ES modules (no framework, no CDN, no new dependencies).

**Spec:** `docs/superpowers/specs/2026-10-17-portal-ui-design.md` (with the mockup next to it).

## Global Constraints

- CSP stays `script-src 'self'; style-src 'self'`: no inline `<script>`, no `<style>`, no `style=` or `on…=` attributes in HTML, no external URLs. JS may set `element.style` (CSSOM) and create SVG with `createElementNS`.
- Untrusted text only through `textContent`; never `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`.
- Words: states "Loads", "Off", "Via gateway", "Unknown", "Not installed"; scopes "everywhere", "this project", "this Mac", "plugin", "account", "Desktop app", "via Claude Code", "via Codex".
- Clients are columns in this order: `claude_code` (CC), `codex` (CX), `cursor` (CU). Neutral monograms, no brand logos. Desktop Code tab items show in the Claude Code column with scope "Desktop app".
- Tokens: copy `:root` and `[data-theme="dark"]` blocks from the mockup verbatim; 4 px grid, 13 px text, 34 px table rows, borders-only depth, one accent `--route`.
- Motion: `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`, `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`, `--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1)`; 180–320 ms; only transform, opacity, small SVG strokes; `prefers-reduced-motion` keeps fades only; skip View Transitions when `document.hidden`.
- Keyboard: `/` focuses search; Enter opens a row; Esc closes the side panel with no animation and returns focus to the row.
- URL hash keeps state: `#<view>?kind=<kind>&only=<filter>&project=<id>&q=<text>`.
- Theme: follows the system; the switch stores `light`/`dark` in `localStorage` inside try/catch.
- Checks after every task: `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run pytest -q`.

## Review Focus

- A client that is not installed: its column shows "Not installed" in every row, and the map still renders (test in Task 1).
- Same base name in different kinds (MCP `github` and plugin `github`) stays two rows; the same plugin from two marketplaces is one row with two copies (test in Task 1).
- Names with markup or 120+ characters (fixture skill `<img src=x onerror=…>`): returned raw by the API and shown as text, truncated with the full name in the panel (test in Task 1, guard in Task 5).
- Unknown or missing project id in any new endpoint returns 404 with a plain message, never a 500 (test in Task 4).
- A change that ends `stale` or `restored`: the review panel shows the reason, no Undo toast, counters do not move (browser check in Task 7).

---

### Task 1: Load map model

**Files:**
- Create: `src/agentsetup/views/load_map.py`
- Modify: `src/agentsetup/views/findings.py` (make `_base_name` and `_bypass_kind` public as `base_name`, `bypass_kind`)
- Test: `tests/unit/test_load_map.py`

**Interfaces:**
- Produces: `COLUMNS = ("claude_code", "codex", "cursor")`; `load_map(inventory, project: str | None) -> list[Row]`; `map_dict(inventory, rows) -> dict` returning `{"columns": [{"id", "name", "mark", "status"}], "rows": [{"key", "kind", "name", "cells": {client: {"state", "where", "items", "count"}}, "flags": [{"text", "level"}]}]}`.
- `Row.key` = `_hash(kind, base name)` from `agentsetup.model`.

- [ ] **Step 1: Write the failing tests** (fixture home `claude_code/2.1.283` + `codex/0.159.2` + `cursor/3.21.16`, Cursor state written)

```python
def test_rows_group_by_kind_and_base_name(home)            # plugin "superpowers" is one row; CX cell "none"
def test_cell_states_for_the_website_project(home)        # CC superpowers: state "off", where "this project"
def test_cursor_loading_a_plugin_twice_is_one_cell_with_count_2(home)  # cell["count"] == 2, flag {"text": "Cursor loads it twice", "level": "warning"}
def test_cross_loaded_cells_say_via_which_client(home)    # Cursor skill brandkit: where "via Claude Code"
def test_gateway_entries_are_state_gw(home)               # after mark_gateways: state "gw"
def test_desktop_items_show_in_the_claude_code_column(home)  # metamcp-local: CC cell where "Desktop app"
def test_not_installed_client_column_says_missing(home)   # build with only Claude fixture: CX and CU cells state "missing"
def test_mcp_and_plugin_with_the_same_name_stay_separate()
def test_raw_names_are_returned_unchanged(home)           # the "<img src=x onerror=…>" skill name arrives as-is
```

- [ ] **Step 2: Run them to see them fail** — `uv run pytest -q tests/unit/test_load_map.py` → errors (module missing).
- [ ] **Step 3: Implement `load_map` and `map_dict`.** For each column take `effective_view(inventory, client, project)` (Claude Code also adds the `DESKTOP` view's own items with where "Desktop app"). Cell rules, first match wins: client status not `found` → `missing`; loaded items with that kind and base name → `gw` if any `via_gateway`, `unk` if any `enabled is UNKNOWN`, else `on`, `count` = number loaded; else an item for that client, kind and base name applying to this project (project None or equal) → `off`; else `none`. `where`: scope word from Global Constraints, or "via Claude Code"/"via Codex" when `source.owner_client` is another client. Flags: from `find_findings` + `find_bypasses` for the project, mapped to rows by item id — duplicate → "<Client> loads it twice" (warning); bypass direct entry → "Around gateway" (warning when a gateway is registered, else info "Direct"); bypass local → "Local server" (info); bypass plugin → "From plugin" (info); unknown state → "State unknown" (info).
- [ ] **Step 4: Run the tests** — all pass; then the full checks.
- [ ] **Step 5: Commit** — `feat: load map model for the redesigned page`

### Task 2: Explain model shared by the page and the MCP server

**Files:**
- Create: `src/agentsetup/views/explain.py`
- Modify: `src/agentsetup/mcp_server.py` (use it; keep `explain_item` output keys)
- Test: `tests/unit/test_explain.py`; existing `tests/unit/test_mcp_server.py` stays green

**Interfaces:**
- Produces: `explain(inventory, name: str, kind: str | None, project: str | None) -> list[dict]`, each dict = the MCP `_brief` fields plus `"loads": bool`, `"why": str`, `"actions": list[str]`, `"change_hint": str | None`. `name` matches the item name, or the base name for plugins.

- [ ] **Step 1: Write the failing tests**

```python
def test_plugin_base_name_finds_all_marketplace_copies(home)   # "superpowers" → claude_code user, claude_code project, cursor x2
def test_why_says_which_definition_wins(home)                  # CC user definition in website: why contains "the project definition overrides it"
def test_actions_and_hints_are_included(home)                  # CC user superpowers actions == ["plugin.disable"]; Cursor copy change_hint mentions "Customize"
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Move `_brief` and `_why` from `mcp_server.py` into `explain.py`; `explain_item` calls `explain`.**
- [ ] **Step 4: Run `tests/unit/test_explain.py` and `tests/unit/test_mcp_server.py`** — pass.
- [ ] **Step 5: Commit** — `refactor: share item explanations between the page and the MCP server`

### Task 3: Overview and gateway models

**Files:**
- Create: `src/agentsetup/views/overview.py`, `src/agentsetup/views/gateway_view.py`
- Test: `tests/unit/test_overview.py`, `tests/unit/test_gateway_view.py`

**Interfaces:**
- Consumes: `load_map`, `base_name`, `bypass_kind` (Task 1).
- Produces: `overview(inventory, gateways, project: str | None) -> dict` = `{"headline": str, "attention": [{"id", "title", "text", "action", "target": {"view", "kind"?, "row"?}}], "notes": int, "clients": [{"id", "name", "version", "tested", "status"}], "gateway": {"name", "through", "total", "can_move", "stay_local", "from_plugins"} | None}`; `gateway_view(inventory, gateways, project) -> dict` = `{"gateways": [...], "connections": {client: [entry names]}, "groups": {"move": [...], "local": [...], "plugin": [...]}}`, each entry `{"item", "client", "name", "path", "actions"}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_headline_counts_attention(home)                    # "2 things need attention" for the fixture (Cursor superpowers twice, Codex docker-expert twice)
def test_duplicate_card_says_where_from(home)               # title "Cursor loads superpowers twice"; target {"view": "map", "kind": "plugin", "row": <key>}
def test_unreadable_file_becomes_an_attention_card(tmp_path)  # broken Cursor state DB → title starts "Could not read"
def test_untested_version_is_an_attention_card(home)        # version "2.0.0" for Claude Code → "Claude Code 2.0.0 is not tested"
def test_gateway_card_only_with_a_registered_gateway(home)  # no gateway → no gateway card, overview["gateway"] is None
def test_gateway_groups(home)                               # cursor "Neon" in "move" with "mcp.remove_direct"; codex "aseprite" not listed (off); cursor "n8n-mcp" in "local"
def test_connections_list_gateway_entries_per_client(home)  # after connecting: {"claude_code": ["gateway"], ...}
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** Attention order: unreadable files, untested versions, duplicates, then one gateway card "N MCP servers go around your gateway" (only with a gateway and N > 0; text "A can move in. B must run on this Mac. C come from plugins.", target `{"view": "gateway"}`). `notes` = info findings not shown as cards. Headline: "N things need attention", "1 thing needs attention", or "All clear".
- [ ] **Step 4: Run the tests** — pass; full checks.
- [ ] **Step 5: Commit** — `feat: overview and gateway models`

### Task 4: API endpoints for the new page

**Files:**
- Modify: `src/agentsetup/web/app.py`
- Test: `tests/unit/test_api_views.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `GET /api/map?project=<id>`, `GET /api/explain?kind=&name=&project=<id>`, `GET /api/overview?project=<id>`, `GET /api/gateway-view?project=<id>`. `project` is a project id from `/api/projects`; empty = everywhere. Response of `/api/map` also has `"project": {...} | null`.

- [ ] **Step 1: Write the failing tests**

```python
def test_map_everywhere_and_for_a_project(client)       # rows differ: "site-db" only with project=<work/site id>
def test_unknown_project_is_404(client)                 # each of the four endpoints, status 404, {"detail": "Unknown project."}
def test_explain_needs_a_name(client)                   # missing name → 422
def test_new_endpoints_need_the_session_cookie(tmp_path)  # without cookie → 401
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Add the four routes** with one helper `_project_path(request) -> str | None` that raises a 404 response for unknown ids; gateways come from `load_gateways(home)` (empty list without `home`).
- [ ] **Step 4: Run the tests** — pass; full checks.
- [ ] **Step 5: Commit** — `feat: API for the load map, explanations, overview and gateway`

### Task 5: Page shell, tokens, router and Overview

**Files:**
- Modify: `src/agentsetup/web/static/index.html`, `src/agentsetup/web/static/style.css`
- Delete: `src/agentsetup/web/static/app.js` (replaced)
- Create: `src/agentsetup/web/static/js/dom.js` (`$`, `el`, `shortPath`, `button`), `js/api.js` (`getJson`, `postJson`), `js/motion.js` (`animate`, `transition`, `rollTo`, `entrance`, `reducedMotion`), `js/parts.js` (`socket`, `mark`, `flag`), `js/app.js` (state, router, shell, theme, rescan, events), `js/overview.js`
- Test: `tests/security/test_static_files.py`; existing `tests/security/test_web_security.py` stays green

**Interfaces:**
- Produces: `state = { view, kind, only, project, q, selected }`; `go(view, params)`; `render()`; `load()` (fetches and caches `/api/clients`, `/api/projects`, overview, map); `rollTo(holder, value)`; `entrance(nodes)`; `transition(change, extraClass)`; `socket({state, where})`.

- [ ] **Step 1: Write the static guard tests**

```python
def test_no_html_injection_apis_in_scripts()       # no innerHTML/outerHTML/insertAdjacentHTML/document.write/eval(/new Function in static/js/*.js
def test_index_has_no_inline_code_or_styles()      # no "<style", " style=", "<script>" without src, no on…= attributes
def test_no_external_urls()                        # no "http://"/"https://" except "http://www.w3.org/2000/svg"
def test_every_module_import_exists()              # each `import … from "./x.js"` resolves to a file
def test_index_loads_the_app_as_a_module()         # <script type="module" src="/static/js/app.js">
```

- [ ] **Step 2: Run them to see them fail** (old `app.js` path, no modules yet).
- [ ] **Step 3: Build the shell** from the mockup: rail (Overview with roll counter, Load map, Gateway with "N around", Changes with roll counter; footer: scanned time + Rescan, "Agents can ask: show my setup", theme switch), top bar ("Where" `<select>` with Everywhere + projects, labelled; search with `/` hint), `<main id="main" class="page">`, side panel, scrim, toast container. Router reads and writes the hash format from Global Constraints; page changes use `transition()`. Theme switch uses the circle reveal from the mockup. Rescan button posts `/api/rescan`, shows the sweep line, then reloads data. SSE `rescan_finished` reloads data without closing the side panel. Overview renders the `/api/overview` model as in the mockup (attention cards with one action each; "Show N notes (nothing to fix)" expands an inline list of the info findings from `/api/findings`; Clients card; Gateway card with the filling bar, or "No gateway yet · Set up" linking to Gateway; Recent changes from `/api/changes`). Each place calls `entrance()` on its first visit only. While data loads, places show skeleton blocks shaped like the final content; a failed fetch shows an inline banner "Could not load <what>. Retry" with a Retry button.
- [ ] **Step 4: Run the full checks** — static guard and all tests pass.
- [ ] **Step 5: Browser check** on a fixture sandbox (`uv run agentsetup --no-browser --home <sandbox>`): Overview shows the attention cards, theme switch works and persists after reload, Where lists projects, console has no errors (CSP violations would show there).
- [ ] **Step 6: Commit** — `feat: new page shell and overview`

### Task 6: Load map

**Files:**
- Create: `src/agentsetup/web/static/js/map.js`
- Modify: `src/agentsetup/web/static/style.css`

**Interfaces:**
- Consumes: `/api/map`, `socket`, `entrance`, router state.
- Produces: `renderMap(main)`; `previousCells` snapshot `{rowKey: {client: "state|where"}}` used by Task 7 to morph changed cells; rows call `openItem(row)` from Task 7 (until then a click only selects the row).

- [ ] **Step 1: Implement** tabs per kind with counts and one gliding ink line; filters All / Needs attention (rows with a warning flag) / Differs between clients (cells with more than one distinct state, ignoring `missing`); search filters by name across all kinds and switches tab counts to match counts; table with fixed column widths 38/20.6/20.6/20.6 %, sticky header, truncated names (`title` attribute holds the full name), flags; legend (Loads, Off, Via gateway, Unknown, Not installed); empty states ("No hooks in any client", "Nothing matches “<q>”"). Rows are focusable; Enter or click opens the side panel.
- [ ] **Step 2: Browser check** on the sandbox: every kind tab, each filter, search `super`, a project in Where (the `work/website` project shows superpowers Off · this project), a 120-character name truncates, the `<img …>` skill name shows as text, keyboard `/` → type → Enter → Esc.
- [ ] **Step 3: Full checks, then commit** — `feat: load map page`

### Task 7: Side panel — details, review, Apply motion and undo

**Files:**
- Create: `src/agentsetup/web/static/js/panel.js`
- Modify: `src/agentsetup/web/static/js/map.js`, `js/app.js`, `style.css`

**Interfaces:**
- Consumes: `/api/explain`, `/api/commands?item=`, `POST /api/changes/preview`, `/apply`, `/cancel`, `/undo`; `previousCells` (Task 6); `rollTo`.
- Produces: `openItem(row)`, `openPanel(content, {instant})`, `closePanel({instant, keepSelection})`, `review(previewBody)` (used by Load map, Gateway, Agents), `toast(text, onUndo)`.

- [ ] **Step 1: Implement the detail panel** from the mockup: kicker (kind), title in mono, "Loads in …" line, warning callout when the row has a warning flag, one layer stack per client (definition, path shortened with `~`, badge "Loads", "Off" or the `why` text), secret note when any definition has `secret_present`, change hint text when no action exists. Footer: buttons from the definitions' `actions` ("Turn off in <Client>…", "Turn on in <Client>…", "Remove from <Client>…") that call `review()`, and "Commands…", which lists `/api/commands` results (command in `pre`, note as text). Panel slides in with the drawer curve and its sections rise 40 ms apart; focus moves in and returns to the row on close; Esc closes instantly.
- [ ] **Step 2: Implement the review panel** on the same surface: title in words from the action and target, masked diff with `+`/`-` lines coloured, client command line, "After you apply" checklist from `restart_note`/`login_note`, shared-file warning, footer Cancel/Apply. Apply morph: label blurs to "Applying…" with spinner, then the check draws and "Applied"; the panel leaves after 450 ms. On `verified`: toast "<what changed> · <restart note>" with Undo and the 6 s countdown that pauses on hover; reload data; cells whose `state|where` differ from `previousCells` morph (dot drains or fills, words blur across, one ping); nav counters roll. On `stale`, `restored` or an error: stay in the panel, show the reason in a callout, no toast. Undo from the toast calls `/undo` and morphs back.
- [ ] **Step 3: Browser check** on the sandbox: superpowers in Everywhere and in `work/website`; an MCP entry with a secret; a Cursor plugin shows the Customize hint and no toggle; Commands for a Claude plugin shows the Codex install lines; turn superpowers off in Claude Code → cell drains, attention count rolls, toast shows; Undo → back; edit the sandbox settings file between preview and Apply → "changed since preview" callout and no toast; emulated reduced motion → no movement, same results.
- [ ] **Step 4: Full checks, then commit** — `feat: side panel with details, review, apply motion and undo`

### Task 8: Gateway, Changes and Agents pages

**Files:**
- Create: `src/agentsetup/web/static/js/gateway.js`, `js/changes.js`, `js/agents.js`
- Modify: `style.css`

**Interfaces:**
- Consumes: `/api/gateway-view`, `/api/gateways` (GET, POST), `/api/changes`, `review()`, `toast()`.

- [ ] **Step 1: Implement Gateway** from the mockup: card with kind, URL, "Open <name> ↗" link (only `http(s)` URLs, `rel="noopener noreferrer"`, new tab); route diagram SVG (three clients to the hub; flowing dashes only for clients with a gateway entry, a plain grey wire otherwise; hub sub-label "<n> clients"); groups "Can move into the gateway" (Remove… opens review), "Must run on this Mac", "Come with a plugin"; "Add a gateway" form (MCP address, interface link, login None/key variable/OAuth, variable name) and "Connect" form (gateway, entry name, client checkboxes, Preview) as today. Empty state when no gateway: one sentence on why, then the Add form open.
- [ ] **Step 2: Implement Changes** (newest first, latest state per change, badge, Undo for `verified`, Details expands the logged steps) **and Agents** (one card per client: "Added" socket when an `agentsetup` MCP entry exists, else "Add…" → review of `setup_server.register`).
- [ ] **Step 3: Browser check:** register a gateway with key variable `GW_KEY` and connect it in the sandbox (flows appear, entries become Via gateway in the map); remove a direct entry; undo both from Changes; add show-my-setup for Codex.
- [ ] **Step 4: Full checks, then commit** — `feat: gateway, changes and agents pages`

### Task 9: Finish and verify

**Files:**
- Modify: `README.md` (table of page places matches the new names), `specs/001-agent-setup-inventory/validation.md` (UI results), `docs/superpowers/specs/2026-10-17-portal-ui-design.md` (legend: Overridden only in the panel; Not installed added)

- [ ] **Step 1: Run** `uv run pytest -q`, `uv run pytest -q -m contract`, ruff check and format check — all green.
- [ ] **Step 2: Browser walkthrough** on the sandbox at 1280×800 and 390×844, light and dark: every place, every state from the Review Focus list, no console errors, no sideways scroll at 1280, text and status colours readable in both themes (spot-check contrast of muted text, flags and sockets).
- [ ] **Step 3: Owner check on the real page** (read-only): restart `uv run agentsetup`, open each place.
- [ ] **Step 4: Commit** — `docs: page redesign results`
