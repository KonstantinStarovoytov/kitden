// The Library's map (library-notes §2): the clients, the plugins and skills they load by where they
// come from, and what an open plugin holds. It is drawn from /api/library-map
// (views/library_map.py) with the map every map page shares (map.js, map-view.js). Nothing here
// writes: a press only selects, unfolds and lights a path; Details (library-details.js) hear it. A
// plugin or a skill drags onto a client (map-drag.js), which only adds a row to the tray.
import { $, cutName, el, icon, joinWords, pageWaits, plural, reportError, WAITS } from "./dom.js";
import { findIn, layoutTree, linkKey, litFor, litFrom, pagesNow, pagesWith, turnPage, turnWords } from "./map.js";
import { clientAt, covered, follow, ON_CLIENT, pointOf, startDrag } from "./map-drag.js";
import { glidePill, goSwitched, leaveThen } from "./map-page.js";
import { linkRemoval } from "./library-rules.js";
import { mapView } from "./map-view.js";
import { afterOldPage, rise, riseHead, shake } from "./motion.js";
import { banner, CLIENT_NAMES, folderName, mark, ORIGIN_WORDS, scopeBar, setHint, skeleton, STATE_WORDS } from "./parts.js";
import { busy, current, currentError, projectPath, retry, state, viewMode } from "./store.js";
import { say } from "./toast.js";
import { addToTray, inTray, keyFor, onTray, takeOut, tray } from "./tray.js";

const LEDE = "Follow the source. Connect only what you need.";
const MAP_HINT = "Point at a link for its Details · click a plugin to see what it holds · drag a plugin onto a client to add it there";
// The map's columns at the mockup's x (0, 250, 500) and sizes (library-notes §2.1): a client
// 150×54, a plugin card 180×60 (a skill or hook row 34 high), an inside item 200×34. What a plugin
// holds, and the Inside caption, grow out of the plugin as it opens (map-view.js `grows`).
export const LIBRARY_COLUMNS = [
  { id: "clients", caption: "Clients", w: 150, h: 54, top: 140, rowGap: 18 },
  { id: "plugins", caption: "Plugins and skills", w: 180, h: 60, colGap: 100, top: 37, rowGap: 4 },
  { id: "inside", caption: "Inside", w: 200, h: 34, colGap: 70, top: 26, rowGap: 8, grows: true },
];
const ROW_H = 34; // a skill or hook row in the Plugins and skills column
const GROUP_BEFORE = 15; // the space before a group caption, after the group above it
const INSIDE_PAGE = 8; // an open plugin's Inside column shows this many a page
// Its caption names the plugin cut to this many letters, so "<plugin> · 17–20 of 20" ends inside
// the map.
const INSIDE_NAME = 14;
// What a plugin holds, in this order: its key in the answer, the kind word and its icon.
const INSIDE_KINDS = [
  ["skills", "Skill", "sparkles"], ["commands", "Command", "square-terminal"], ["agents", "Agent", "bot"],
  ["hooks", "Hook", "webhook"], ["mcp_servers", "MCP server", "server"],
];
const ROW_LABELS = { skill: { icon: "sparkles", words: "Skill" }, hook: { icon: "webhook", words: "Hook" } };
// The clients' lamps: green while it loads through Kitden's facts ("Connected", "Via Claude Code"),
// none where Kitden could not read it, grey otherwise.
const CLIENT_LAMPS = { on: "on", via: "on", unreadable: null };
// The Map's own tabs: "Instructions" opens the List's Instructions tab until its map is drawn.
const TABS = [["plugins", "Plugins and skills"], ["instructions", "Instructions"]];
// What drags onto a client, and what a drop adds there for all projects.
const INSTALLS = { plugin: "plugin.install", skill: "skill.install" };
// Why a client cannot take a dragged item, before the drop (decisions, in this order).
const CURSOR_PLUGINS = "Cursor gets plugins through Claude Code";
const WAITS_ALREADY = "Already in preview";
// A block whose add waits in the tray: a press takes it out.
const IN_PREVIEW = "In preview. Click to take it out.";
// What the × of a link that the tray draws says, and the × while a change is written.
const TAKE_OUT = "Take it out of the preview";
const OWN_WAITS = "Your change is being written.";

