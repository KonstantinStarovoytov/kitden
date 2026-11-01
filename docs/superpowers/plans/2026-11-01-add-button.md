# Add Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the small "+ Add" beside the map captions with a soft-accent header button and a
grey dashed "Add a server" card at the end of the map's server groups (and the same on Library).

**Architecture:** One shared header button made in `map-page.js` beside Map / List, keeping today's
focus key (`add:servers`, `add:plugins`), so `add-panel.js` still finds it, shows it pressed and
gives focus back to it. One new map block kind, `addslot`, drawn by `map-view.js` like any block;
pressing it opens the same panel. The caption button and `onAdd` go away.

**Tech Stack:** vanilla JS modules, CSS, `node --test` with the fake DOM in `tests/frontend`.

**Spec:** `docs/superpowers/specs/2026-11-01-add-select-sign-in-design.md`, Part 1.

## Global Constraints

- Header button: "+ Add servers" (Gateway), "+ Add plugins" (Library); class `btn add`; 28 px tall,
  the same as Map / List; placed left of Map / List.
- Pressed while the panel is open: `aria-expanded="true"` and `--route-soft` fill. Not the filled
  `.primary` look (the owner rejected a loud button).
- Slot card words: name "Add a server" / "Add a plugin", meta "From the catalog". Grey dashed edge
  `--wire-strong`, no fill. Accent edge on hover and while the gateway is lit by a drag.
- Dashed accent stays reserved for preview. The new card must not use `--preview-line`.
- Motion: only today's tokens (button press; color fade `--t-fast`; the card enters with the map).
- UI text in simple English; update `docs/design.md` and `ROADMAP.md` in the same change.
- Before commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.

## Review Focus

1. **First run (no gateway yet) and a gateway Kitden cannot read:** no slot card, since there is
   nowhere to add yet. The header button still shows and opens the panel.
2. **List view:** the header button shows and works; the slot card is map-only.
3. **Focus back:** closing the panel returns focus to the header button, also when the panel was
   opened from the slot card.
4. **Narrow map:** the slot card hides its words like other blocks, keeps its "+" tile, and still
   opens the panel.
5. **Search on the page (`state.q`):** the slot card is never a match and is dimmed with the rest.

---

### Task 1: Header button on both map pages

**Files:**
- Modify: `src/kitden/web/static/js/map-page.js` (new export)
- Modify: `src/kitden/web/static/js/gateway.js:131-132` (head), `:1204-1209` (`pressAdd`)
- Modify: `src/kitden/web/static/js/library.js:328-329` (head)
- Modify: `src/kitden/web/static/js/add-panel.js:37-42` (`showPressed`)
- Modify: `src/kitden/web/static/style.css` (near `.btn.add`, line ~505)
- Test: `tests/frontend/map-page.test.mjs` (create if missing, else add), `tests/frontend/gateway-add.test.mjs`

**Interfaces:**
- Produces: `addHeadButton(label: string, key: string, onPress: (node) => void): HTMLButtonElement`
  in `map-page.js`. Returns `button(label, …, "btn add")` with `dataset.focus = key` and
  `aria-expanded="false"`.

- [ ] **Step 1: Write the failing tests**

```js
test('the header add button is a soft-accent button with its focus key', () => {
  const pressed = [];
  const add = addHeadButton('+ Add servers', 'add:servers', (node) => pressed.push(node));
  assert.deepEqual([add.textContent, add.className, add.dataset.focus, add.getAttribute('aria-expanded')],
    ['+ Add servers', 'btn add', 'add:servers', 'false']);
  for (const fn of add.listeners.click) fn({});
  assert.deepEqual(pressed, [add]);
});
```

In `gateway-add.test.mjs`, change the `addButton()` helper to make `className = 'btn add'`, and
add:

```js
test('the header add button looks pressed while the panel is open, never filled', async () => {
  const from = await open();
  assert.equal(from.getAttribute('aria-expanded'), 'true');
  assert.equal(from.classList.contains('primary'), false);
  await done();
  assert.equal(from.getAttribute('aria-expanded'), 'false');
});
```

- [ ] **Step 2: Run to see them fail**

Run: `node --test tests/frontend/map-page.test.mjs tests/frontend/gateway-add.test.mjs`
Expected: FAIL (`addHeadButton` not exported; `primary` still toggled).

- [ ] **Step 3: Implement**

- `addHeadButton` in `map-page.js`.
- `showPressed` sets only `aria-expanded`.
- Gateway: `head.append(addHeadButton("+ Add servers", "add:servers", (node) => openAdd({ from: node })), seg)`.
  Show it whenever the page has a gateway (map and list).
