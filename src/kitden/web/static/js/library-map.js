// The Library's map (library-notes §2): the clients, the plugins and skills they load by where they
// come from, and what an open plugin holds. It is drawn from /api/library-map
// (views/library_map.py) with the map every map page shares (map.js, map-view.js). Nothing here
// writes: a press only selects, unfolds and lights a path; Details (library-details.js) hear it. A
// plugin or a skill drags onto a client (map-drag.js), which only adds a row to the tray. Its
// Instructions tab (library-notes §6) draws the instruction files the clients read and what they
// pull in, from /api/instructions-map (views/instructions_map.py), in the same map; it only reads.
import { $, cutName, el, icon, joinWords, pageWaits, plural, reportError, WAITS } from "./dom.js";
import { findIn, layoutTree, linkKey, litFor, litFrom, pagesNow, pagesWith, shownFound, turnPage, turnWords } from "./map.js";
import { clientAt, covered, flyGhost, follow, liftGhost, mapArea, moveGhost, ON_CLIENT, pointOf, startDrag } from "./map-drag.js";
import { drawChip, glidePill } from "./map-page.js";
import { linkRemoval } from "./library-rules.js";
import { mapView } from "./map-view.js";
import { afterOldPage, CALM, rise, riseHead, shake } from "./motion.js";
import { banner, CLIENT_NAMES, CLIENT_ORDER, folderName, mark, ORIGIN_WORDS, scopeBar, setHint, skeleton, STATE_WORDS } from "./parts.js";
import { busy, current, currentError, projectPath, render, retry, setState, state, viewMode } from "./store.js";
import { say } from "./toast.js";
import { addToTray, inTray, keyFor, onTray, takeOut, tray } from "./tray.js";

export const LEDE = "Follow the source. Connect only what you need.";
const MAP_HINT = "Point at a link and press × to remove it · drag a plugin onto a client to add it there · + adds it for all projects · click anything for its Details";
// The map's columns at the mockup's x (0, 250, 500) and sizes (library-notes §2.1): a client
// 150×54, a plugin card 180×60 (a skill or hook row 34 high), an inside item 200×34. What a plugin
// holds, and the Inside caption, grow out of the plugin as it opens (map-view.js `grows`).
export const LIBRARY_COLUMNS = [
  { id: "clients", caption: "Clients", w: 150, h: 54, top: 140, rowGap: 18 },
  { id: "plugins", caption: "Plugins and skills", add: true, w: 180, h: 60, colGap: 100, top: 37, rowGap: 4 },
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
// The Map's own tabs. The address keeps the tab as the kind (`kind=instructions`), so Map | List
// keeps it too; Plugins and skills goes by "plugin".
const TABS = [["plugins", "Plugins and skills"], ["instructions", "Instructions"]];
const TAB_KINDS = { plugins: "plugin", instructions: "instructions" };
const mapTab = () => (state.kind === "instructions" ? "instructions" : "plugins");
// Each tab's answer (store.js), what its banner says it could not load, and its hint line.
const TAB_READS = { plugins: "libraryMap", instructions: "instructionsMap" };
const TAB_BANNERS = { plugins: "the library map", instructions: "the instruction files" };
export const INSTRUCTIONS_HINT = "Kitden only reads instruction files. It never changes them.";
// The Instructions tab's columns (library-notes §6): the same clients, a file card 190×54 at x 250,
// grouped by where it applies, and an import 200×40 at x 500.
export const INSTRUCTION_COLUMNS = [
  LIBRARY_COLUMNS[0],
  { id: "files", caption: "Files", w: 190, h: 54, colGap: 100, top: 37, rowGap: 4 },
  { id: "imports", caption: "Pulls in", w: 200, h: 40, colGap: 60, top: 60, rowGap: 16 },
];
const FILE_GROUPS = { all: "layers", project: "folder", commands: "square-terminal" };
// The words for a block of "Commands and agents" (`file.kind`), and with none here at all.
export const FILE_KINDS = { command: "command", agent: "agent" };
export const NO_FILES = "No instruction files here.";
// The Instructions tab's group ids carry this, so they never share an id with a group of Plugins
// and skills (`group:project`).
export const filesGroup = (key) => `group:files:${key}`;
const MISSING = { icon: "triangle-alert", words: "Missing" };
// Another tab's blocks grow from here and shrink back to its x (library-notes §6; map-view.js).
const TAB_FROM = { x: 150, y: 200 };
// What drags onto a client, and what a drop adds there for all projects.
const INSTALLS = { plugin: "plugin.install", skill: "skill.install" };
// Why a client cannot take a dragged item, before the drop (decisions, in this order).
const CURSOR_GETS = "Cursor gets plugins through Claude Code";
const WAITS_ALREADY = "Already in preview";
// A block whose add waits in the tray: a press takes it out. Its meta names the clients, or says
// it adds for all projects when it adds to several clients at once ("+ Add"); a meta too long for
// the card ends in "…", so its title says it whole.
const CLICK_OUT = "Click to take it out.";
const ALL_PROJECTS = "all projects";
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

// Whether the picked project's own settings decide the item there: for `client`, or for any client
// (`here` is per client, views/library_map.py).
export const decidedHere = (item, client = null) => (client ? Boolean((item.here || {})[client]) : Object.values(item.here || {}).some(Boolean));

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
  if (decidedHere(item)) block.tag = ORIGIN_WORDS.override;
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
  if (item.discovery) params.discovery = item.discovery;
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
    const wait = waitOn(block, addsOf(block.item, rows), project, clients, model);
    if (wait.rows.length) Object.assign(block, waitLook(wait));
  }
  return withNewCards(model, rows, project, clients);
}