// How many blocks the Plugins and skills column holds: plugins, skills and hooks.
const itemCount = (answer) => answer.groups.reduce((n, group) => n + group.items.length, 0);

// Map or List: the address's choice, else List past MAP_AT plugins and skills (viewMode), else
// the Map, also before Kitden has read them.
export function libraryMode() {
  const answer = current("libraryMap");
  return answer ? viewMode(state, itemCount(answer)) : state.mode || "map";
}

// An item's lamp: green while any client has it on, an amber dashed ring while Kitden knows of no
// client that has it on but does not know of one, grey while it is off in all of them.
export function lampOf(item) {
  const states = Object.values(item.by || {});
  if (states.includes("on")) return "on";
  return states.includes("unknown") ? "unk" : "off";
}

function clientBlock(client) {
  const lamp = client.state in CLIENT_LAMPS ? CLIENT_LAMPS[client.state] : "off";
  return { id: `client:${client.id}`, column: "clients", kind: "client", name: client.name, meta: client.words, lamp, state: lamp ? (lamp === "on" ? "on" : "off") : "unk", stateInMeta: true, client: client.id, ports: { right: true } };
}

// A plugin card says how many things Kitden read inside it, and has their count in its badge; with
// nothing read it says its state. A skill or a hook is a slim row with its kind word. In a project,
// "This project" marks an item whose state there comes from the project's own settings.
function itemBlock(item, group) {
  const lamp = lampOf(item);
  const block = { id: `item:${item.id}`, column: "plugins", parent: group, kind: item.kind, name: item.name, lamp, state: lamp, item, ports: { left: true }, drags: item.kind in INSTALLS };
  if (item.here) block.tag = ORIGIN_WORDS.override;
  if (item.kind !== "plugin") return { ...block, h: ROW_H, label: ROW_LABELS[item.kind] };
  const counted = typeof item.count === "number";
  Object.assign(block, { meta: counted ? plural(item.count, "item", "items") : STATE_WORDS[lamp], stateInMeta: !counted });
  if (counted && item.count > 0) Object.assign(block, { count: item.count, unit: "item", ports: { left: true, right: true } });
  return block;
}

// A solid link from each client that loads the item, a faint one where it loads it through
// another client's folder (Cursor through Claude Code). Off, not known, or "Via Claude Code" not
// loaded yet: no link.
function clientLinks(item, to, clients) {
  const links = [];
  for (const [client, on] of Object.entries(item.by || {})) {
    if (on !== "on" || !clients.has(client)) continue;
    links.push({ from: `client:${client}`, to, kind: (item.through || {})[client] ? "faint" : "on" });
  }
  return links;
}

// What a plugin holds, in the Inside column, each joined to it; the layout shows them while the
// plugin is open. Past one more than a page they sit in a group named for the plugin, which pages
// eight at a time. They have no state of their own: they follow their plugin.
function insideParts(item, plugin) {
  const parts = INSIDE_KINDS.flatMap(([key, words, mark]) => ((item.inside || {})[key] || []).map((name) => ({ key, name, label: { icon: mark, words } })));
  const blocks = [];
  let parent = plugin.id;
  if (parts.length > INSIDE_PAGE + 1) {
    parent = `inside:${plugin.id}`;
    blocks.push({ id: parent, column: "inside", parent: plugin.id, kind: "group", name: item.name, pageName: cutName(item.name, INSIDE_NAME), icon: "puzzle", pageSize: INSIDE_PAGE, rowGap: LIBRARY_COLUMNS[2].rowGap, grows: true });
  }
  for (const part of parts) blocks.push({ id: `part:${item.id}:${part.key}:${part.name}`, column: "inside", parent, kind: "part", name: part.name, label: part.label, ports: { left: true }, plugin: item, grows: true });
  const links = parts.map((part) => ({ from: plugin.id, to: `part:${item.id}:${part.key}:${part.name}`, kind: "on" }));
  return { blocks, links };
}

