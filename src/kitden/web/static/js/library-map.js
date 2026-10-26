// The Library's map (library-notes §2): the clients, the plugins and skills they load by where they
// come from, and what an open plugin holds. It is drawn from /api/library-map
// (views/library_map.py) with the map every map page shares (map.js, map-view.js). Nothing here
// writes: a press only selects, unfolds and lights a path.
import { el, icon, plural } from "./dom.js";
import { findIn, layoutTree, litFor, litFrom, pagesNow, pagesWith, turnPage, turnWords } from "./map.js";
import { glidePill, goSwitched, leaveThen } from "./map-page.js";
import { mapView } from "./map-view.js";
import { afterOldPage, rise, riseHead } from "./motion.js";
import { banner, folderName, mark, ORIGIN_WORDS, scopeBar, setHint, skeleton, STATE_WORDS } from "./parts.js";
import { current, currentError, projectPath, retry, state, viewMode } from "./store.js";
import { say } from "./toast.js";

const LEDE = "Follow the source. Connect only what you need.";
const MAP_HINT = "Point at a link for its Details · click a plugin to see what it holds · Turn off… waits in preview, then Apply";
// The map's columns at the mockup's x (0, 250, 500) and sizes (library-notes §2.1): a client
// 150×54, a plugin card 180×60 (a skill or hook row 34 high), an inside item 200×34.
export const LIBRARY_COLUMNS = [
  { id: "clients", caption: "Clients", w: 150, h: 54, top: 140, rowGap: 18 },
  { id: "plugins", caption: "Plugins and skills", w: 180, h: 60, colGap: 100, top: 37, rowGap: 4 },
  { id: "inside", caption: "Inside", w: 200, h: 34, colGap: 70, top: 26, rowGap: 8 },
];
const ROW_H = 34; // a skill or hook row in the Plugins and skills column
const GROUP_BEFORE = 15; // the space before a group caption, after the group above it
const INSIDE_PAGE = 8; // an open plugin's Inside column shows this many a page
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

// How many blocks the Plugins and skills column holds.
const itemCount = (answer) => answer.groups.reduce((n, group) => n + group.items.length, 0);

// Map or List: the address's choice, else List past MAP_AT plugins and skills (viewMode), else
// the Map, also before Kitden has read them.
export function libraryMode() {
  const answer = current("libraryMap");
  return answer ? viewMode(state, itemCount(answer)) : state.mode || "map";
}