// The adds of one block that show for `project`: a dashed link from each client they add to (in
// `model`), and the clients' names and the rows. `all`: each adds for all projects to several
// clients at once.
function waitOn(block, adds, project, clients, model) {
  const wait = { names: [], rows: [], all: true };
  for (const add of adds) {
    if (add.project && add.project !== project) continue;
    for (const client of add.clients) {
      if (!clients.has(`client:${client}`)) continue;
      model.links.push({ from: `client:${client}`, to: block.id, kind: "preview", row: add.key });
      if (!wait.names.includes(CLIENT_NAMES[client])) wait.names.push(CLIENT_NAMES[client]);
      if (!wait.rows.includes(add.key)) wait.rows.push(add.key);
    }
    if (add.project || add.clients.length < 2) wait.all = false;
  }
  return wait;
}

// How a block whose add waits looks: "Preview · Codex", or "Preview · all projects".
function waitLook(wait) {
  const meta = `Preview · ${wait.all ? ALL_PROJECTS : joinWords(wait.names)}`;
  return { meta, lamp: "preview", state: "preview", stateInMeta: true, takeOut: `${meta}. ${CLICK_OUT}`, rows: wait.rows };
}

// What Kitden knows of the plugins and skills the marketplaces offer, by id (the add panel's read,
// library-add.js): { kind, name, marketplace }.
const offered = new Map();
export function learnOffers(rows) {
  for (const row of rows || []) offered.set(row.id, { kind: row.kind, name: row.name, marketplace: row.marketplace });
}

// A plugin or skill a marketplace offers, as the map draws it: what the add panel read of it,
// else, for a plugin, its id ("<name>@<marketplace>"). Null when Kitden knows nothing of it.
function offerOf(kind, id) {
  const known = offered.get(id);
  if (known && known.kind === kind) return known;
  const at = id.lastIndexOf("@");
  return kind === "plugin" && at > 0 ? { kind, name: id.slice(0, at), marketplace: id.slice(at + 1) } : null;
}