// The Library as one tree for the map (map.js), from the /api/library-map answer: the clients, then
// each source's group caption with its plugins, skills or hooks, in the answer's order, and what
// each plugin holds (layoutTree shows it only for the open plugin).
export function libraryTree(answer) {
  const blocks = answer.clients.map(clientBlock);
  const clients = new Set(answer.clients.map((client) => client.id));
  const links = [];
  for (const group of answer.groups) {
    const id = `group:${group.key}`;
    // A marketplace's caption opens its Details.
    const details = group.kind === "marketplace";
    blocks.push({ id, column: "plugins", kind: "group", name: group.name, icon: group.icon, before: GROUP_BEFORE, rowGap: LIBRARY_COLUMNS[1].rowGap, details, group });
    for (const item of group.items) {
      const block = itemBlock(item, id);
      blocks.push(block);
      links.push(...clientLinks(item, block.id, clients));
      const inside = insideParts(item, block);
      blocks.push(...inside.blocks);
      links.push(...inside.links);
    }
  }
  return { columns: LIBRARY_COLUMNS, blocks, links };
}

// Add `item` to one client, for all projects: the same body as a cell's add (library.js
// previewFor).
export function addBody(item, client) {
  const params = item.kind === "skill" ? { skill: item.skill } : { plugin: item.plugin };
  return { action: INSTALLS[item.kind], targets: [{ client }], params };
}

// The tray rows the map draws: none once their change is applied (the page then reads the result),
// and a row with no part yet only while it is asked, as on the Gateway.
function rowsShown(t) {
  if (t.phase === "applied") return [];
  return t.phase === "asking" ? t.rows : t.rows.filter((row) => row.part);
}

// The adds of `item` in `rows`, each with the clients it adds to: any row of its install action
// for its plugin or skill, for one client or several, for all projects or for one. The map's
// waiting look and "Already in preview" both read it, so they always agree.
export function addsOf(item, rows) {
  const id = item.kind === "skill" ? item.skill : item.plugin;
  if (!INSTALLS[item.kind] || !id) return [];
  const named = (params = {}) => (item.kind === "skill" ? params.skill : params.plugin) === id;
  return rows
    .filter((row) => row.body.action === INSTALLS[item.kind] && named(row.body.params))
    .map((row) => ({ key: row.key, clients: (row.body.targets || []).map((t) => t.client), project: (row.body.params || {}).project || "" }));
}

// Each add in the tray for an item on the map: a dashed link from each client it adds to, and the
// item says so ("Preview · Codex"); a press on either takes the row out. An add for one project
// shows only while that project is picked (`project`, "" for all projects).
export function withWaiting(model, rows, project) {
  const clients = new Set(model.blocks.filter((b) => b.kind === "client").map((b) => b.id));
  for (const block of model.blocks.filter((b) => b.drags)) {
    const wait = { names: [], rows: [] };
    for (const add of addsOf(block.item, rows)) {
      if (add.project && add.project !== project) continue;
      for (const client of add.clients) {
        if (!clients.has(`client:${client}`)) continue;
        model.links.push({ from: `client:${client}`, to: block.id, kind: "preview", row: add.key });
        if (!wait.names.includes(CLIENT_NAMES[client])) wait.names.push(CLIENT_NAMES[client]);
        if (!wait.rows.includes(add.key)) wait.rows.push(add.key);
      }
    }
    if (wait.rows.length) Object.assign(block, { meta: `Preview · ${joinWords(wait.names)}`, lamp: "preview", state: "preview", stateInMeta: true, takeOut: IN_PREVIEW, rows: wait.rows });
  }
  return model;
}

// A link whose removal or turning off waits in the tray is drawn leaving, and names its row: a press
// on it, or its ×, takes the row out. `answer` is the /api/library-map answer the model is from.
export function withLeaving(model, rows, answer) {
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  for (const link of model.links.filter((l) => l.kind === "on")) {
    const [from, to] = [byId.get(link.from), byId.get(link.to)];
    const change = from && from.client && to && to.item && linkRemoval(to.item, from.client, answer);
    const row = change && rows.find((r) => r.key === keyFor(change.body));
    if (row) Object.assign(link, { leaving: true, row: row.key });
  }
  return model;
}

// What a block shows before its name: a client's tile, a plugin's puzzle tile.
function tile(block) {
  if (block.kind === "client") return mark(block.client);
  if (block.kind !== "plugin") return null;
  const holder = el("span", "block-icon");
  holder.append(icon("puzzle", 15));
  return holder;
}