// An item's lamp: green while any client has it on, an amber dashed ring while Kitden knows of no
// client that has it on but does not know of one, grey while it is off in all of them.
function lampOf(item) {
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
  const block = { id: `item:${item.id}`, column: "plugins", parent: group, kind: item.kind, name: item.name, lamp, state: lamp, item, ports: { left: true } };
  if (item.here) block.tag = ORIGIN_WORDS.override;
  if (item.kind !== "plugin") return { ...block, h: ROW_H, label: ROW_LABELS[item.kind] };
  const counted = typeof item.count === "number";
  Object.assign(block, { meta: counted ? plural(item.count, "item", "items") : STATE_WORDS[lamp], stateInMeta: !counted });
  if (counted && item.count > 0) Object.assign(block, { count: item.count, ports: { left: true, right: true } });
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

// What an open plugin holds, in the Inside column, each joined to it. Past one more than a page
// they sit in a group named for the plugin, which pages eight at a time. They have no state of
// their own: they follow their plugin.
function insideParts(item, plugin) {
  const parts = INSIDE_KINDS.flatMap(([key, words, mark]) => ((item.inside || {})[key] || []).map((name) => ({ key, name, label: { icon: mark, words } })));
  const blocks = [];
  let parent = plugin.id;
  if (parts.length > INSIDE_PAGE + 1) {
    parent = `inside:${plugin.id}`;
    blocks.push({ id: parent, column: "inside", parent: plugin.id, kind: "group", name: item.name, icon: "puzzle", pageSize: INSIDE_PAGE, rowGap: LIBRARY_COLUMNS[2].rowGap });
  }
  for (const part of parts) blocks.push({ id: `part:${item.id}:${part.key}:${part.name}`, column: "inside", parent, kind: "part", name: part.name, label: part.label, ports: { left: true }, plugin: item });
  const links = parts.map((part) => ({ from: plugin.id, to: `part:${item.id}:${part.key}:${part.name}`, kind: "on" }));
  return { blocks, links };
}

// The Library as one tree for the map (map.js), from the /api/library-map answer: the clients, then
// each source's group caption with its plugins, skills or hooks, in the answer's order, and what the
// `open` plugin holds.
export function libraryTree(answer, { open = new Set() } = {}) {
  const blocks = answer.clients.map(clientBlock);
  const clients = new Set(answer.clients.map((client) => client.id));
  const links = [];
  for (const group of answer.groups) {
    const id = `group:${group.key}`;
    blocks.push({ id, column: "plugins", kind: "group", name: group.name, icon: group.icon, before: GROUP_BEFORE, rowGap: LIBRARY_COLUMNS[1].rowGap });
    for (const item of group.items) {
      const block = itemBlock(item, id);
      blocks.push(block);
      links.push(...clientLinks(item, block.id, clients));
      if (!open.has(block.id)) continue;
      const inside = insideParts(item, block);
      blocks.push(...inside.blocks);
      links.push(...inside.links);
    }
  }
  return { columns: LIBRARY_COLUMNS, blocks, links };
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
const onMap = { view: null, answer: null, model: null, open: new Set(), selected: null, pages: new Map(), found: null, searched: "", project: null, unfolds: false, folded: false };

// Details of a selection (Task 6 fills it): `fn(block)` on a select, `fn(null)` on a let-go.
let selectHook = null;
export function onLibrarySelect(fn) {
  selectHook = fn;
}

// The List draws: the next Map is a new one, with an entrance.
export function leaveLibraryMap() {
  onMap.view = null;
}

// Draws the Map under the page head (`head`, library.js): the lede, the tabs, the scope bar and
// the map, and the hint line. It returns what the top search found (map.js findIn), or null.
// `switched`: Map | List brought it, so it comes in as one piece instead of its entrance.
export function renderLibraryMap(main, { head, again = false, switched = false } = {}) {
  const lede = el("p", "lede", LEDE);
  const tabs = mapTabs();
  // The project goes by its folder name, as in the project picker.
  const scope = scopeBar(folderName(projectPath()));
  main.append(lede, tabs, scope);
  riseHead(head, lede, scope, { again });
  glidePill(tabs, tabs.querySelector('[aria-pressed="true"]'), "library-tabs-map");
  const answer = current("libraryMap");
  if (!answer) {
    main.append(currentError("libraryMap") ? banner("the library map", retry) : skeleton("card", 2));
    return null;
  }
  setHint(MAP_HINT);
  if (!again) onMap.view = null;
  const fresh = !onMap.view;
  // A new map opens with no plugin open and nothing selected: a real setup has no first plugin.
  if (fresh) Object.assign(onMap, { view: newMap(), open: new Set(), selected: null, pages: new Map() });
  const projectChanged = !fresh && onMap.project !== state.project;
  onMap.project = state.project;
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
  return onMap.found;
}

// The tree for a new answer: the open plugin and the selection stay while the answer has them.
function keepWhatShows(answer) {
  onMap.answer = answer;
  const ids = new Set(libraryTree(answer).blocks.map((block) => block.id));
  onMap.open = new Set([...onMap.open].filter((id) => ids.has(id)));
  onMap.model = libraryTree(answer, { open: onMap.open });
  if (onMap.selected && !onMap.model.blocks.some((block) => block.id === onMap.selected)) onMap.selected = null;
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
    onSelect: pressBlock,
    onEmpty: () => onMap.selected && letGo(),
    // While nothing is selected, pointing at a client lights what it loads.
    onHover: (id) => view.glance(id && id.startsWith("client:") ? litFrom(onMap.model, id) : null),
    enterDelay: afterOldPage(),
  });
  view.box.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && onMap.selected) letGo();
  });
  return view;
}

// Draw the map as it is now. A press that opened a plugin draws its selection first and lights
// its path once what it holds has come in.
function drawMap({ motion = "move", lightLater = false } = {}) {
  const { view, model, selected } = onMap;
  if (!view) return Promise.resolve();
  const layout = layoutTree(model, { open: onMap.open, pages: onMap.pages, narrow: false });
  const lit = litFor(model, selected);
  const later = lightLater && lit.size > 0;
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, lit: later ? new Set() : lit, found: onMap.found, open: onMap.open, motion });
  if (later) drawn.then(() => onMap.view === view && onMap.selected === selected && drawMap());
  return drawn;
}

// A press on a plugin card (map-view calls it before pressBlock): the selected open plugin folds;
// any other opens in place of the one open.
function openPlugin(id) {
  onMap.folded = onMap.selected === id && onMap.open.has(id);
  onMap.unfolds = !onMap.folded && !onMap.open.has(id);
  if (onMap.folded) onMap.open = new Set();
  else if (onMap.unfolds) onMap.open = new Set([id]);
  onMap.model = libraryTree(onMap.answer, { open: onMap.open });
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
  if (folded || (onMap.selected === id && !unfolds)) {
    letGo();
    return;
  }
  const block = onMap.model.blocks.find((b) => b.id === id);
  if (!block) return;
  onMap.selected = id;
  drawMap({ lightLater: unfolds });
  if (selectHook) selectHook(block);
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