// An add in the tray of something the map does not show (a plugin no client has, a skill inside
// a plugin) gets a preview card of its own at the end of its marketplace's group, a new group
// when the map has none; it looks and goes as any waiting add, and its group never pages it away.
function withNewCards(model, rows, project, clients) {
  const shown = new Set(model.blocks.filter((b) => b.drags).map((b) => `${b.kind}:${b.kind === "skill" ? b.item.skill : b.item.plugin}`));
  const cards = new Map();
  for (const row of rows) {
    const kind = Object.keys(INSTALLS).find((k) => INSTALLS[k] === row.body.action);
    const id = kind && (row.body.params || {})[kind];
    if (!id || shown.has(`${kind}:${id}`) || cards.has(`${kind}:${id}`)) continue;
    const offer = offerOf(kind, id);
    if (offer) cards.set(`${kind}:${id}`, { kind, id, offer });
  }
  for (const { kind, id, offer } of cards.values()) {
    const item = { kind, name: offer.name, [kind]: id };
    const block = { id: `item:new:${kind}:${id}`, column: "plugins", kind, name: offer.name, item, ports: { left: true } };
    if (kind === "skill") Object.assign(block, { h: ROW_H, label: ROW_LABELS.skill });
    const wait = waitOn(block, addsOf(item, rows), project, clients, model);
    if (!wait.rows.length) continue;
    model.blocks.push(Object.assign(block, waitLook(wait), { pinned: true, parent: marketGroup(model, offer.marketplace) }));
  }
  return model;
}

// The id of a marketplace's group on the map; a new caption, in name order among the marketplaces
// and before the other groups, when the map has none. It opens its Details as any marketplace's.
function marketGroup(model, name) {
  const id = `group:marketplace:${name}`;
  if (model.blocks.some((b) => b.id === id)) return id;
  const roots = model.blocks.filter((b) => b.kind === "group" && b.column === "plugins" && !b.parent);
  const next = roots.find((b) => !b.group || b.group.kind !== "marketplace" || b.name.toLowerCase() > name.toLowerCase());
  const group = { key: `marketplace:${name}`, name, icon: "store", kind: "marketplace", items: [] };
  const caption = { id, column: "plugins", kind: "group", name, icon: "store", before: GROUP_BEFORE, rowGap: LIBRARY_COLUMNS[1].rowGap, details: true, group };
  model.blocks.splice(next ? model.blocks.indexOf(next) : model.blocks.length, 0, caption);
  return id;
}

// The Instructions tab as one tree (decisions "Instructions"): the clients, each group of files
// ("All projects", "Only this project · <folder>", "Commands and agents") with a link from each
// client that reads a file, and what the files pull in. Only Claude Code follows imports (spec 6.1,
// D27): a file links to its imports, nested ones too, only while Claude Code reads it. A group with
// no file is not drawn.
export function instructionsTree(answer) {
  const blocks = answer.clients.map(clientBlock);
  const clients = new Set(answer.clients.map((client) => client.id));
  const links = [];
  for (const group of answer.groups.filter((one) => one.files.length)) {
    const id = filesGroup(group.key);
    blocks.push({ id, column: "files", kind: "group", name: group.name, icon: FILE_GROUPS[group.key], before: GROUP_BEFORE, rowGap: INSTRUCTION_COLUMNS[1].rowGap });
    for (const file of group.files) {
      const block = fileBlock(file, group, id);
      blocks.push(block);
      for (const client of readers(file)) if (clients.has(client)) links.push({ from: `client:${client}`, to: block.id, kind: "on" });
      for (const to of importsOf(file)) links.push({ from: block.id, to: `import:${to}`, kind: "on" });
    }
  }
  for (const imported of answer.imports || []) {
    blocks.push({ id: `import:${imported.id}`, column: "imports", kind: "import", name: imported.name, label: imported.missing ? MISSING : undefined, imported, ports: { left: true } });
  }
  return { columns: INSTRUCTION_COLUMNS, blocks, links };
}

// The clients that read a file, in client order; what it pulls in, while Claude Code reads it.
export const readers = (file) => CLIENT_ORDER.filter((client) => (file.by || {})[client]);
export const importsOf = (file) => ((file.by || {}).claude_code ? file.imports || [] : []);

// A file card: its name, a green lamp, and who reads it where: "Claude Code · this project",
// "Codex · all projects", "Claude Code · 2 imports", "Cursor · 2 rules" (a folder of rules),
// "Claude Code · command". Its title says the meta whole, where the card cuts it.
function fileBlock(file, group, parent) {
  const pulls = importsOf(file).length;
  const meta = fileMeta(file, group);
  return { id: `file:${file.id}`, column: "files", parent, kind: "file", name: file.name, meta, title: `${file.name} · ${meta}`, lamp: "on", state: "on", stateInMeta: true, file, ports: { left: true, right: pulls > 0 } };
}