// The map of this visit: its view, the answer it was drawn from and the tree, the plugin open
// (one at a time), the block selected, the pages of the groups that page, what the search found and
// for which words, and the project it was drawn for.
// It is the drag engine's map too (map-drag.js): the layout drawn last, the drag that runs, the
// block held off its place, and how to draw again.
const onMap = { view: null, answer: null, model: null, open: new Set(), selected: null, pages: new Map(), found: null, searched: "", project: null, unfolds: false, folded: false, layout: null, drag: null, home: null, redraw: () => drawMap() };

// Details of a selection (library-details.js): `fn(id)` on a select (a block's id or a link's key),
// `fn(null)` on a let-go, and `fn(id or null, { follow: true })` once another project is drawn in
// place: the same selection, or null when that project does not have it.
let selectHook = null;
export function onLibrarySelect(fn) {
  selectHook = fn;
}

// What the map shows now for a selection: `{ block }`, or `{ link, from, to }` for a link's key; null
// when the map has nothing of that id. `answer` is the /api/library-map answer it is drawn from.
export function libraryThing(id) {
  const model = onMap.model;
  if (!model || !id) return null;
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  if (byId.has(id)) return { block: byId.get(id), answer: onMap.answer };
  const link = model.links.find((l) => linkKey(l) === id);
  return link ? { link, from: byId.get(link.from), to: byId.get(link.to), answer: onMap.answer } : null;
}

// The List draws: the next Map is a new one, with an entrance.
export function leaveLibraryMap() {
  onMap.view = null;
}

// Map | List lets go of what the map has selected.
export function letGoLibraryMap() {
  if (onMap.selected) letGo();
}

// Draws the Map under the page head (`head`, library.js): the lede, the tabs, the scope bar and
// the map, and the hint line. It returns what the top search lights, for the chip (chipFound), or
// null.
// `switched`: Map | List brought it, so it comes in as one piece instead of its entrance.
export function renderLibraryMap(main, { head, again = false, switched = false } = {}) {
  const lede = el("p", "lede", LEDE);
  const tabs = mapTabs();
  // The project goes by its folder name, as in the project picker.
  const scope = scopeBar(folderName(projectPath()));
  main.append(lede, tabs, scope);
  riseHead(head, lede, scope, { again });
  glidePill(tabs, tabs.querySelector('[aria-pressed="true"]'), "library-tabs-map");
  // A new visit starts a new map, also when it first waits for the answer.
  if (!again) onMap.view = null;
  const answer = current("libraryMap");
  if (!answer) {
    main.append(currentError("libraryMap") ? banner("the library map", retry) : skeleton("card", 2));
    return null;
  }
  setHint(MAP_HINT);
  const fresh = !onMap.view;
  // A new map opens with no plugin open and nothing selected: a real setup has no first plugin.
  if (fresh) Object.assign(onMap, { view: newMap(), open: new Set(), selected: null, pages: new Map() });
  const projectChanged = !fresh && onMap.project !== state.project;
  onMap.project = state.project;
  const had = onMap.selected;
  keepWhatShows(answer);
  main.append(onMap.view.box);
  const text = state.q.trim();
  onMap.found = text ? findIn(onMap.model, text) : null;
  // A new search, or a new map, brings the pages of its matches.
  const matches = onMap.found && (fresh || text !== onMap.searched) ? [...onMap.found.matches] : [];
  onMap.searched = text;
  onMap.pages = pagesWith(onMap.model, pagesNow(onMap.model, onMap.pages), matches);
  const motion = fresh ? (switched ? "none" : "enter") : projectChanged ? "project" : "move";
  drawMap({ motion });
  if (switched) rise([onMap.view.box], { delay: afterOldPage() });
  // Details follow the project drawn in place: the same selection, or none.
  if (projectChanged && had && selectHook) selectHook(onMap.selected, { follow: true });
  return chipFound(onMap.found);
}

// The tree for a new answer: the open plugin and the selection (a block, or a link) stay while the
// answer has them.
function keepWhatShows(answer) {
  onMap.answer = answer;
  const rows = rowsShown(tray);
  onMap.model = withLeaving(withWaiting(libraryTree(answer), rows, state.project || ""), rows, answer);
  const ids = new Set([...onMap.model.blocks.map((block) => block.id), ...onMap.model.links.map(linkKey)]);
  onMap.open = new Set([...onMap.open].filter((id) => ids.has(id)));
  if (onMap.selected && !ids.has(onMap.selected)) onMap.selected = null;
}

