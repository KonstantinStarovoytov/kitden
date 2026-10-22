# Part 6: The setup map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "List | Map" switch on the Overview shows the setup as sources, item groups and
clients in three fixed columns; selecting a client, a source or an item shows how they connect,
with typed, labelled lines and Details beside the map.

**Architecture:** One read model, `views/setup_map.py:setup_map()`, groups every definition into
a source group and reuses `load_map()` rows (item identity and cell states),
`effective_view().shadowed` (overrides) and `find_findings()` (real duplicates);
`GET /api/setup-map` serves it like the other read models, from the inventory in memory. One page
module, `map.js`, is loaded with `import()` only when Map is shown: pure layout functions tested
with node, and `renderMap()` that draws HTML buttons plus one SVG overlay for the selected item's
lines. Selection is Part 2's `sel`; Details is Part 3's panel, opened beside the map.

**Tech Stack:** Python 3.13, Starlette; plain ES modules and one CSS file; pytest on sandbox
homes and the demo samples; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 6 (6.1–6.5), with
Constraints, Anti-goals and Acceptance; concept §5, §10, §12. Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (its Rules and "Names that cross part
boundaries" bind this plan). Branch `visual-part6-map`, from `main` after Part 5 is merged.

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments, UI and docs; tests on sandbox homes
  (`make_home`, `build_demo_home`); short plain commit subjects ending with the session's
  co-author line; files staged by name.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`,
  `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Read only. The map changes nothing; every action stays in Details and goes through
  preview → Apply with a backup → verify → Undo. "No command runs, no server starts" (spec 6.3);
  no network.
- Main pages: names, counts, client tiles, short flags. No path, command or address on the map:
  they stay in Details' technical part.
- "The map's code loads only when first shown (dynamic `import()`), so the start does not slow
  down." No script imports `map.js` statically.
- Anti-goals (spec): "Moving lines or pulses while idle; a map that rearranges itself; a map that
  is required to do a task (the table route must always work)." "A state shown as fact when
  Kitden does not know it: Unknown shown as Missing, a name match shown as the same item." No graph
  editor: "no drag to install, no drag to connect, no free node placement".
- Spec numbers: endpoint "under 150 ms on the `large` sample"; "a group with more than 30 items
  shows the first 30 and 'Show all'"; "Under 900 px wide the map becomes a stacked list
  (source → items → clients) with the same selection"; "a selected line draws once; nothing moves
  while idle; reduced motion shows it at once"; local storage key `kitden.overview` = `"list"` |
  `"map"` (master).
- `docs/design.md`: tokens only, both themes, `:focus-visible`, targets of at least 24 px,
  transform and opacity only. A task that changes the page updates design.md and pins new words in
  `tests/unit/test_page_words.py` in the same commit (master rule).
- `ROADMAP.md`: while `git status` shows the owner's uncommitted edit, no task edits or stages it
  (Task 6 puts the lines in the report).

## Review Focus

1. **A skill folder two clients read** (`~/.agents/skills` by Codex and Cursor): one source, one
   item, a line to each client, no "Loads twice"; a real duplicate (`docker-expert` also in
   `~/.codex/skills`) is marked only because the findings say so. Task 1:
   `test_a_shared_folder_is_one_source_with_a_line_to_each_client`,
   `test_loads_twice_only_where_the_findings_say_so`.
2. **A state Kitden does not know** (a client it could not read, a file that failed, an on/off it
   cannot read): the map says "Could not read" or "may be available to", never a silent gap or a
   plain "available to". Task 1: `test_an_unknown_on_off_state_is_only_maybe_available`,
   `test_a_client_that_could_not_be_read_keeps_its_node`,
   `test_a_file_that_could_not_be_read_marks_its_source`.
3. **The `large` sample:** the closed first view fits one window, a group over 30 shows 30 and
   "Show all N", a selected item past the first 30 still shows with its sources, long names end
   with "…", the endpoint stays under 150 ms. Task 3: `a large setup folds sources after twelve…`,
   `a selected item past the first 30 still shows…`, `long names end with …`; Task 2: the script.
4. **A redraw** (rescan, resize, Details opening, narrow ↔ wide, project change): the same
   selection stays, a line already drawn does not draw again, another project's map never shows.
   Task 3: `lines draw only when the selection is new`, `the narrow list opens the selected
   item's source`; Task 4: `a project change never shows another project's map`.
5. **A plugin whose own entry sits in the plugin cache** (Codex `gmail@openai-curated-remote`,
   `plugin_of()` names it): the plugin is an item of "Codex all projects", not content of itself;
   its contents are in "Plugin gmail". Task 1: `test_a_plugin_is_not_inside_its_own_plugin_group`.

## Names this part uses

| Consumes | From | Use here |
| --- | --- | --- |
| `kitden.demo.build_demo_home(root, size)`, `demo_build(home)` | Part 1 | `medium` page test, `large` timing |
| `create_app(..., demo=True)`; `measure_demo` in `scripts/measure-start.py` | Part 1 | timing and page test; the map number follows the demo line |
| `cutName(name, max = 24)` (`gateway.js`) | Part 5 | moved to `dom.js` and used for map labels |
| `Cell.state` `"review"`, `Item.stale_at`; JS `STATE_WORDS.review` ("Needs review") and `STATE_WORDS.unread` ("Could not read") in `parts.js` | Part 2 | item and node flags; source "Last read" flag |
| `state.selected: {kind, name} \| null`, hash `sel=`, `parseSel`, `selFor`, `setState` writing `sel`, `goTo(view, selected)`, `arrival` / `takeArrival()` (all `store.js`); `rowSel(row)` (`library.js`); `closePanel` clears the selection through `setState` | Part 2 | item selection; opening Details once on arrival; "Show on the map" |
| `openItem(row, options)` in `details.js` (re-exported by `panel.js`), `openPanel` / `closePanel` in `panel.js`; `contextLinks(row, definitions, view)` in `details.js`, whose links close the panel and call `goTo(link.view, link.selected)` | Part 3 | Details beside the map; the "Show on the map" link |

| Produces | Used by |
| --- | --- |
| `GET /api/setup-map?project=<id>` → `{project, sources, groups, items, clients, relations}` | 8 (tour) |
| `map.js`: `layoutMap(model, open)`, `renderMap(container, model)` | 8 |
| `store.js`: `OVERVIEW_KEY = "kitden.overview"`, `overviewMode()`, `setOverviewMode(mode)`, `loadSetupMap()` | 8 (the tour's map stop switches to Map) |

## Files

- Create `src/kitden/views/setup_map.py` (read model), `src/kitden/web/static/js/map.js`
  (layout and drawing), tests `tests/unit/test_setup_map.py`, `tests/unit/test_setup_map_api.py`,
  `tests/frontend/map.test.mjs`, `docs/research/walkthrough-script-2.md`.
- Modify `src/kitden/web/app.py` (route), `scripts/measure-start.py` (the map number),
  `store.js` (overview choice, map data), `overview.js` (switch, lazy load), `parts.js`
  (`LOAD_KINDS`), `dom.js` (`cutName`, `svgEl`), `gateway.js` (uses both), `panel.js` (beside,
  closed event), `details.js` (Part 3's module: `beside`, "Show on the map"), `app.js` (search on
  the map), `style.css`, `docs/design.md`, `docs/development.md`, `README.md`.

---

### Task 1: The setup map read model (6.3)

**Files:**
- Create: `src/kitden/views/setup_map.py`
- Test: `tests/unit/test_setup_map.py`

**Interfaces:**
- Consumes: `load_map(inventory, project) -> list[Row]`, `row_key(item)`, `COLUMNS`, `NAMES`
  (`views/load_map.py`; `Cell.state` may be `"review"` after Part 2); `effective_view(...)`,
  `plugin_of(item)`, `DESKTOP` (`views/effective.py`); `find_findings(inventory, project)`;
  `KITDEN_GATEWAY` (`changes/actions.py`); `Item.stale_at` (Part 2).
- Produces:
  - `MAP_KINDS = (ItemKind.MCP_SERVER, ItemKind.PLUGIN, ItemKind.SKILL, ItemKind.HOOK, ItemKind.INSTRUCTIONS)`
  - `source_group(item: Item, shared_paths: set[str]) -> tuple[str, str, str]`: `(id, label, kind)`.
  - `setup_map(inventory, project: str | None) -> dict` with exactly these keys:

```text
sources   [{id, label, kind, count, problem: bool, stale_at: str | None}]
          kind in client, desktop, account, managed, shared, project, gateway, plugin
groups    [{id, kind, count}]                                  id == kind
items     [{id, kind, name, lookup, source, category, group, sources: [source id],
            clients: [client id], twice: [client id], review: bool}]   id == load-map row key
clients   [{id, name, status}]                                 status "found" | "unreadable"
relations [{type, from, to, ...}]
          defines | contains | overrides : from source id, to item id, + items: [inventory item ids]
          overrides also: over: source id (the definition it beats)
          routes_through : from item id, to "kitden", + items
          available_to   : from item id, to client id, + unknown: bool
```

The rules (the tests below pin them; this is the order the code follows):

- **Source group of one definition**, first match wins:
  1. `via_gateway == KITDEN_GATEWAY` → `("kitden", "Kitden gateway", "gateway")`.
  2. kind is not `PLUGIN` and `plugin_of(item)` gives `name@market` →
     `(f"plugin:{owner}:{name@market}", f"Plugin {name}", "plugin")`.
  3. `item.project` set → `("project", f"Project {folder name}", "project")`.
  4. a skill whose `source.path` is in `shared_paths` (the paths of items whose
     `source.owner_client == "shared"`; skill paths are already real paths) →
     `("shared", "Shared skills folder", "shared")`.
  5. `item.client == DESKTOP` → `("desktop", "Claude Desktop app", "desktop")`.
  6. owner = `source.owner_client` if it is in `NAMES`, else `item.client`; scope `ACCOUNT` →
     `(f"account:{owner}", f"{NAMES[owner]} account", "account")`; `MANAGED` →
     `(f"managed:{owner}", f"{NAMES[owner]} managed settings", "managed")`; else
     `(f"client:{owner}", f"{NAMES[owner]} all projects", "client")`.
  Plugin groups whose labels are equal add `" · <client name>"`; still equal, `" · <market>"`.
- **Items:** one per `load_map(inventory, project)` row of `MAP_KINDS`, in its order. A row's
  definitions: every inventory item of a `COLUMNS` client or `DESKTOP`, of that `row_key`, with
  `project` None or the picked one.
- **Lines:** each definition gives one line from its group: `routes_through` (gateway group, from
  the item to `"kitden"`), else `overrides` (the definition wins a `shadowed` pair with mode
  `"override"` in some client and neither side is in the Kitden gateway; `over` is the loser's
  group), else `contains` (plugin group), else `defines`. One relation per `(from, to)` pair: a
  stronger type replaces a weaker one (overrides > routes_through > contains > defines) and
  `items` gathers every definition behind the line. `available_to` for each column whose cell
  state is `on`, `gw` or `review` (`unknown: false`) or `unk` (`unknown: true`).
- `twice`: the clients of `DUPLICATE_IN_CLIENT` findings that hold a definition of the item.
  `review`: some cell is `"review"`.
- **Sources** listed: every group with a line, and every group with a problem. Order: `client`
  (in `COLUMNS` order), `desktop`, `account`, `managed`, `shared`, `project`, `gateway`, `plugin`
  (by label, ignoring case). `count`: items with a line to it. `item.sources` follow this order.
  `problem`: an `inventory.problems` source inside the picked project's folder marks `"project"`;
  any other marks its owner's group (`"desktop"` for the Desktop app); the group shows even with
  no items. `stale_at`: the earliest `stale_at` of the definitions behind its lines, else None.
- **Groups:** one per kind that has items, in `MAP_KINDS` order. **Clients:** `COLUMNS` whose
  status is found or unreadable, `name` from `NAMES`.

Builder call: an item is a Library row (load-map row key), so one name defined in two places is one item with two source lines; same-name items from different sources are separate only where the Library has separate rows (plugins per marketplace, instruction files per category), otherwise Part 2's "review" state flags them.
Builder call: a server held by the Kitden gateway gets `routes_through` (item → "Kitden gateway") in place of `defines`; registered gateways (Obot, MetaMCP) get no source of their own, since their servers are not in the inventory.
Builder call: the Claude Desktop app's items reach the Claude Code client, as in the Library's Claude Code column; marketplaces are not on the map (catalogs, not loaded items).
Builder call: a failed file outside the picked project marks its owner's "all projects" source, because a project at the home folder cannot be told from the user's own files; a false "Could not read" is safer than a hidden one.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_setup_map.py` (imports: `json`,
  `pytest`; `Client, ClientStatus, Item, ItemKind, Scope, Source, SourceKind` from
  `kitden.model`; `Inventory, build_inventory`; `NAMES` from `kitden.views.load_map`;
  `setup_map`; `make_home, write_cursor_fixture_state` from `tests.conftest`)

```python
@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    skill = home / ".agents/skills/review-kit/SKILL.md"  # read by Codex and Cursor
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review-kit\ndescription: Shared.\n---\n")
    return home


def node(answer, kind, lookup):
    return next(i for i in answer["items"] if (i["kind"], i["lookup"]) == (kind, lookup))


def lines(answer, item):
    return [r for r in answer["relations"] if item["id"] in (r["from"], r["to"])]


def found(*items, clients=("claude_code",)):
    return Inventory(clients=[Client(c, NAMES[c], ClientStatus.FOUND) for c in clients], items=list(items))


def test_a_shared_folder_is_one_source_with_a_line_to_each_client(home):
    answer = setup_map(build_inventory(home), None)
    kit = node(answer, "skill", "review-kit")
    assert (kit["sources"], kit["clients"], kit["twice"]) == (["shared"], ["codex", "cursor"], [])
    defines = [r for r in lines(answer, kit) if r["type"] == "defines"]
    assert [(r["from"], len(r["items"])) for r in defines] == [("shared", 2)]
    assert next(s for s in answer["sources"] if s["id"] == "shared")["label"] == "Shared skills folder"


def test_loads_twice_only_where_the_findings_say_so(home):
    answer = setup_map(build_inventory(home), None)
    docker = node(answer, "skill", "docker-expert")  # ~/.agents/skills and ~/.codex/skills
    assert docker["sources"] == ["client:codex", "shared"]
    assert docker["twice"] == ["codex", "cursor"]


def test_a_plugin_is_not_inside_its_own_plugin_group(home):
    answer = setup_map(build_inventory(home), None)
    assert node(answer, "plugin", "gmail@openai-curated-remote")["sources"] == ["client:codex"]
    group = "plugin:claude_code:superpowers@claude-plugins-official"
    brainstorming = node(answer, "skill", "brainstorming")
    assert brainstorming["sources"] == [group]
    assert [r["type"] for r in lines(answer, brainstorming) if r["from"] == group] == ["contains"]
    assert next(s for s in answer["sources"] if s["id"] == group)["label"] == "Plugin superpowers"


def test_a_project_override_says_what_it_overrides(home):
    inventory = build_inventory(home)
    answer = setup_map(inventory, str(home / "work/website"))
    plugin = node(answer, "plugin", "superpowers@claude-plugins-official")
    drawn = {(r["type"], r["from"], r.get("over")) for r in lines(answer, plugin) if r["type"] != "available_to"}
    assert drawn == {("overrides", "project", "client:claude_code"), ("defines", "client:claude_code", None)}
    assert plugin["clients"] == ["cursor"]  # off in Claude Code here; Cursor imports it
    assert [s["label"] for s in answer["sources"] if s["kind"] == "project"] == ["Project website"]
    assert not [s for s in setup_map(inventory, None)["sources"] if s["kind"] == "project"]


def test_a_server_in_the_kitden_gateway_routes_through_it():
    source = Source(SourceKind.FILE, "/data/gateway.json", "kitden", key_path="servers.github")
    held = Item("claude_code", ItemKind.MCP_SERVER, "github", source, Scope.USER, via_gateway="kitden")
    answer = setup_map(found(held), None)
    github = node(answer, "mcp_server", "github")
    assert [(r["type"], r["to"]) for r in lines(answer, github)] == [("routes_through", "kitden"), ("available_to", "claude_code")]
    assert answer["sources"] == [{"id": "kitden", "label": "Kitden gateway", "kind": "gateway", "count": 1, "problem": False, "stale_at": None}]


def test_an_unknown_on_off_state_is_only_maybe_available(home):
    answer = setup_map(build_inventory(home), None)
    gmail = node(answer, "plugin", "gmail@openai-curated-remote")  # Codex's plugin list not read
    assert [(r["to"], r["unknown"]) for r in lines(answer, gmail) if r["type"] == "available_to"] == [("codex", True)]


def test_a_client_that_could_not_be_read_keeps_its_node():
    inventory = Inventory(clients=[
        Client("claude_code", "Claude Code", ClientStatus.FOUND),
        Client("codex", "Codex", ClientStatus.NOT_FOUND),
        Client("cursor", "Cursor", ClientStatus.UNREADABLE),
    ])
    assert setup_map(inventory, None)["clients"] == [
        {"id": "claude_code", "name": "Claude Code", "status": "found"},
        {"id": "cursor", "name": "Cursor", "status": "unreadable"},
    ]


def test_a_file_that_could_not_be_read_marks_its_source(home):
    (home / ".cursor/mcp.json").write_text("{")
    (home / "work/website/.mcp.json").write_text("{")
    inventory = build_inventory(home)
    assert {s["id"]: s["problem"] for s in setup_map(inventory, None)["sources"]}["client:cursor"] is True
    website = setup_map(inventory, str(home / "work/website"))
    assert {s["id"]: s["problem"] for s in website["sources"]}["project"] is True


def test_two_plugins_with_one_name_say_whose():
    def skill(client, root):
        path = f"/h/{root}/plugins/cache/mkt/superpowers/1/skills/plan/SKILL.md"
        return Item(client, ItemKind.SKILL, "plan", Source(SourceKind.PLUGIN, path, client), Scope.PLUGIN)
    answer = setup_map(found(skill("claude_code", ".claude"), skill("codex", ".codex"), clients=("claude_code", "codex")), None)
    assert sorted(s["label"] for s in answer["sources"]) == ["Plugin superpowers · Claude Code", "Plugin superpowers · Codex"]


def test_groups_count_items_by_kind_without_marketplaces(home):
    answer = setup_map(build_inventory(home), None)
    assert [(g["kind"], g["count"]) for g in answer["groups"]] == [
        ("mcp_server", 8), ("plugin", 9), ("skill", 7), ("hook", 2), ("instructions", 4)]


def test_the_answer_is_the_same_each_time_and_holds_no_path(home):
    inventory = build_inventory(home)
    first = setup_map(inventory, None)
    assert first == setup_map(inventory, None)
    text = json.dumps(first)
    assert str(home) not in text and str(home.resolve()) not in text
    assert [s["id"] for s in first["sources"]][:3] == ["client:claude_code", "client:codex", "client:cursor"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_setup_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kitden.views.setup_map'`.

- [ ] **Step 3: Implement** `source_group` and `setup_map` in `src/kitden/views/setup_map.py` by
  the rules above. A module docstring says what it answers and that it reads only the inventory.
  Compute `find_findings` and the three effective views once per call.

- [ ] **Step 4: Run** `uv run pytest tests/unit/test_setup_map.py -v` → PASS; then the four checks.

- [ ] **Step 5: Commit**

```bash
git add src/kitden/views/setup_map.py tests/unit/test_setup_map.py
git commit -m "Setup map: where each item comes from and who has it"
```

---

### Task 2: The endpoint, the table-route test and the time budget (6.3, Done)

**Files:**
- Modify: `src/kitden/web/app.py` (beside `_map`: `_setup_map`; the route list)
- Modify: `scripts/measure-start.py`, `docs/development.md` ("## Speed")
- Test: `tests/unit/test_api_views.py`, `tests/unit/test_setup_map_api.py` (create),
  `tests/security/test_no_secrets.py`, `tests/unit/test_measure_start.py`

**Interfaces:**
- Consumes: Task 1 `setup_map`; Part 1 `build_demo_home`, `demo_build(home)` (a build that runs
  no client command), `create_app(..., demo=True)` (no version read), and the script's
  `measure_demo` line, which this one follows.
- Produces: `GET /api/setup-map?project=<id>` → `{"project": <project dict> | None, **setup_map(state.inventory, path)}`
  through `_read_model` (so an unknown id answers 404 "Unknown project.").
  `scripts/measure-start.py`: `MAP_BUDGET = 0.150`, `measure_map(root: Path, size: str = "large") -> float`.

Builder call: the map number is the slowest median of five answers, over All projects and each known project of the sample, through the app (TestClient), so JSON is counted too.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_api_views.py`: add `"/api/setup-map"` to `ENDPOINTS` (the 404 test covers it), and

```python
def test_setup_map_everywhere_and_for_a_project(client):
    everywhere = client.get("/api/setup-map").json()
    assert set(everywhere) == {"project", "sources", "groups", "items", "clients", "relations"}
    assert everywhere["project"] is None
    website = client.get(f"/api/setup-map?project={_project_id(client, 'work/website')}").json()
    assert "Project website" in [s["label"] for s in website["sources"]]
```

`tests/unit/test_setup_map_api.py` (the spec's "page test that the table route answers every map
question without the map"):

```python
LOADS = ("on", "gw", "unk", "review")

@pytest.fixture
def page(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as client:
        client.get("/?token=tok")
        yield client


def test_the_table_route_answers_every_map_question(page):
    """Who has an item, what defines it and where it loads twice: the Library's rows, Details
    and the findings answer each one, in every project, without the map."""
    for project in [None, *page.get("/api/projects").json()]:
        query = f"?project={project['id']}" if project else ""
        path = project["path"] if project else None
        drawn = page.get(f"/api/setup-map{query}").json()
        rows = {r["key"]: r for r in page.get(f"/api/map{query}").json()["rows"]}
        findings = page.get(f"/api/findings?project={path or ''}").json()  # takes the path
        twice = {(f["client"], i) for f in findings if f["type"] == "duplicate_in_client" for i in f["items"]}
        for item in drawn["items"]:
            row = rows[item["id"]]  # the Library has a row for every item on the map
            assert item["clients"] == [c for c, cell in row["cells"].items() if cell["state"] in LOADS]
            behind = {i for r in drawn["relations"] if r["type"] != "available_to"
                      and item["id"] in (r["from"], r["to"]) for i in r["items"]}
            ask = {"name": item["lookup"], "kind": item["kind"], "category": item["category"] or "",
                   "project": project["id"] if project else ""}
            details = page.get("/api/explain", params=ask).json()["definitions"]
            assert behind == {d["id"] for d in details if d["project"] in (None, path)}, item["name"]
            for client in item["twice"]:
                assert any((client, i) in twice for i in behind), item["name"]
```

`tests/security/test_no_secrets.py`: add `"/api/setup-map"` to the read list, and
`/api/setup-map?project=<id>` for every project in the loop that already reads each project; do
the same in Part 1's `_demo_outputs(home)` (beside `/api/map`, for All projects and each
project), so the sweep on all three samples covers the map.

`tests/unit/test_measure_start.py`:

```python
def test_the_map_measure_answers_on_the_small_sample(tmp_path):
    seconds = measure_start.measure_map(tmp_path, "small")
    assert 0 < seconds < 5
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_api_views.py tests/unit/test_setup_map_api.py tests/unit/test_measure_start.py tests/security/test_no_secrets.py -v`
Expected: FAIL (404 for `/api/setup-map`; no `measure_map`).

- [ ] **Step 3: Implement** `_setup_map(request, project, path)` and
  `Route("/api/setup-map", _read_model(_setup_map))` in `create_app`.

- [ ] **Step 4: Implement the map number** in `scripts/measure-start.py`:
  - `measure_map(root, size)`: `home = build_demo_home(root, size)`;
    `create_app(demo_build(home), token=…, port=…, home=home, demo=True)` (so no client command
    runs and the real `/Applications` paths in `clients/versions.py` are never reached); in a
    `starlette.testclient.TestClient` with the token cookie, time five `GET /api/setup-map` for
    All projects and for each project; return the slowest median, in seconds.
  - `main()` runs it after Part 1's demo line, prints
    `setup map: {ms:.0f} ms (budget {MAP_BUDGET * 1000:.0f} ms)`, and a missed budget gives exit 1.
  - The module docstring and the usage line name the new number.

- [ ] **Step 5: Update** `docs/development.md` "## Speed": one more bullet (**setup map**: the
  slowest median of five answers of `/api/setup-map` on the `large` sample, for All projects and
  each project; budget 150 ms), the count of numbers it prints, and the measured line with
  today's numbers and date.

- [ ] **Step 6: Run** the tests of Step 2 → PASS. Run `uv run python scripts/measure-start.py`:
  the `setup map:` line under 150 ms, every other line within its budget, exit 0. Then the four
  checks.

- [ ] **Step 7: Commit**

```bash
git add src/kitden/web/app.py scripts/measure-start.py docs/development.md tests/unit/test_api_views.py tests/unit/test_setup_map_api.py tests/security/test_no_secrets.py tests/unit/test_measure_start.py
git commit -m "Setup map: an endpoint, a table-route test and a 150 ms budget"
```

---

### Task 3: The map's layout, as pure functions (6.1, 6.2, 6.4)

**Files:**
- Create: `src/kitden/web/static/js/map.js` (pure part only)
- Modify: `src/kitden/web/static/js/parts.js` (export `LOAD_KINDS`, moved from `overview.js`),
  `src/kitden/web/static/js/overview.js` (import it), `src/kitden/web/static/js/dom.js`
  (`cutName`, moved from `gateway.js`), `src/kitden/web/static/js/gateway.js` (imports it and
  exports it again, so Part 5's tests stay as they are)
- Test: `tests/frontend/map.test.mjs` (create), `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: the `/api/setup-map` answer (Task 1 shape); `plural` (`dom.js`); `LOAD_KINDS`
  (`parts.js`: `[kind, one, many]` rows, "MCP server"/"MCP servers" … "instruction file"/"instruction files");
  `STATE_WORDS.unread` and `STATE_WORDS.review` (`parts.js`, Part 2); `cutName(name, max = 24)`
  (Part 5, moved to `dom.js` here so both pictures cut names the same way).
- Produces (all exported from `map.js`):
  - Constants: `ITEM_LIMIT = 30`, `SOURCE_LIMIT = 12`, `NODE_H = 36`, `ITEM_H = 28`, `GAP = 8`,
    `INDENT = 12`, `NARROW = "(max-width: 900px)"`,
    `CHARS = { source: 28, group: 24, item: 30, client: 16 }`,
    `RELATION_WORDS = { defines: "defines", contains: "contains", available_to: "available to", overrides: "overrides", routes_through: "routes through" }`,
    `UNKNOWN_WORDS = "may be available to"`.
  - `open` (the one argument shape, every key optional): `{ group: kind|null, all: bool, sources: bool, source: sourceId|null, q: string, item: itemId|null }`.
  - Node keys: `s:<source id>`, `g:<kind>`, `i:<item id>`, `c:<client id>`, `more:sources`, `more:items`, `search`.
  - `findItem(model, selected: {kind, name} | null) -> item | null`: same kind, `lookup === name` first, else `name === name`.
  - `searchItems(model, q: string) -> item[]`: names containing `q` (any case); exact names, then names that start with it, then the rest, each in model order; `[]` for a blank `q`.
  - `layoutMap(model, open) -> { height, nodes: [{ key, type, column, y, h, indent, label, title, count, flags, open, ref }] }`;
    `type` in `source group item client more search`; `flags` are `{ text, level, title }`.
  - `stackMap(model, open) -> [{ key, label, title, count, flags, open, items: [{ key, label, title, clients, flags, ref }], more }]`
  - `related(model, selection: {type: "client"|"source"|"item", id} | null) -> Set<nodeKey>`
  - `linesFor(model, itemId, drawnFor) -> [{ key, type, from, to, label, sentence, unknown, draw }]`
  - `lineGeometry(line, nodes: Map<key, node>, boxes: [{x, w}, {x, w}, {x, w}]) -> { d, at: {x, y} }`

The layout rules (`layoutMap`; `stackMap` uses the same folding):

- Column 0, sources, in model order. Without `open.sources` and with more than `SOURCE_LIMIT`:
  the first `SOURCE_LIMIT`, then any source of `open.item` not among them, then a `more` node
  `Show all ${model.sources.length}`.
- Column 1. With a non-blank `open.q`: a `search` node ("1 match", "N matches", "No matches"),
  then the matches. Otherwise one `group` node per group (`plural(count, one, many)` from
  `LOAD_KINDS`), and under the open one its items. The open group is `open.item`'s group when an
  item is selected, else `open.group`: one group is open at a time. A list shows its first
  `ITEM_LIMIT` items (all with `open.all`), then `open.item` if it was cut, then
  `more` `Show all ${listLength}`. Items have `h = ITEM_H`, `indent = INDENT`, a gap of 4.
- Column 2, clients, in model order.
- Every column starts at `y = 0`; other nodes are `NODE_H` tall with `GAP` between; `height` is
  the lowest bottom.
- Labels: `cutName(label, CHARS[column kind])`, `title` the full words. An item whose name another
  item in the same list shares says `name · source` (marketplace) or `name · category`.
- Flags: a source with `stale_at`, `Last read HH:MM` (info, title "From the last good read at
  HH:MM"); else with `problem`, `STATE_WORDS.unread` (warning). An item with `twice`, `Loads twice`
  (warning, title "Loads twice in Codex and Cursor"); with `review`, `STATE_WORDS.review` (info). A
  client with status unreadable, `STATE_WORDS.unread` (warning). State words come only from
  `STATE_WORDS`, so a rename stays one change.
- `stackMap`: one entry per shown source (folded as above, then a `more:sources` entry). The open
  entry is `open.source`, or the first source of `open.item` when the item is not under
  `open.source`; only the open entry lists its items (those with a line to that source, folded at
  `ITEM_LIMIT` as above, `more` the count cut). With a non-blank `q`: one entry, key `search`,
  label as the search node, open, with the matches.
- `related`: client → itself, every item available to it, their sources and groups. Source →
  itself, its items, their groups and clients. Item → itself, its group, its sources (and an
  override's `over`), its clients. `null` → empty set.
- `linesFor`: every relation that touches the item, in model order. `label`: `RELATION_WORDS`,
  or `UNKNOWN_WORDS` for an unknown `available_to`. `sentence`: "`<source>` defines `<item>`",
  "`<source>` contains `<item>`", "`<source>` overrides `<over>` for `<item>`", "`<item>` routes
  through `<source>`", "`<item>` is available to `<client>`" or "`<item>` may be available to
  `<client>`", with full labels and names. `draw` is `itemId !== drawnFor`.
- `lineGeometry`: the end in the left column uses that node's right edge (`x + w`), the end in
  the right column its left edge (`x + indent`); `y` is the node's middle. With `m` the middle
  of the two `x`: `d = "M ax ay C m ay, m by, bx by"`, `at = { x: m, y: (ay + by) / 2 }`.

Builder call: `cutName` moves from gateway.js to dom.js and map.js uses it, so one rule cuts names in the route diagram and the map.
Builder call: sources fold after 12 (plus the selected item's own), so the closed first view of a setup with 60 plugin sources still fits one window.
Builder call: a search on the map replaces the groups with one list of matches.
Builder call: an on/off state Kitden cannot read reads "may be available to" on its line, never "available to".
Builder call: source nodes can be selected too (they light their items and clients), so Tab and Enter work on every node.
Builder call: a source kept from the last good read says "Last read 14:02" on its node; Part 2's full sentence is its hover text.

- [ ] **Step 1: Write the failing tests** in `tests/frontend/map.test.mjs`. Header as
  `gateway.test.mjs` (stub `matchMedia`, delete `navigator`, then `await import(...map.js)`). Data:

```js
const src = (id, label, kind = 'client') => ({ id, label, kind, count: 1, problem: false, stale_at: null });
const it = (id, kind, name, sources, clients, more = {}) => ({ id, kind, name, lookup: name, source: null, category: null, group: kind, sources, clients, twice: [], review: false, ...more });
function model() {
  return {
    sources: [src('client:claude_code', 'Claude Code all projects'), src('client:codex', 'Codex all projects'), src('shared', 'Shared skills folder', 'shared'), src('kitden', 'Kitden gateway', 'gateway')],
    groups: [{ id: 'mcp_server', kind: 'mcp_server', count: 1 }, { id: 'skill', kind: 'skill', count: 2 }],
    items: [it('gh', 'mcp_server', 'github', ['kitden'], ['claude_code']),
      it('dx', 'skill', 'docker-expert', ['client:codex', 'shared'], ['codex', 'cursor'], { twice: ['codex', 'cursor'] }),
      it('rk', 'skill', 'review-kit', ['shared'], ['codex', 'cursor'])],
    clients: [{ id: 'claude_code', name: 'Claude Code', status: 'found' }, { id: 'codex', name: 'Codex', status: 'found' }, { id: 'cursor', name: 'Cursor', status: 'found' }],
    relations: [
      { type: 'routes_through', from: 'gh', to: 'kitden', items: ['a'] }, { type: 'available_to', from: 'gh', to: 'claude_code', unknown: false },
      { type: 'defines', from: 'client:codex', to: 'dx', items: ['b'] }, { type: 'defines', from: 'shared', to: 'dx', items: ['c', 'd'] },
      { type: 'available_to', from: 'dx', to: 'codex', unknown: false }, { type: 'available_to', from: 'dx', to: 'cursor', unknown: true },
      { type: 'defines', from: 'shared', to: 'rk', items: ['e', 'f'] }, { type: 'available_to', from: 'rk', to: 'codex', unknown: false }, { type: 'available_to', from: 'rk', to: 'cursor', unknown: false },
    ],
  };
}
// big(n, m): n sources 's0'… (labels 'Source 0'…), m skills 'k0'… where skill k is defined by source k % n.
```

Tests (names and what they assert):

- `the closed first view shows sources, groups and clients, and no items`: column keys are
  `['s:client:claude_code', 's:client:codex', 's:shared', 's:kitden']`, `['g:mcp_server', 'g:skill']`,
  `['c:claude_code', 'c:codex', 'c:cursor']`; the skill group's label is `'2 skills'`;
  `height === 4 * NODE_H + 3 * GAP`.
- `a large setup folds sources after twelve and keeps the first view short`: `big(70, 64)` →
  column 0 has `SOURCE_LIMIT + 1` nodes, the last `{ type: 'more', label: 'Show all 70' }`;
  `height <= (SOURCE_LIMIT + 1) * (NODE_H + GAP)`.
- `an open group shows its first 30 items, then Show all`: `{ group: 'skill' }` on `big(3, 64)` →
  30 item nodes then `more:items` labelled `'Show all 64'`; with `all: true`, 64 items and no `more:items`.
- `a selected item past the first 30 still shows, and so do its sources`: `big(70, 64)` with
  `{ item: 'k40' }` → 31 item nodes including `i:k40`; `s:s40` is in column 0 before `more:sources`.
- `the selected item opens its own group`: `{ group: 'mcp_server', item: 'dx' }` → the only group
  node with `open: true` is `g:skill`.
- `two items with one name say which is which`: plugins `superpowers` with sources
  `claude-plugins-official` and `cursor-public` → labels `'superpowers · claude-plugins-official'`
  and `'superpowers · cursor-public'`; instruction files `review` with categories `command` and
  `agent` → `'review · command'`, `'review · agent'`.
- `long names end with … and keep the full name in the title`: an item named `'x'.repeat(80)` →
  `label.length === CHARS.item`, `label.endsWith('…')`, `title === 'x'.repeat(80)`; a short
  name is unchanged.
- `flags say what the map does not know`: a source with `problem: true` → flag text
  `STATE_WORDS.unread` (`'Could not read'`); `dx` → flag `{ text: 'Loads twice', title: 'Loads twice in Codex and Cursor' }`;
  an item with `review: true` → `STATE_WORDS.review`; a client with status `unreadable` →
  `STATE_WORDS.unread`.
- `a search lists the matches in place of the groups`: `{ q: 'dock' }` → column 1 keys
  `['search', 'i:dx']`, search label `'1 match'`; `{ q: 'zzz' }` → `'No matches'`.
- `searchItems puts the exact name first, then names that start with it`: items `code-review`,
  `review-kit`, `review` → `['review', 'review-kit', 'code-review']`.
- `findItem takes the full plugin id or the name, of the same kind` (with the two `superpowers`
  plugins above, `lookup` `superpowers@<market>`):
  `{ kind: 'plugin', name: 'superpowers@cursor-public' }` finds that one; `{ kind: 'skill', name: 'review-kit' }`
  finds `rk`; `{ kind: 'plugin', name: 'review-kit' }` and `null` give `null`.
- `a client lights its sources, groups and items`: `related(model(), { type: 'client', id: 'cursor' })`
  equals `new Set(['c:cursor', 'i:dx', 'i:rk', 'g:skill', 's:client:codex', 's:shared'])`.
- `an item lights its sources, group and clients`: `gh` → `['i:gh', 'g:mcp_server', 's:kitden', 'c:claude_code']`.
- `a source lights its items and their clients`: `shared` → `['s:shared', 'i:dx', 'i:rk', 'g:skill', 'c:codex', 'c:cursor']`.
- `each line of an item has one label and one sentence`: `linesFor(model(), 'dx', null)` →
  `[from, to, label]` = `['s:client:codex','i:dx','defines']`, `['s:shared','i:dx','defines']`,
  `['i:dx','c:codex','available to']`, `['i:dx','c:cursor','may be available to']`; sentences
  `'Codex all projects defines docker-expert'` and `'docker-expert may be available to Cursor'`.
- `routes through runs from the item to the gateway`: first line of `gh` is
  `{ from: 'i:gh', to: 's:kitden', label: 'routes through', sentence: 'github routes through Kitden gateway' }`.
- `an override names what it overrides`: add source `project` ("Project website") and relation
  `{ type: 'overrides', from: 'project', to: 'dx', over: 'client:codex', items: ['g'] }` → sentence
  `'Project website overrides Codex all projects for docker-expert'`.
- `lines draw only when the selection is new`: every line of `linesFor(m, 'dx', 'dx')` has
  `draw === false`; of `linesFor(m, 'dx', 'rk')`, `true`.
- `a line runs from the right edge of a source to the left edge of an item`: boxes
  `[{x:0,w:200},{x:280,w:220},{x:580,w:140}]`, source at `y 0 h 36`, item at `y 100 h 28 indent 12` →
  `d === 'M 200 18 C 246 18, 246 114, 292 114'`, `at` `{ x: 246, y: 66 }`; an `available_to`
  line starts at `x 500` and ends at `x 580`; a `routes_through` line starts at `x 292`, ends at `x 200`.
- `the narrow list opens the selected item's source`: `stackMap(model(), { item: 'dx' })` → keys
  are the four sources; only `s:client:codex` is open, with items `[{ key: 'i:dx', clients: ['codex', 'cursor'] }]`;
  with `{ q: 'review' }` one entry `search` labelled `'1 match'`.
- `the layout is the same for the same input`: two calls `deepEqual`.

`tests/unit/test_page_words.py`, in `test_library_replaces_load_map_and_discover`: replace
`assert not (STATIC / "js" / "map.js").exists() and ...` with
`assert not (STATIC / "js" / "discover.js").exists()` and
`assert "Load map" not in script("map.js")` (the file is now the setup map, not the old page;
`#map` stays the old Library address, spec 2.5).

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/map.test.mjs` → FAIL (module not found).

- [ ] **Step 3: Move** `LOAD_KINDS` from `overview.js` to `parts.js` (exported, same rows),
  `overview.js` importing it; and `cutName` from `gateway.js` to `dom.js`, `gateway.js` importing
  and exporting it. Run `node --test tests/frontend/overview.test.mjs tests/frontend/gateway.test.mjs` → PASS.

- [ ] **Step 4: Implement** the constants and pure functions in `map.js` by the rules above. The
  file's first comment says it draws the setup map on the Overview and loads only when Map is
  shown. It imports only `dom.js` and `parts.js` for now.

- [ ] **Step 5: Run** `node --test tests/frontend/*.test.mjs` and
  `uv run pytest tests/unit/test_page_words.py tests/security/test_static_files.py -v` → PASS;
  then the four checks.

- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/map.js src/kitden/web/static/js/parts.js src/kitden/web/static/js/overview.js src/kitden/web/static/js/dom.js src/kitden/web/static/js/gateway.js tests/frontend/map.test.mjs tests/unit/test_page_words.py
git commit -m "Setup map: a fixed layout in three columns"
```

---

### Task 4: The List | Map switch and the map's nodes (6.1, 6.2, 6.4)

**Files:**
- Modify: `src/kitden/web/static/js/store.js`, `overview.js`, `map.js` (`renderMap`),
  `src/kitden/web/static/style.css` (a "Setup map" block before the reduced-motion rule),
  `docs/design.md`
- Test: `tests/frontend/store.test.mjs`, `tests/unit/test_page_words.py`,
  `tests/security/test_static_files.py`, `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: Task 3's functions; `current`, `currentError`, `setState`, `state`, `loadMap`,
  `render`, `retry` (`store.js`); `openItem` (`details.js`, Part 3); `closePanel` (`panel.js`); `mark`, `flag`, `opens`, `banner`,
  `skeleton` (`parts.js`); `glide` (`motion.js`); Part 2's `state.selected` shape.
- Produces:
  - `store.js`: `OVERVIEW_KEY = "kitden.overview"`; `overviewMode() -> "list" | "map"` (the choice
    made on this page, else local storage, else `"list"`; storage that throws or is missing reads as
    nothing); `setOverviewMode(mode)` (keeps it for the page, then tries local storage);
    `data.setupMap`; `loadSetupMap()` (`guarded("setupMap", "/api/setup-map?project=…")`).
    `reload()` reads it beside the others only while `state.view === "overview"` and
    `overviewMode() === "map"`; otherwise it drops the old answer's scope
    (`delete data.scope.setupMap`) so a later show reads again.
  - `map.js`: `renderMap(container: HTMLElement, model) -> void`.

What the page does:

- **Switch.** The Overview head holds the headline and, on its right, a `.seg` group
  (`aria-label` "Overview as") with "List" and "Map", `aria-pressed`, `data-focus`
  `overview:list` / `overview:map`, the show choice's sliding mark (`glide`, key
  `overview-mode`). Pressing one calls `setOverviewMode(mode)` and `render()`. With Map, the
  headline and lede stay and the map takes the place of the cards grid.
- **Lazy load.** `overview.js` keeps the loaded module in a variable. With the module and
  `current("setupMap")` at hand it calls `renderMap` at once (so a redraw keeps focus); else it
  shows `skeleton("card", 1)` and runs one `Promise.all([import("./map.js"), loadSetupMap()])`
  at a time, then `render()`; a failed read or import shows `banner("the map", retry)`.
- **Nodes (wider than 900 px).** `.setup-map` (`role="group"`, `aria-label` "Setup map") holds
  three quiet column heads ("Sources", "Items", "Clients") and `.map-cols`, a grid of three
  `.map-col` with a lane for lines between them; each column is `height` px tall. Each node is a
  `<button type="button" class="map-node <type>">` placed by `style.top`, `style.height` and
  `style.left = indent` (CSSOM, allowed by the CSP), with `data-focus="map:<key>"`, its cut label,
  `title`, a quiet count, and flags drawn by `flag()`. Client nodes start with `mark(id)`; item
  nodes end with `opens()`. Sources, items and clients carry `aria-pressed`; groups
  `aria-expanded`. The search node is a plain line, not a button.
- **Narrow (900 px and less, `matchMedia(NARROW)`, redrawn on change).** `.map-stack`: a row of
  client buttons (tile and name, `aria-pressed`), then each `stackMap` entry as a source button
  (`aria-expanded`) and, when open, its items: name, flags, the tiles of its clients, `opens()`.
- **Selection.** A client or source press selects it (a second press clears it); the map gets
  `.focusing` and the nodes in `related()` get `.lit`; the rest go quiet. An item press clears
  the client or source, calls `setState({ selected: { kind: item.kind, name: item.lookup } })`
  (the same value as Part 2's `rowSel` of its Library row), redraws and opens Details: the
  load-map row with `key === item.id` from `current("map")` (`await loadMap()` first when
  missing), `openItem(row, { instant: event.detail === 0 })`. A group press opens it (or closes
  the open one) and clears an item selection that is not in it, closing its Details
  (`closePanel({ instant: true, focus: false })`). "Show all" sets `all` or `sources` and moves
  focus to the first new node.
- **Keyboard.** Tab follows the DOM: sources, items, clients. Enter and Space press (native
  buttons). Escape on `.setup-map` clears the selection; a press on the empty map area does too.
  A redraw puts focus back on the node with the same `data-focus`.
- **Empty.** A model with no items shows `el("p", "empty", "Nothing to show here yet.")`.
- **Look.** Tokens only; nodes like quiet cards (`--panel`, `--wire`, radius 8); a selected node
  uses the selection surface and accent border, as `.btn.toggle[aria-pressed="true"]`; quiet nodes
  `opacity: 0.35`, as `.routes.focusing`; `:focus-visible` ring. Do not use the class `map`:
  the Library's table owns `.map th` and `.map td`.

Builder call: List is the default; the map is opt-in until walkthrough 2 says otherwise.
Builder call: with Map, the headline and lede stay and the map takes the whole width in place of the cards and the side column, so Details fits beside it.
Builder call: only the item selection goes in the address (`sel`); a selected client or source is the map's own and is not.
Builder call: the map writes `sel` with the item's `lookup` (the full plugin id that `/api/explain` takes); `findItem` reads a `lookup` or a name.
Builder call: opening another group clears the item selection, so one group is open at a time.
Builder call: the narrow list is a second drawing chosen with `matchMedia`, not CSS, so each width keeps one DOM.

- [ ] **Step 1: Write the failing tests**

`tests/frontend/store.test.mjs` (log each fetched URL in the stub in `requested`; set
`globalThis.localStorage` per test; `beforeEach` also resets `state.view = 'overview'`):

```js
test('the overview choice is read from storage and survives a blocked one', async () => {
  globalThis.localStorage = { getItem: (key) => (key === 'kitden.overview' ? 'map' : null), setItem() {} };
  assert.equal(overviewMode(), 'map');
  globalThis.localStorage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  setOverviewMode('list');
  assert.equal(overviewMode(), 'list');
});

test('reload reads the setup map only while it is shown', async () => {
  state.view = 'overview'; setOverviewMode('list'); requested.length = 0; await reload();
  assert.ok(!requested.some((u) => u.startsWith('/api/setup-map')));
  setOverviewMode('map'); await reload();
  assert.ok(requested.includes('/api/setup-map'));
  state.view = 'library'; await reload();
  assert.equal(current('setupMap'), null);
});

test('a project change never shows another project\'s map', async () => {
  fetchAnswers({ '/api/setup-map?project=a': { items: ['a-item'] } });
  state.view = 'overview'; setOverviewMode('map'); state.project = 'a'; await reload();
  assert.equal(current('setupMap').items[0], 'a-item');
  state.project = 'b';
  assert.equal(current('setupMap'), null);
});
```

`tests/unit/test_page_words.py`:

```python
def test_the_overview_shows_a_list_or_a_map_and_loads_the_map_only_when_shown():
    overview = script("overview.js")
    assert '"List"' in overview and '"Map"' in overview and '"Overview as"' in overview
    assert 'import("./map.js")' in overview
    assert not any('from "./map.js"' in p.read_text() for p in (STATIC / "js").glob("*.js"))
    assert 'OVERVIEW_KEY = "kitden.overview"' in script("store.js")


def test_the_map_says_what_it_shows_and_works_by_keyboard():
    text = script("map.js")
    for words in ("Sources", "Items", "Clients", "Show all", "Nothing to show here yet.",
                  "STATE_WORDS.unread", "STATE_WORDS.review", "Loads twice", '"Escape"',
                  "aria-pressed", "aria-expanded", "matchMedia(NARROW)", '"Setup map"'):
        assert words in text, words
    assert 'banner("the map"' in script("overview.js")


def test_the_map_has_its_own_class_and_no_idle_motion():
    css = (STATIC / "style.css").read_text()
    block = css[css.index("/* Setup map */"):css.index("@media (prefers-reduced-motion")]
    assert ".setup-map" in block and "infinite" not in block
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", block)  # tokens only, both themes
```

In `test_every_view_reads_project_data_through_current`, widen the pattern to
`r"\bdata\.(map|gateway|overview|setupMap)\b"`.

`tests/security/test_static_files.py`, `test_every_module_import_exists`: also check
`import\(\s*["'](\.[^"']+)["']\s*\)` targets.

`tests/unit/test_docs_words.py`:

```python
def test_design_md_describes_the_setup_map():
    design = " ".join((ROOT / "docs/design.md").read_text().split())
    for words in ("List | Map", "Sources, Items and Clients", "Show all", "under 900 px", "kitden.overview"):
        assert words in design, words
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/frontend/store.test.mjs` and
`uv run pytest tests/unit/test_page_words.py tests/security/test_static_files.py tests/unit/test_docs_words.py -v` → FAIL.

- [ ] **Step 3: Implement** the `store.js` names and the `reload()` rule.
- [ ] **Step 4: Implement** the switch and the lazy load in `overview.js`.
- [ ] **Step 5: Implement** `renderMap` in `map.js` (wide and narrow drawing, selection,
  keyboard, empty state), as described above. Listeners on `document` use
  `globalThis.document?.` so node tests can import the module.
- [ ] **Step 6: Add** the `/* Setup map */` block to `style.css`.
- [ ] **Step 7: Update** `docs/design.md`: in Components, a "Setup map" paragraph and table (the
  List | Map switch and the `kitden.overview` key; the three columns Sources, Items and Clients;
  source, group, item and client nodes with their flags; one group open, the first 30 then "Show
  all"; selection lights related nodes and quiets the rest at 0.35; the stacked list under 900
  px; Tab, Enter, Escape). In Performance: "The map's code and data load only when Map is shown;
  `/api/setup-map` answers in under 150 ms on the `large` sample."
- [ ] **Step 8: Run** the tests of Step 2 → PASS; the four checks; then
  `uv run python scripts/measure-start.py` → first usable still within 2 s.
- [ ] **Step 9: Look at it** in `kitden demo --size medium` (Part 1; nothing real runs): switch to
  Map, open groups, select a client, a source and an item, use only the keyboard, a window under
  900 px, both themes, and reduced motion. Nothing moves while idle.
- [ ] **Step 10: Commit**

```bash
git add src/kitden/web/static/js/store.js src/kitden/web/static/js/overview.js src/kitden/web/static/js/map.js src/kitden/web/static/style.css docs/design.md tests/frontend/store.test.mjs tests/unit/test_page_words.py tests/security/test_static_files.py tests/unit/test_docs_words.py
git commit -m "Overview: a List | Map switch and the setup map's nodes"
```

---

### Task 5: Lines, Details beside the map, and search (6.2, 6.4)

**Files:**
- Modify: `src/kitden/web/static/js/map.js`, `dom.js` (`svgEl`), `gateway.js` (`routes` uses
  `svgEl`), `panel.js` (`openPanel`, `closePanel`), `details.js` (`openItem`, `contextLinks`,
  the links' press), `app.js`, `src/kitden/web/static/style.css`, `docs/design.md`
- Test: `tests/frontend/details.test.mjs` (Part 3's `contextLinks` tests), `tests/unit/test_page_words.py`,
  `tests/unit/test_docs_words.py`; `tests/frontend/gateway.test.mjs` and `map.test.mjs` must still pass

**Interfaces:**
- Consumes: Task 3 `linesFor`, `lineGeometry`, `findItem`, `searchItems`; Task 4 `renderMap`,
  `overviewMode`, `setOverviewMode`; Part 2 `goTo`, `takeArrival()` (`store.js`), `rowSel(row)`;
  Part 3 `contextLinks(row, definitions, view) -> [{ label, view, selected }]`.
- Produces:
  - `dom.js`: `svgEl(tag: string, attrs: object = {}, text: string | null = null, parent: Element | null = null) -> SVGElement`
    (the `add` closure of `gateway.js routes()`, moved; Part 5 Task 7 rewrote `routes()` to draw
    from `routeLayout`, so find the helper there by what it does: it makes one SVG element with
    its attributes and text and appends it).
  - `panel.js`: `openPanel(content, { instant = false, beside = false })` toggles class `beside`
    on `#drawer` and `#scrim`; `closePanel()` ends by dispatching `kitden:panel-closed` on
    `document`. `details.js`: `openItem(row, { …, beside })` passes `beside` on.
  - `details.js`: `contextLinks` ends with `{ label: "Show on the map", view: "overview", selected: rowSel(row) }`
    unless `view === "map"`; `showDetails` passes `"map"` as `view` while the Overview shows the
    map; a link press with `view === "overview"` calls `setOverviewMode("map")` before `goTo`.
  - `app.js`: on the Overview with `overviewMode() === "map"`, typing in `#q` calls
    `go("overview", { q })` (it stays; elsewhere the search still opens the Library), and Enter
    in `#q` dispatches `kitden:pick`.

What the page does:

- **Lines.** With an item selected, after the nodes are in the page (next animation frame, and
  on every `ResizeObserver` callback of `.setup-map`), `map.js` measures the three `.map-col`
  boxes, then draws in `<svg class="map-lines" aria-hidden="true">` over `.map-cols` one
  `<path class="map-line" pathLength="1">` per line of `linesFor(model, id, lastDrawn)` with
  `lineGeometry`, a small arrowhead at its `to` end, and one label (`.map-label`: a panel-colored
  pill with the words) at `at`. A line with `draw` gets the class `draw` (the `wire-draw`
  keyframes, 700 ms `--ease-out`); then `lastDrawn = id`, so a resize or redraw does not draw
  again. An unknown line is dashed and appears at once. A visually hidden `role="status"`
  paragraph holds the sentences, joined. Client and source selections draw no lines.
- **Details beside.** From the map, `openItem(row, { beside: true, instant })`. From 1360 px wide:
  `.scrim.beside` is transparent and lets presses through, and while `#drawer.open.beside` is on
  the page (`:has()`) the map narrows so its right edge stays left of the drawer (from `100vw`,
  the rail width and `min(520px, 100vw)`); the lines follow through the `ResizeObserver`. Narrower
  windows get the usual panel over the page.
- **Selection from the address.** When `findItem(model, state.selected)` finds an item, its
  group opens and its lines draw. Details opens, instantly and beside, only when `takeArrival()`
  returns a selection (Part 2: an address, Back, or a "Show on the map" link), so a redraw never
  opens it again. On `kitden:panel-closed` the map redraws from `state.selected` (Part 2's
  `closePanel` clears it, so the lines go: Escape clears).
- **Search.** `renderMap` passes `state.q` as `open.q`. On `kitden:pick` the map selects
  `searchItems(model, state.q)[0]`, if any, and opens its Details.
- **Show on the map.** The last of Part 3's context links; pressing it sets Map and goes to the
  Overview with the item selected; it is left out while Details sits on the map.
- **`svgEl`.** `gateway.js routes()` uses it in place of its own `add`; nothing else changes there.

Builder call: Details sits beside the map from 1360 px wide (no scrim, the map keeps clear of it); narrower windows keep the usual panel, since a shrunk map would cut every label.
Builder call: the search box goes straight to an item only while the Overview shows the map; with List it still opens the Library, as today.
Builder call: lines carry an arrowhead at their `to` end, so direction follows the meaning (concept §5.2); an unknown line is dashed (shape, not only color) and is not drawn in.
Builder call: map nodes are HTML buttons, so gateway.js's SVG link helper (`opens(node, label, open)`) is not needed; only its `add` moves to `dom.js`, and the quiet 0.35 opacity matches `focusRoutes` without sharing its code.

- [ ] **Step 1: Write the failing tests**

`tests/frontend/details.test.mjs`, next to Part 3's `contextLinks` test 'links lead to another
page with the same item'. Every one of its cases now ends with the map link, since none passes
`'map'` as `view`; update its three label lists in this commit (`'overview'`: Compare across
clients, Manage tools, Show on the map; `'library'`: Manage tools, Show on the map; `'gateway'`:
Compare across clients, Show on the map):

```js
test('Show on the map comes last, except on the map itself', () => {
  const row = { kind: 'mcp_server', name: 'files' };   // as in Part 3's test
  const held = [{ via_gateway: 'kitden' }];
  assert.deepEqual(contextLinks(row, held, 'library').map((l) => l.label), ['Manage tools', 'Show on the map']);
  assert.deepEqual(contextLinks(row, held, 'library').at(-1), { label: 'Show on the map', view: 'overview', selected: rowSel(row) });
  assert.deepEqual(contextLinks(row, held, 'map').map((l) => l.label), ['Compare across clients', 'Manage tools']);
});
```

`tests/unit/test_page_words.py` (`panel()` is Part 3's helper that reads `panel.js`,
`details.js`, `tools.js` and `review.js`):

```python
def test_the_map_draws_labelled_lines_once_and_keeps_details_beside_it():
    text = script("map.js")
    for words in ("ResizeObserver", "lineGeometry(", "linesFor(", '"kitden:pick"',
                  '"kitden:panel-closed"', "beside: true", 'role", "status"', "takeArrival()"):
        assert words in text, words
    css = (STATIC / "style.css").read_text()
    assert ".scrim.beside" in css and ".map-line.draw" in css and "wire-draw" in css
    assert "@media (min-width: 1360px)" in css


def test_search_on_the_map_stays_on_the_overview():
    app = script("app.js")
    assert 'go("overview", { q })' in app and '"kitden:pick"' in app


def test_details_can_show_an_item_on_the_map():
    text = panel()
    assert '"Show on the map"' in text and 'setOverviewMode("map")' in text
    assert '"kitden:panel-closed"' in script("panel.js") and "beside" in script("panel.js")


def test_svg_nodes_are_made_by_one_helper():
    assert "export function svgEl(" in script("dom.js")
    gateway = script("gateway.js")
    assert "svgEl(" in gateway and "const add = (tag" not in gateway
```

`tests/unit/test_docs_words.py`, extend `test_design_md_describes_the_setup_map` with
`"routes through"`, `"may be available to"`, `"beside the map"`, `"draws once"`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_page_words.py tests/unit/test_docs_words.py -v` → FAIL.

- [ ] **Step 3: Move** `add` to `dom.js` as `svgEl`; `gateway.js` uses it. Run
  `node --test tests/frontend/gateway.test.mjs` → PASS.
- [ ] **Step 4: Implement** `beside` and the closed event in `panel.js`, and `beside`, the map
  link and its press in `details.js`; run `node --test tests/frontend/details.test.mjs` → PASS.
- [ ] **Step 5: Implement** lines, selection from the address, the closed-event redraw and
  `kitden:pick` in `map.js`; the `#q` changes in `app.js`.
- [ ] **Step 6: Add** the line, label, arrowhead, beside and 1360 px rules to the
  `/* Setup map */` block of `style.css` (the beside rule's media query sits there too).
- [ ] **Step 7: Update** `docs/design.md`: Setup map rows for lines (one label each: defines,
  contains, available to, may be available to, overrides, routes through; an arrowhead; dashed
  when unknown), Details beside the map from 1360 px, and search on the map; a Motion pattern row
  "Map line | `.map-line.draw` with `wire-draw` | Overview map: a selected item's lines; it draws
  once per new selection, a redraw does not draw again".
- [ ] **Step 8: Run** the tests of Step 2, `node --test tests/frontend/*.test.mjs` and the four
  checks → PASS. Look at it in `kitden demo --size medium`: select the shared skill
  `code-review`, the held server `files`, and `docs` with `~/work/atlas` picked (the project
  override); resize; open and close Details by keyboard; search and press Enter;
  "Show on the map" from the Library's Details; both themes; reduced motion shows lines at once.
- [ ] **Step 9: Commit**

```bash
git add src/kitden/web/static/js/map.js src/kitden/web/static/js/dom.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/panel.js src/kitden/web/static/js/details.js src/kitden/web/static/js/app.js src/kitden/web/static/style.css docs/design.md tests/frontend/details.test.mjs tests/unit/test_page_words.py tests/unit/test_docs_words.py
git commit -m "Setup map: labelled lines, Details beside it, and search"
```

---

### Task 6: README, the second walkthrough script and the roadmap (6.5)

**Files:**
- Modify: `README.md` ("### See what needs attention")
- Create: `docs/research/walkthrough-script-2.md`
- Test: `tests/unit/test_docs_words.py`
- `ROADMAP.md` only if the owner has committed their edit (see Step 4)

**Interfaces:**
- Consumes: Part 1's `docs/research/walkthrough-script-1.md` and the results file
  `docs/research/walkthrough-<date>.md` (or "skipped" in Part 2's ledger); the `medium` sample's
  names in `src/kitden/demo/`.

- [ ] **Step 1: Write the failing test** in `tests/unit/test_docs_words.py`:

```python
def test_readme_and_walkthrough_two_describe_the_map():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "Switch the Overview from List to Map" in readme
    script = " ".join((ROOT / "docs/research/walkthrough-script-2.md").read_text().split())
    for words in ("kitden demo --size medium", "walkthrough 1", "Part 7 hides the Map switch",
                  "the tour skips the map stop"):
        assert words in script, words
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v` → FAIL.

- [ ] **Step 3: Write the README lines** after the Overview paragraph: "Switch the Overview from
  List to Map to see where each item comes from: sources on the left, item groups in the middle,
  the clients on the right. Select a client, a source or an item to see how they connect;
  Details opens beside the map. The Library answers the same questions without the map." No new
  picture (Part 8 makes them).

- [ ] **Step 4: Write `docs/research/walkthrough-script-2.md`**, in the shape of script 1:
  - How to run: `uvx kitden demo --size medium` (or `uv run kitden demo --size medium`), a window
    at least 1440 px wide, light theme first; the owner gets no help before a task; the agent notes.
  - The seven tasks of concept §12, with the sample's own names (the same tasks as script 1, so
    the two can be compared), each as one plain instruction, the evidence of success from the
    concept, and (for the note-taker only) where the new page answers it: 1 why Codex and Cursor
    both have `code-review` (Map: `code-review` → "Shared skills folder", two "available to"
    lines); 2 what differs in `atlas` (Library, Differences: `api-style` missing in Claude Code,
    `docs` overridden in `atlas`); 3 add the missing skill to `atlas` only (Add missing, scope
    named before Apply); 4 the two `docs` servers of Claude Code and Codex (Needs review,
    Compare); 5 turn off `read_file` of `files` for `atlas` (Gateway tool origin; `atlas/web`
    follows it); 6 why Cursor still reaches `files` around the gateway (its "Direct" line and the
    limit line); 7 Undo the change from task 5.
  - A table to fill in: task, done (yes / partly / no), wrong turns, time to the first correct
    explanation, mistaken belief about scope or protection, the same task in walkthrough 1.
  - Two questions after: did the map help with tasks 1 and 4; keep "Map" on the Overview?
  - The rule from spec 6.5, in these words: "If the owner finds the map does not help, Part 7
    hides the Map switch: the Overview shows the list only, `/api/setup-map` and `map.js` stay in
    the code, and the tour skips the map stop. Fixes this walkthrough finds go into Part 7 before
    the deferred findings. If the owner skips the walkthrough, Part 7's ledger says 'skipped' and
    the map stays."
  - Results go to `docs/research/walkthrough-<date>.md`; the controller writes it.

- [ ] **Step 5: Run** `uv run pytest tests/unit/test_docs_words.py -v` → PASS; the four checks.

- [ ] **Step 6: Roadmap.** If `git status` still shows the owner's uncommitted `ROADMAP.md`, do not
  touch it; the report gives these lines. Otherwise make the change and stage it with the rest:
  - under "### Not released yet": "- **Setup map:** the Overview has a List | Map switch. The map
    shows sources, item groups and clients; select one to see where an item comes from and which
    clients have it, with Details beside it. Its code and data load only when it is shown."
  - move this part's line out of "## Planned", and drop the "A living map …" line from "## Later".

- [ ] **Step 7: Commit**

```bash
git add README.md docs/research/walkthrough-script-2.md tests/unit/test_docs_words.py
git commit -m "Docs: the setup map and the second walkthrough script"
```

(Add `ROADMAP.md` to the `git add` line only when Step 6 changed it.)