function fileMeta(file, group) {
  const who = readers(file).map((client) => CLIENT_NAMES[client]).join(", ");
  const pulls = importsOf(file).length;
  if (FILE_KINDS[file.kind]) return `${who} · ${FILE_KINDS[file.kind]}`;
  if (typeof file.count === "number") return `${who} · ${plural(file.count, "rule", "rules")}`;
  if (pulls) return `${who} · ${plural(pulls, "import", "imports")}`;
  return `${who} · ${group.key === "project" ? "this project" : ALL_PROJECTS}`;
}

// A link whose removal or turning off waits in the tray is drawn leaving, and names its row: a press
// on it, or its ×, takes the row out. A plugin's removal from a client takes the faint lines through
// that client with it (Cursor through Claude Code): they draw leaving too, with no × and no row of
// their own. `answer` is the /api/library-map answer the model is from.
export function withLeaving(model, rows, answer) {
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  const removed = new Set(); // "<client>>block id" of a waiting plugin removal
  for (const link of model.links.filter((l) => l.kind === "on")) {
    const [from, to] = [byId.get(link.from), byId.get(link.to)];
    const change = from && from.client && to && to.item && linkRemoval(to.item, from.client, answer);
    const row = change && rows.find((r) => r.key === keyFor(change.body));
    if (!row) continue;
    Object.assign(link, { leaving: true, row: row.key });
    if (change.body.action === "plugin.remove") removed.add(`${from.client}>${to.id}`);
  }
  for (const link of model.links.filter((l) => l.kind === "faint")) {
    const [from, to] = [byId.get(link.from), byId.get(link.to)];
    const owner = from && to && to.item && (to.item.through || {})[from.client];
    if (owner && removed.has(`${owner}>${to.id}`)) link.leaving = true;
  }
  return model;
}

// What a block shows before its name: a client's tile, a plugin's puzzle tile, a file's tile, an
// import's bare icon.
const TILES = { plugin: ["block-icon", "puzzle", 15], file: ["block-icon", "file-text", 15], import: ["block-icon bare", "scroll-text", 13] };
function tile(block) {
  if (block.kind === "client") return mark(block.client);
  if (!TILES[block.kind]) return null;
  const [look, name, size] = TILES[block.kind];
  const holder = el("span", look);
  holder.append(icon(name, size));
  return holder;
}

// The map of this visit: its view, its tabs and the tab drawn, the answer it was drawn from and the
// tree, the plugin open (one at a time), the block selected, the pages of the groups that page (and
// the other tab's, kept for the way back: `tabPages`), what the search found and
// for which words, and the project it was drawn for.
// It is the drag engine's map too (map-drag.js): the layout drawn last, the drag that runs, the
// block held off its place, and how to draw again.
const onMap = { view: null, tabs: null, tab: "plugins", answer: null, model: null, open: new Set(), selected: null, pages: new Map(), tabPages: {}, found: null, searched: "", project: null, unfolds: false, folded: false, layout: null, drag: null, home: null, redraw: () => drawMap() };

// "+ Add" beside the Plugins and skills caption: `fn(button)` opens the add panel (library-add.js).
let addHook = null;
export function onLibraryAdd(fn) {
  addHook = fn;
}

// Details of a selection (library-details.js): `fn(id)` on a select (a block's id or a link's key),
// `fn(null)` on a let-go, and `fn(id or null, { follow: true })` once another project is drawn in
// place: the same selection, or null when that project does not have it.
let selectHook = null;
export function onLibrarySelect(fn) {
  selectHook = fn;
}

// The List opens the same Details as the map: `id` is a block id of the tab's tree (a row's), or
// null to let them go; `how` ({ follow: true }) when another project is drawn in place.
export function libraryDetails(id, how) {
  if (selectHook) selectHook(id, how);
}