// What the map lights for a search: its matches, and a folded plugin that holds one (it stays
// folded: one plugin opens at a time, by a press).
function foundOnMap(found) {
  if (!found) return null;
  const matches = new Set(found.matches);
  for (const block of onMap.model.blocks) {
    if (block.kind === "part" && found.matches.has(block.id)) matches.add(`item:${block.plugin.id}`);
  }
  return { ...found, matches };
}

// What the chip counts (app.js): what lights, with a plugin card once however many of its parts
// match, open or folded.
function chipFound(found) {
  if (!found) return null;
  const parts = new Set(onMap.model.blocks.filter((block) => block.kind === "part").map((block) => block.id));
  return { ...found, matches: new Set([...foundOnMap(found).matches].filter((id) => !parts.has(id))) };
}

// "Plugins and skills" | "Instructions" (.seg.sm). Instructions has no map yet: the mark glides
// there (280 CALM), the map goes out and the List opens on its Instructions tab.
function mapTabs() {
  const seg = el("div", "seg sm map-tabs");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show");
  for (const [id, label] of TABS) {
    const choice = el("button", null, label);
    choice.type = "button";
    choice.setAttribute("aria-pressed", String(id === "plugins"));
    choice.dataset.focus = `map-tab:${id}`;
    if (id === "instructions") choice.addEventListener("click", () => toInstructions(seg, choice));
    seg.append(choice);
  }
  return seg;
}

function toInstructions(seg, choice) {
  for (const other of seg.children) if (other.dataset.focus) other.setAttribute("aria-pressed", String(other === choice));
  glidePill(seg, choice, "library-tabs-map");
  letGo();
  leaveThen(onMap.view && onMap.view.box, () => {
    if (state.view === "library") goSwitched("library", { mode: "list", kind: "instructions", selected: null });
  });
}

function newMap() {
  const view = mapView({
    tile,
    onOpen: openPlugin,
    onFold: foldPlugin,
    onSelect: pressBlock,
    onEmpty: () => onMap.selected && letGo(),
    // While nothing is selected, pointing at a client lights what it loads.
    onHover: (id) => view.glance(id && id.startsWith("client:") ? litFrom(onMap.model, id) : null),
    links: LINKS,
    enterDelay: afterOldPage(),
  });
  view.box.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && onMap.selected) letGo();
  });
  view.box.addEventListener("pointerdown", pressItem);
  watchDrawer();
  return view;
}

// Every link opens its Connection Details. A link has a × while the map can add its change to the
// tray (changeOf), or its change waits there: the × then takes it out. A link with none stays read
// only: it keeps its Details and leaves Delete to the page.
const LINKS = { canHit: () => true, tip: linkTip, waits: linksWait, onClick: pressLink, onRemove: removeLink };

// The tray row a link draws (a preview, or leaving), by its key; null for any other link. The
// layout's links do not carry the row, the map's do.
function rowOfLink(link) {
  const drawn = onMap.model && onMap.model.links.find((l) => linkKey(l) === linkKey(link));
  return (drawn && drawn.row) || null;
}

// What a link's × would add: from a client to a plugin or skill that loads there on its own. A
// faint line, a Cursor plugin, a hook and a plugin's inside items have none.
function changeOf(link) {
  const byId = onMap.model && new Map(onMap.model.blocks.map((b) => [b.id, b]));
  const [from, to] = byId ? [byId.get(link.from), byId.get(link.to)] : [];
  if (link.kind !== "on" || !from || from.kind !== "client" || !to || !to.item) return null;
  return linkRemoval(to.item, from.client, onMap.answer);
}

// What a link's × says; "" for no ×. A change already in the tray is taken out.
function linkTip(link) {
  if (rowOfLink(link)) return TAKE_OUT;
  const change = changeOf(link);
  if (!change) return "";
  return inTray(keyFor(change.body)) ? TAKE_OUT : change.tip;
}

// The × waits while a change is written, and says why.
function linksWait() {
  return tray.phase === "applying" || tray.phase === "applied" ? OWN_WAITS : busy.change && WAITS;
}