- Library: the same with "+ Add plugins", `"add:plugins"`, calling the hook `library-add.js` sets
  (today's `addHook`).
- CSS:
  - `.page-head .btn.add { height: 28px; }`
  - `.btn.add[aria-expanded="true"] { background: var(--route-soft); }`
  - The page head keeps the button and Map / List together on the right, 8 px apart.

- [ ] **Step 4: Run to see them pass**

Run: `node --test tests/frontend/*.test.mjs`
Expected: all pass. Fix any test that pressed `add:servers` / `add:plugins` on the caption: the
key is the same, now on the header.

- [ ] **Step 5: Commit** — "Put the add button in the page header"

### Task 2: "Add a server" card at the end of the server groups

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (where `addGateway` runs for the Kitden gateway, not
  the first-run branch; `pressBlock` at ~1215)
- Modify: `src/kitden/web/static/js/map-view.js` (`fill`: draw kind `addslot`)
- Modify: `src/kitden/web/static/js/gateway-drag.js:206, 381` (glance sets)
- Modify: `src/kitden/web/static/style.css` (`div.map .block.addslot`)
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/map-view.test.mjs`

**Interfaces:**
- Produces: a block `{ id: "addslot:servers", column: "servers", kind: "addslot", name: "Add a server", meta: "From the catalog", icon: "plus", h: 50 }`.
  It is pushed after the Kitden gateway's groups and before the Outside group.
- Consumes: `openAdd({ from })` from `gateway-add.js`; the header button found by its
  `data-focus="add:servers"`.

- [ ] **Step 1: Write the failing tests**

```js
test('the map ends the gateway groups with an "Add a server" card', () => {
  const model = treeFor(VIEW_WITH_SERVERS, 'map');
  const ids = model.blocks.filter((b) => b.column === 'servers').map((b) => b.id);
  const card = model.blocks.find((b) => b.id === 'addslot:servers');
  assert.deepEqual([card.kind, card.name, card.meta], ['addslot', 'Add a server', 'From the catalog']);
  assert.ok(ids.indexOf('addslot:servers') < ids.indexOf('group:outside'));
});
test('no "Add a server" card before the gateway is set up', () => {
  assert.equal(treeFor(FIRST_RUN_VIEW, 'map').blocks.some((b) => b.kind === 'addslot'), false);
});
test('pressing the card opens the add panel with focus going back to the header button', async () => { /* press 'addslot:servers'; expect openAdd called with from = node(box,'add:servers') */ });
test('a drag that lights the gateway lights the card too', () => { /* glance set includes 'addslot:servers' */ });
```

In `map-view.test.mjs`: an `addslot` block gets class `block addslot`, its "+" tile and both
lines, no lamp, no ports.

- [ ] **Step 2: Run to see them fail**

Run: `node --test tests/frontend/gateway.test.mjs tests/frontend/map-view.test.mjs`
Expected: FAIL.

- [ ] **Step 3: Implement**

- Push the block as above, only when the Kitden gateway is read and not first run.
- `pressBlock`: `addslot` → `openAdd({ from: headerButton })`. If the header button is missing,
  use `from: null`.
- `findIn`: skip kind `addslot`.
- Add `"addslot:servers"` to the two glance sets in gateway-drag.js when the card exists.
- CSS:
  - `div.map .block.addslot { border: 1px dashed var(--wire-strong); background: transparent; }`
  - `div.map .block.addslot:hover, div.map .block.addslot.lit { border-color: var(--route); }`
  - The color moves over `--t-fast`.
  - The "+" tile is `--raised` with `--accent-text` "+".

- [ ] **Step 4: Run to see them pass**

Run: `node --test tests/frontend/*.test.mjs`. Expected: all pass.

- [ ] **Step 5: Commit** — "Add a server card at the end of the gateway groups"

### Task 3: Same card on Library; caption "+ Add" removed; docs

**Files:**
- Modify: `src/kitden/web/static/js/library-map.js:27` (`add: true` goes), plugins column builder
  (push `{ id: "addslot:plugins", column: "plugins", kind: "addslot", name: "Add a plugin", meta: "From the catalog", icon: "plus", h: 50 }` last), `pressBlock`
- Modify: `src/kitden/web/static/js/gateway.js:221` (`add: true` goes)
- Modify: `src/kitden/web/static/js/map-view.js:269-275, 345, 515-530` (remove `addButton`, `onAdd`, caption add)
- Modify: `docs/design.md` (Gateway and Library add rows, Controls), `ROADMAP.md`
- Test: `tests/frontend/map-view.test.mjs:276` (delete the caption test), `tests/frontend/library-add.test.mjs:206-215`

- [ ] **Step 1: Write the failing tests**

- Library model ends the plugins column with `addslot:plugins`.
- Pressing it opens the Library panel, with focus going back to the `add:plugins` header button.
- A caption never holds a button.

- [ ] **Step 2: Run to see them fail**

Run: `node --test tests/frontend/library-add.test.mjs tests/frontend/map-view.test.mjs`
Expected: FAIL.

- [ ] **Step 3: Implement, then update docs**

- `docs/design.md`: "+ Add" beside the caption becomes "+ Add servers" / "+ Add plugins" in the
  header, plus the "Add a …" card. Add one Controls line for the header add button.
- `ROADMAP.md`: mark Part 1 done.

- [ ] **Step 4: Full checks**

Run: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
Expected: all pass.

- [ ] **Step 5: Look at it**

Check the sandbox at http://127.0.0.1:47977, in light and dark themes, on the Gateway map, the
Gateway list, the Library map, a narrow window and the first run. Then commit — "Same add card on
Library; drop the caption button".