// What the map shows now for a selection: `{ block }`, or `{ link, from, to }` for a link's key; null
// when the map has nothing of that id. `answer` is the /api/library-map answer it is drawn from.
// While the List shows, the tab's tree is drawn from its answer for Details only.
export function libraryThing(id) {
  const { model, answer } = shownTree();
  if (!id) return null;
  if (listOnly.has(id) && !(model && model.blocks.some((b) => b.id === id))) return { block: listOnly.get(id), answer };
  if (!model) return null;
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  if (byId.has(id)) return { block: byId.get(id), answer };
  const link = model.links.find((l) => linkKey(l) === id);
  return link ? { link, from: byId.get(link.from), to: byId.get(link.to), answer } : null;
}

// What the List draws that the map does not (a plugin Claude Code keeps in the account), as blocks
// for their Details: `{ id, kind: "account", name, reason, item }`. Each draw of the List's rows
// gives the whole set, so a row that is gone leaves no card behind.
const listOnly = new Map();
export function setListOnly(blocks) {
  listOnly.clear();
  for (const block of blocks) listOnly.set(block.id, block);
}

// The map's tree while it shows; else the shown tab's, kept while its answer stays the same.
const listed = { answer: null, model: null };
function shownTree() {
  if (onMap.view) return onMap;
  const tab = mapTab();
  // An answer with no clients is not a tree (a read that went wrong): nothing to draw from.
  const read = current(TAB_READS[tab]);
  const answer = read && read.clients ? read : null;
  if (answer && listed.answer !== answer) Object.assign(listed, { answer, model: tab === "instructions" ? instructionsTree(answer) : libraryTree(answer) });
  return answer ? listed : { model: null, answer: null };
}

// The List draws: the next Map is a new one, with an entrance.
export function leaveLibraryMap() {
  Object.assign(onMap, { view: null, tabs: null });
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
  // A new visit starts a new map, also when it first waits for the answer.
  if (!again) leaveLibraryMap();
  const tab = mapTab();
  const lede = el("p", "lede", LEDE);
  const tabs = mapTabs(tab);
  // The project goes by its folder name, as in the project picker.
  const scope = scopeBar(folderName(projectPath()));
  main.append(lede, tabs, scope);
  riseHead(head, lede, scope, { again });
  glidePill(tabs, tabs.querySelector('[aria-pressed="true"]'), "library-tabs-map");
  const answer = current(TAB_READS[tab]);
  if (!answer) {
    main.append(currentError(TAB_READS[tab]) ? banner(TAB_BANNERS[tab], retry) : skeleton("card", 2));
    return null;
  }
  setHint(tab === "plugins" ? MAP_HINT : INSTRUCTIONS_HINT);
  const fresh = !onMap.view;
  // A new map opens with no plugin open and nothing selected: a real setup has no first plugin.
  if (fresh) Object.assign(onMap, { view: newMap(), open: new Set(), selected: null, pages: new Map(), tabPages: {} });
  const projectChanged = !fresh && onMap.project !== state.project;
  onMap.project = state.project;
  // Another tab is drawn in the same map: the clients stay, the rest swaps (library-notes §6).
  const swap = !fresh && onMap.tab !== tab;
  // Each tab keeps the pages its groups were turned to, for the way back.
  if (swap) {
    onMap.tabPages[onMap.tab] = onMap.pages;
    onMap.pages = onMap.tabPages[tab] || new Map();
  }
  onMap.tab = tab;
  const had = onMap.selected;
  keepWhatShows(answer);
  if (tab === "instructions" && !answer.groups.some((group) => group.files.length)) main.append(el("p", "muted", NO_FILES));
  main.append(onMap.view.box);
  const text = state.q.trim();
  onMap.found = text ? findIn(onMap.model, text) : null;
  // A new search, or a new map, brings the pages of its matches.
  const matches = onMap.found && (fresh || text !== onMap.searched) ? [...onMap.found.matches] : [];
  onMap.searched = text;
  onMap.pages = pagesWith(onMap.model, pagesNow(onMap.model, onMap.pages), matches);
  const motion = fresh ? (switched ? "none" : "enter") : projectChanged ? "project" : "move";
  drawMap({ motion, swap });
  if (switched) rise([onMap.view.box], { delay: afterOldPage() });
  // Details follow the project drawn in place: the same selection, or none.
  if (projectChanged && had && selectHook) selectHook(onMap.selected, { follow: true });
  return chipFound(onMap.found);
}