// The × of a link, or Delete on it: a row it draws, or its own change already in the tray, is taken
// out; any other change is added to the tray.
function removeLink(link) {
  if (linksWait()) return;
  const row = rowOfLink(link);
  const change = row ? null : changeOf(link);
  let done = null;
  if (row) done = takeOut(row);
  else if (change) done = inTray(keyFor(change.body)) ? takeOut(keyFor(change.body)) : addToTray(change.body);
  if (done) done.catch(reportError);
}

// A press on a link selects it: its two ends light and its Details open. A second press lets go.
// A link the tray draws (a preview, or leaving) is taken out of it instead.
function pressLink(link) {
  const key = linkKey(link);
  const row = rowOfLink(link);
  if (row) {
    takeOutWaiting([row]);
    return;
  }
  if (onMap.selected === key) {
    letGo();
    return;
  }
  onMap.selected = key;
  drawMap();
  if (selectHook) selectHook(key);
}

// Details closing (Escape, Close, another place) lets go of what the map selected.
let watching = false;
function watchDrawer() {
  const drawer = $("#drawer");
  if (watching || !drawer) return;
  watching = true;
  new MutationObserver(() => {
    if (!drawer.classList.contains("open") && onMap.selected) letGo();
  }).observe(drawer, { attributes: true, attributeFilter: ["class"] });
}

// Draw the map as it is now. A press that opened a plugin draws its selection first and lights
// its path once what it holds has come in.
function drawMap({ motion = "move", lightLater = false } = {}) {
  const { view, model, selected } = onMap;
  if (!view) return Promise.resolve();
  const layout = layoutTree(model, { open: onMap.open, pages: onMap.pages, narrow: false });
  onMap.layout = layout;
  const lit = litFor(model, selected);
  const later = lightLater && lit.size > 0;
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, lit: later ? new Set() : lit, found: foundOnMap(onMap.found), open: onMap.open, motion });
  if (later) drawn.then(() => onMap.view === view && onMap.selected === selected && drawMap());
  // A block dragged while the map draws again stays with the pointer.
  if (onMap.drag) follow(onMap);
  return drawn;
}

// A press on a plugin card (map-view calls it before pressBlock): the selected open plugin folds;
// any other opens in place of the one open.
function openPlugin(id) {
  if (waitingRows(id).length) return;
  onMap.folded = onMap.selected === id && onMap.open.has(id);
  onMap.unfolds = !onMap.folded && !onMap.open.has(id);
  if (onMap.folded) onMap.open = new Set();
  else if (onMap.unfolds) onMap.open = new Set([id]);
}

// A press on a plugin card's count opens it in place of the one open, or folds it, and nothing else.
// A selection the change hides is let go.
function foldPlugin(id) {
  onMap.open = onMap.open.has(id) ? new Set() : new Set([id]);
  const layout = layoutTree(onMap.model, { open: onMap.open, pages: onMap.pages, narrow: false });
  if (onMap.selected && !layout.blocks.some((at) => at.id === onMap.selected)) letGo();
  else drawMap();
}

// A press on a block. "N more" turns its group's page. A press that folded a plugin, or a second
// press on the selected block, lets go. Any other block is selected: its path lights.
function pressBlock(id) {
  if (id.startsWith("more:")) {
    turnOnMap(id);
    return;
  }
  const { folded, unfolds } = onMap;
  onMap.folded = false;
  onMap.unfolds = false;
  const waiting = waitingRows(id);
  if (waiting.length) {
    takeOutWaiting(waiting);
    return;
  }
  if (folded || (onMap.selected === id && !unfolds)) {
    letGo();
    return;
  }
  const block = onMap.model.blocks.find((b) => b.id === id);
  if (!block) return;
  onMap.selected = id;
  drawMap({ lightLater: unfolds });
  if (selectHook) selectHook(id);
}

// "N more" shows the next page in place, and a screen reader hears which ones show. A selection
// the turn hides is let go.
function turnOnMap(id) {
  onMap.pages = turnPage(onMap.model, onMap.pages, id);
  say(turnWords(onMap.model, onMap.pages, id));
  const layout = layoutTree(onMap.model, { open: onMap.open, pages: onMap.pages, narrow: false });
  if (onMap.selected && !layout.blocks.some((at) => at.id === onMap.selected)) letGo();
  else drawMap();
}

function letGo() {
  onMap.selected = null;
  drawMap();
  if (selectHook) selectHook(null);
}

// The tray rows of the adds that wait for a block ([] for none).
function waitingRows(id) {
  const block = onMap.model && onMap.model.blocks.find((b) => b.id === id);
  return (block && block.rows) || [];
}

// A press on a waiting add takes its rows out of the tray, but not while a change is written.
function takeOutWaiting(keys) {
  if (!busy.change) takeOut(keys).catch(reportError);
}

// The tray changed: the map draws its adds again in place, while it shows. Not while the change is
// applied: the page reads the result first.
onTray((t) => {
  if (t.phase === "applied" || !onMap.view || !onMap.answer || !onMap.view.box.isConnected) return;
  keepWhatShows(onMap.answer);
  drawMap();
});

// The Library's drags, by kind, as the engine hears them (map-drag.js). Only plugin cards and
// skill rows drag.
export const DRAGS = { item: { begin: beginItem, over: overItem, drop: dropItem } };

// A pointer goes down on a plugin card or a skill row (its count too): once it moves 5 px it drags
// onto a client, and the selection lets go. A press while a change is written, or while another
// project is read, does nothing here.
function pressItem(event) {
  if (event.button !== 0 || busy.change || pageWaits() || onMap.drag || !onMap.model) return;
  const node = event.target.closest("button.block, button.block-count");
  const block = node && onMap.model.blocks.find((b) => b.drags && [`block:${b.id}`, `count:${b.id}`].includes(node.dataset.focus));
  if (block) startDrag(event, block, "item", { hooks: DRAGS, map: onMap, onStart: () => onMap.selected && letGo() });
}

// The block and every client light, as a glance does, and the tip asks for a client.
function beginItem(drag) {
  const clients = onMap.model.blocks.filter((b) => b.kind === "client").map((b) => b.id);
  onMap.view.glance(new Set([drag.id, ...clients]));
  Object.assign(drag, { target: null, why: null });
  tipItem(drag);
}

// The pointer over a client, and not over Details or the dock: a client that can take the item
// lights, and a dashed wire runs from it to the block; one that cannot stays as it is and the tip
// says why. Off a client the light goes and the wire fades.
function overItem(drag) {
  const { view } = onMap;
  const point = covered(drag.at) ? null : pointOf(onMap, drag);
  const client = point ? clientAt(onMap, point) : null;
  if ((client && client.id) !== (drag.target && drag.target.id)) {
    drag.target = client;
    drag.why = client ? whyNot(drag.block.item, client.client) : null;
    view.unlightTarget();
    view.unwire();
    if (client && !drag.why) {
      view.lightTarget(client.id);
      view.wire(client.id, drag.id);
    }
  }
  tipItem(drag);
}

function tipItem(drag) {
  const client = drag.target;
  const words = client ? drag.why || `Add to ${CLIENT_NAMES[client.client]}` : ON_CLIENT;
  onMap.view.tip(words, { on: Boolean(client && !drag.why) });
}

// Why `client` cannot take the item, first match wins; null when it can (the server may still
// refuse, and the bar says why). Any add of it for that client in the tray, for any project,
// says "Already in preview".
function whyNot(item, client) {
  const who = CLIENT_NAMES[client];
  if (item.kind === "plugin" && client === "cursor") return CURSOR_PLUGINS;
  const has = (item.by || {})[client];
  if (has && has !== "via") return `Already in ${who}`;
  if (addsOf(item, tray.rows).some((add) => add.clients.includes(client))) return WAITS_ALREADY;
  if (!((item.can && item.can.add) || []).includes(client)) return `${who} cannot get ${item.name}`;
  return null;
}

// A drop on a client that can take the item adds it there for all projects (one row, that client
// only); a drop on one that cannot shakes it. The block always comes home, so the drop is never
// taken.
function dropItem(drag, at) {
  const { view } = onMap;
  view.unwire();
  const client = at && drag.target;
  if (client && drag.why) {
    const node = view.node(client.id);
    if (node) shake(node);
  } else if (client) addToTray(addBody(drag.block.item, client.client)).catch(reportError);
  return false;
}