// The tree for a new answer: the open plugin and the selection (a block, or a link) stay while the
// answer has them. The open plugin stays while the Instructions tab shows, for the way back.
function keepWhatShows(answer) {
  onMap.answer = answer;
  const rows = rowsShown(tray);
  const waited = waitingIds(onMap.model);
  onMap.model = treeOf(answer, rows);
  // An item whose add has just come into the tray shows: its group turns to its page.
  const fresh = [...waitingIds(onMap.model)].filter((id) => !waited.has(id));
  if (fresh.length) onMap.pages = pagesWith(onMap.model, pagesNow(onMap.model, onMap.pages), fresh);
  const ids = new Set([...onMap.model.blocks.map((block) => block.id), ...onMap.model.links.map(linkKey)]);
  if (onMap.tab === "plugins") onMap.open = new Set([...onMap.open].filter((id) => ids.has(id)));
  if (onMap.selected && !ids.has(onMap.selected)) onMap.selected = null;
}

// The tab's tree, with what waits in the tray on Plugins and skills. Instructions has none.
function treeOf(answer, rows) {
  if (onMap.tab === "instructions") return instructionsTree(answer);
  return withLeaving(withWaiting(libraryTree(answer), rows, state.project || ""), rows, answer);
}

// The blocks of a tree whose add waits in the tray.
function waitingIds(model) {
  return new Set(model ? model.blocks.filter((b) => b.rows).map((b) => b.id) : []);
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

// What the chip counts (app.js): what lights on the page shown, with a plugin card once however many
// of its parts match, open or folded. A match on another page is not counted.
function chipFound(found) {
  if (!found) return null;
  const parts = new Set(onMap.model.blocks.filter((block) => block.kind === "part").map((block) => block.id));
  const lit = { ...found, matches: new Set([...foundOnMap(found).matches].filter((id) => !parts.has(id))) };
  return shownFound(lit, onMap.layout);
}

// "Plugins and skills" | "Instructions" (.seg.sm), `tab` pressed. The same node stays while the
// page draws again in place, so its mark glides on (280 CALM) as the map swaps.
function mapTabs(tab) {
  if (!onMap.tabs) {
    onMap.tabs = el("div", "seg sm map-tabs");
    onMap.tabs.setAttribute("role", "group");
    onMap.tabs.setAttribute("aria-label", "Show");
    for (const [id, label] of TABS) {
      const choice = el("button", null, label);
      choice.type = "button";
      choice.dataset.focus = `map-tab:${id}`;
      choice.addEventListener("click", () => toTab(id, choice));
      onMap.tabs.append(choice);
    }
  }
  for (const choice of onMap.tabs.children) if (choice.dataset.focus) choice.setAttribute("aria-pressed", String(choice.dataset.focus === `map-tab:${tab}`));
  return onMap.tabs;
}

// A press on the other tab: the mark glides there, the selection lets go, the address keeps the
// tab, and the page draws it in the same map.
function toTab(id, choice) {
  if (id === mapTab()) return;
  for (const other of onMap.tabs.children) if (other.dataset.focus) other.setAttribute("aria-pressed", String(other === choice));
  glidePill(onMap.tabs, choice, "library-tabs-map");
  if (onMap.selected) letGo();
  setState({ kind: TAB_KINDS[id], selected: null });
  render();
}

function newMap() {
  const view = mapView({
    tile,
    onOpen: openPlugin,
    onFold: foldPlugin,
    onSelect: pressBlock,
    onAdd: (column, node) => addHook && addHook(node),
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
// `swap`: another tab is drawn, so its blocks grow from TAB_FROM (map-view.js).
function drawMap({ motion = "move", lightLater = false, swap = false } = {}) {
  const { view, model, selected } = onMap;
  if (!view) return Promise.resolve();
  const layout = layoutTree(model, { open: onMap.open, pages: onMap.pages, narrow: false });
  if (swap) layout.swap = TAB_FROM;
  onMap.layout = layout;
  const lit = litOf(model, selected);
  const later = lightLater && lit.size > 0;
  drawChip(chipFound(onMap.found));
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, lit: later ? new Set() : lit, found: foundOnMap(onMap.found), open: onMap.open, motion });
  if (later) drawn.then(() => onMap.view === view && onMap.selected === selected && drawMap());
  // A block dragged while the map draws again stays with the pointer.
  if (onMap.drag) follow(onMap);
  return drawn;
}

// What a selection lights (map.js litFor). An import lights the files that bring it in, not their
// clients (library-notes §6).
function litOf(model, selected) {
  if (!String(selected || "").startsWith("import:")) return litFor(model, selected);
  const lit = new Set([selected]);
  for (const link of model.links.filter((l) => l.to === selected)) lit.add(link.from).add(linkKey(link));
  return lit;
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

// The Library's drags, by kind, as the engine hears them (map-drag.js): plugin cards and skill
// rows of the map, and rows of the add panel.
export const DRAGS = {
  item: { begin: beginItem, over: overItem, drop: dropItem },
  row: { still: true, begin: beginRow, over: overRow, drop: dropRow },
};

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
  if (item.kind === "plugin" && client === "cursor") return CURSOR_GETS;
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

// A row of the add panel goes back onto its row after any let go.
const BACK_HOME = { dur: 180, ease: CALM };

// A press on a free row of the add panel (library-add.js gives its `item`, as the map's blocks
// have it, and its `node`) starts a drag onto a client, while the map shows. The same waits as a
// press on the map hold it back.
export function pressRow(event, row) {
  if (event.button !== 0 || busy.change || pageWaits() || onMap.drag || !onMap.model || !mapArea(onMap)) return;
  startDrag(event, { id: `row:${row.item.kind}:${row.item.name}`, name: row.item.name, ...row }, "row", { hooks: DRAGS, map: onMap, onStart: () => onMap.selected && letGo() });
}

// The row lifts (its ghost follows the pointer), and every client lights, as a glance does.
function beginRow(drag) {
  Object.assign(drag, liftGhost(drag.block.node), { target: null, why: null });
  onMap.view.glance(new Set(onMap.model.blocks.filter((b) => b.kind === "client").map((b) => b.id)));
}

// Over a client, and not over Details or the dock: a client that can take the item lights, the
// ghost takes the drop look and a dashed wire runs from the client to the pointer; the tip goes by
// the pointer. One that cannot stays as it is, and the tip says why.
function overRow(drag) {
  const { view } = onMap;
  moveGhost(drag);
  const point = covered(drag.at) ? null : pointOf(onMap, drag);
  const client = point ? clientAt(onMap, point) : null;
  if ((client && client.id) !== (drag.target && drag.target.id)) {
    drag.target = client;
    drag.why = client ? whyNot(drag.block.item, client.client) : null;
    view.unlightTarget();
    if (client && !drag.why) view.lightTarget(client.id);
  }
  const on = Boolean(client && !drag.why);
  drag.ghost.classList.toggle("over", on);
  if (on) view.wire(client.id, point);
  else view.unwire();
  if (!point) {
    view.untip();
    return;
  }
  const words = client ? drag.why || `Add to ${CLIENT_NAMES[client.client]}` : ON_CLIENT;
  view.tip(words, { on, at: point });
}

// A drop on a client that can take the item adds it there for all projects (one row, that client
// only); one on a client that cannot shakes it. The ghost always flies back onto its row.
function dropRow(drag, at) {
  const { view } = onMap;
  view.unwire();
  const client = at && drag.target;
  if (client && drag.why) {
    const node = view.node(client.id);
    if (node) shake(node);
  } else if (client) addToTray(addBody(drag.block.item, client.client)).catch(reportError);
  flyGhost(drag, null, BACK_HOME);
  return false;
}
