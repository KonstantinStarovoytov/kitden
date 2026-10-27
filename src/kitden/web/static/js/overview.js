// Overview, "Your setup, connected.": what needs attention and what can improve, one card each
// with one action, the notes folded under them, and the "Your setup" map beside them. A card's
// button only adds a row to the tray. The card leaves once that change is applied and checked
// and the page has read the result; an Undo brings it back.
import { getJson, query } from "./api.js";
import { previewButton, syncTrayIn } from "./details.js";
import { $, button, el, icon, joinWords, plural, reportError } from "./dom.js";
import { SETUP_NOTE } from "./gateway-details.js";
import { loadLibraryFor, noClients } from "./library.js";
import { layoutTree, litFrom } from "./map.js";
import { mapView } from "./map-view.js";
import { animateTo, countUp, D, rise, riseHead, rollTo } from "./motion.js";
import { toast } from "./panel.js";
import { banner, folderName, mark, setHint, skeleton, staleNote, versionWords } from "./parts.js";
import { current, currentError, data, go, goTo, libraryChoice, loadMap, parseSel, projectPath, retry, state } from "./store.js";
import { keyFor, onTray } from "./tray.js";

const TITLE = "Your setup, connected.";
const HINT = "Hover a card to see it on the map · a button adds a preview · click Kitden gateway or Library to open it";
const GROUPS = [
  { id: "attention", words: "Needs attention", icon: "triangle-alert", look: "btn primary" },
  { id: "improve", words: "Can improve", icon: "sparkles", look: "btn" },
];

// What the page drew last and what it waits for, across draws:
// - `shown`: each card drawn, by id: { card, node, list, group, at } (`at`, its place in its list);
// - `applied`: the cards whose tray row was applied, by id, with the time; the first read of the
//   page after that time decides whether each one leaves;
// - `leaving`: the cards on their way out, by id, as `shown` had them;
// - `gone`: the cards that left, so the draw that brings one back (an Undo) shows it coming;
// - `need`: the attention count the lede showed; `counted`: the lede counted up once;
// - `drew`: the last draw had the page's data;
// - `notesOpen`, and `notes`, the notes read last ({ project, groups });
// - `setup`: the "Your setup" map ({ view, model }).
const page = {
  shown: new Map(), applied: new Map(), leaving: new Map(), gone: new Set(), need: null, counted: false, drew: false,
  notesOpen: false, notes: null, setup: null,
};

export function renderOverview(main, { again = false } = {}) {
  const model = current("overview");
  const head = el("h1", null, TITLE);
  main.append(head);
  setHint(model ? HINT : "");
  if (!model) {
    page.drew = false;
    main.append(currentError("overview") ? banner("the overview", retry) : skeleton("card", 3));
    riseHead(head, null, null, { again });
    return;
  }
  // A new visit starts fresh; a draw again on the same visit (data, Apply, Undo) moves what changed.
  const fresh = !again || !page.drew;
  if (!again) {
    page.gone.clear();
    page.leaving.clear();
  }
  // No client found: what Kitden looks for comes first, and no lede promises anything.
  const none = Array.isArray(data.clients) && !data.clients.some((c) => c.status === "found");
  let lede = null;
  if (none) head.textContent = "No clients found";
  else {
    lede = ledeNode(model.counts, { count: !page.counted, from: again ? page.need : null });
    page.counted = true;
    page.need = model.counts.attention;
    main.append(lede);
  }
  const folder = folderName(projectPath());
  const scope = el("p", folder ? "scope-bar project" : "scope-bar");
  scope.append(icon(folder ? "folder" : "layers", 14), el("span", null, folder ? `Project ${folder}` : "All projects"));
  main.append(scope);
  riseHead(head, lede, scope, { again });
  if (currentError("overview")) main.append(staleNote(data.readAt.overview));

  const grid = el("div", "ov-grid");
  const left = el("div", "ov-main");
  const order = [];
  if (none) {
    const box = noClients({ overview: false });
    left.append(box);
    order.push(box);
  }
  const leaving = settleApplied(model);
  const shown = new Map();
  for (const group of GROUPS) {
    const section = groupNode(group, model.cards.filter((c) => c.group === group.id), leaving, shown, { fresh, order });
    left.append(section);
  }
  page.shown = shown;
  const notes = notesFold(model.notes);
  if (notes) {
    left.append(notes);
    order.push(notes.firstElementChild);
  }
  const right = setupColumn(model.map, fresh);
  grid.append(left, right);
  main.append(grid);
  page.drew = true;
  if (fresh) {
    rise(order, { delay: 160, step: 40 });
    rise([right], { delay: 200 });
  }
}

// The lede's words, with each number as { num, value }: "3 things need your attention. Everything
// else looks fine: 3 clients, 4 projects.", or "Everything looks fine: …" with nothing to fix.
export function ledeParts({ attention, clients, projects }) {
  const rest = [{ num: "clients", value: clients }, ` ${clients === 1 ? "client" : "clients"}, `, { num: "projects", value: projects }, ` ${projects === 1 ? "project" : "projects"}.`];
  if (!attention) return ["Everything looks fine: ", ...rest];
  return [{ num: "need", value: attention }, ` ${attention === 1 ? "thing needs" : "things need"} your attention. Everything else looks fine: `, ...rest];
}

export const ledeText = (counts) => ledeParts(counts).map((part) => (typeof part === "string" ? part : String(part.value))).join("");

// The lede. Its numbers count up on the first visit (700 ms OUT3, 200 / 260 / 320 ms late); on a
// later draw the attention count rolls from the one shown before (`from`), if it changed.
const COUNT_DELAYS = { need: 200, clients: 260, projects: 320 };
function ledeNode(counts, { count, from }) {
  const lede = el("p", "lede ov-lede");
  for (const part of ledeParts(counts)) {
    if (typeof part === "string") {
      lede.append(el("span", null, part));
      continue;
    }
    const holder = el("span", "num roll");
    const value = el("span", null, String(part.value));
    holder.append(value);
    lede.append(holder);
    if (count) countUp(value, part.value, { delay: COUNT_DELAYS[part.num] });
    else if (part.num === "need" && from && from !== part.value) {
      value.textContent = String(from);
      rollTo(holder, part.value);
    }
  }
  return lede;
}

// A group: its caption, then its cards. A card that leaves keeps its place in it until it has
// gone; a group with no card hides, caption and all.
function groupNode(group, cards, leaving, shown, { fresh, order }) {
  const section = el("section", "ov-group");
  section.dataset.group = group.id;
  const caption = el("h2", "ov-cap");
  caption.append(icon(group.icon, 13), el("span", null, group.words));
  const list = el("div", "ov-cards");
  section.append(caption, list);
  const nodes = cards.map((card) => {
    const node = cardNode(card, group);
    shown.set(card.id, { card, node, list, group: section, at: 0 });
    if (!fresh && page.gone.delete(card.id)) comeBack(node);
    return node;
  });
  for (const [id, was] of leaving) {
    if (was.group.dataset.group !== group.id) continue;
    nodes.splice(Math.min(was.at, nodes.length), 0, was.node);
    Object.assign(was, { list, group: section });
    page.leaving.set(id, was);
  }
  list.append(...nodes);
  nodes.forEach((node, at) => {
    const mine = shown.get(node.dataset.card);
    if (mine && mine.node === node) mine.at = at;
  });
  section.hidden = !nodes.length;
  if (nodes.length) order.push(caption, ...nodes);
  return section;
}

// One card: its icon tile (a client's mark for a client), its name with one line under it, the
// clients it is about and one button. Pointing at it, or keyboard focus in it, shows its path on
// the map; leaving lets go.
function cardNode(card, group) {
  const node = el("article", "ov-card");
  node.dataset.card = card.id;
  let tile;
  if (card.icon && card.icon.client) tile = mark(card.icon.client);
  else {
    tile = el("span", "itile");
    tile.append(icon(card.icon, 15));
  }
  const words = el("span", "tx");
  words.append(el("span", "nm", card.name), el("span", "ln", card.line));
  const who = el("span", "who");
  for (const client of card.clients) who.append(mark(client));
  node.append(tile, words, who);
  const action = actionButton(card, group.look);
  if (action) node.append(action);
  node.addEventListener("pointerenter", () => focusSetup(card.focus));
  node.addEventListener("pointerleave", () => focusSetup(null));
  node.addEventListener("focusin", () => focusSetup(card.focus));
  node.addEventListener("focusout", (event) => {
    if (!node.contains(event.relatedTarget)) focusSetup(null);
  });
  return node;
}

// A change for the tray ("Move in…", "Connect…", "Update…": the button says "In preview" while it
// waits there), or a page to open ("Keep one…", "Show…").
function actionButton({ id, action }, look) {
  if (!action) return null;
  const node = action.body
    ? previewButton(action.label, action.body, { note: action.body.action.startsWith("setup_server.") ? SETUP_NOTE : null, look })
    : button(action.label, () => openPlace(action.go), look);
  node.dataset.focus = `card:${id}`;
  return node;
}

// Keep one… opens the item; Show… the Gateway's List at the outside group.
async function openPlace({ view, sel, mode }) {
  const selected = parseSel(sel);
  if (view === "library" && selected) await follow({ view: "map", ...selected });
  else if (selected) await goTo(view, selected, mode ? { mode } : {});
  else go(view, mode ? { mode } : {});
}

// The item a card or note is about, for the address: its kind and name. Null for a place.
// The server still names the Load map ("map"); its rows are the Library's "Installed".
export function targetSel(target) {
  return target.view === "map" ? { kind: target.kind, name: target.name } : null;
}

// An item opens selected in the Library, which opens its Details. The tab is read first, so the
// Library draws its rows inside the place change.
async function follow(target) {
  const sel = targetSel(target);
  if (sel) {
    await loadLibraryFor(libraryChoice(sel));
    goTo("library", sel);
  } else {
    go(target.view);
  }
}

// The tray tells the page: every card button shows whether its row waits there, and once a change
// is applied and checked, the cards whose rows it held wait for the page's next read.
onTray((t) => {
  if (typeof document === "undefined" || state.view !== "overview") return;
  syncTrayIn($("#main"));
  if (t.phase !== "applied") return;
  const keys = new Set(t.rows.map((row) => row.key));
  const at = Date.now();
  for (const [id, { card }] of page.shown) {
    if (card.action && card.action.body && keys.has(keyFor(card.action.body))) page.applied.set(id, at);
  }
});

// The cards that leave now, by id: those whose change was applied and that the page's read after it
// no longer has. A card it still has stays. A card that comes back while it still leaves stops
// leaving at once.
function settleApplied(model) {
  const now = new Set(model.cards.map((c) => c.id));
  const read = data.readAt.overview || 0;
  for (const [id, at] of page.applied) {
    if (read < at) continue;
    page.applied.delete(id);
    const was = page.shown.get(id);
    if (now.has(id) || !was || page.leaving.has(id)) continue;
    page.leaving.set(id, was);
    leave(id, was).catch(reportError);
  }
  for (const [id, was] of page.leaving) {
    if (!now.has(id)) continue;
    page.leaving.delete(id);
    was.node.remove();
  }
  return new Map(page.leaving);
}

// A card leaves: out to the right (opacity, x 28) in 180 ms ease-in, then it folds to nothing
// (height, padding, border, and the gap under it) in 160 ms CALM, and is removed. The cards under
// it move up with the fold; nothing slides after it. Under reduced motion it goes at once.
async function leave(id, was) {
  const { node } = was;
  // Its button follows the tray no more, and a draw meanwhile gives focus back to another one.
  for (const control of node.querySelectorAll("[data-tray]")) delete control.dataset.tray;
  for (const control of node.querySelectorAll("[data-focus]")) delete control.dataset.focus;
  node.classList.add("leaving");
  node.setAttribute("aria-hidden", "true");
  page.gone.add(id);
  await byTime(animateTo(node, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateX(28px)" }], { dur: 180, ease: "ease-in", fill: "forwards" }), 180);
  if (page.leaving.get(id) !== was) return;
  if (D(1)) {
    const style = getComputedStyle(node);
    const from = { height: `${node.offsetHeight}px`, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, borderTopWidth: style.borderTopWidth, borderBottomWidth: style.borderBottomWidth, marginBottom: "0px" };
    const to = { height: "0px", paddingTop: "0px", paddingBottom: "0px", borderTopWidth: "0px", borderBottomWidth: "0px", marginBottom: "-8px" };
    await byTime(animateTo(node, [from, to], { dur: 160, fill: "forwards" }), 160);
    if (page.leaving.get(id) !== was) return;
  }
  page.leaving.delete(id);
  if (node.contains(document.activeElement)) focusNext(was);
  node.remove();
  if (!was.list.children.length) was.group.hidden = true;
}

// A motion's end, or its time, whichever comes first: a hidden tab may never end an animation.
function byTime(motion, ms) {
  return Promise.race([motion, new Promise((done) => setTimeout(done, D(ms) + 50))]);
}

// Focus on a card that leaves goes to the next card's button, else the one before.
function focusNext({ node, list }) {
  const cards = [...list.children];
  const at = cards.indexOf(node);
  const next = cards[at + 1] || cards[at - 1];
  const control = next ? next.querySelector("button") : null;
  if (control) control.focus({ preventScroll: true });
}

// An Undo brought the card back: it comes in from 8 px above at .98 of its size, 220 ms CALM.
function comeBack(node) {
  animateTo(node, [{ opacity: 0, transform: "translateY(-8px) scale(0.98)" }, { opacity: 1, transform: "none" }], { dur: 220 });
}

// The notes ---------------------------------------------------------------------------------

// A note as part of a sentence: "<name> <words>."; the full explanation, with its paths, is in
// the item's panel.
const NOTE_WORDS = {
  cross_loaded: "loads from another client",
  same_in_other_clients: "is set up in more than one client",
  same_name_other_source: "has the same name as an entry from another source",
  scope_override: "has one definition that replaces another",
  unknown_state: "has an on/off state Kitden cannot read",
  bypasses_gateway: "is not connected to the gateway",
};

const notesWords = (count, open) => (open ? `Hide ${plural(count, "note", "notes")}` : `Show ${plural(count, "note", "notes")} (nothing to fix)`);

// The fold under the cards: "Show 3 notes (nothing to fix)", or none at 0 notes. It opens in
// 280 ms CALM and its notes rise 40 ms apart; it closes in 220 ms ease-in.
let notesTurn = 0;
function notesFold(count) {
  if (!count) return null;
  const box = el("div", "ov-notes-fold");
  const toggle = el("button", "ov-fold");
  toggle.type = "button";
  toggle.dataset.focus = "notes";
  const label = el("span", null, notesWords(count, page.notesOpen));
  toggle.append(icon("chevron-right", 14), label);
  toggle.setAttribute("aria-expanded", String(page.notesOpen));
  const list = el("div", "ov-notes");
  list.hidden = !page.notesOpen;
  if (page.notesOpen) fillNotes(list, false);
  toggle.addEventListener("click", () => {
    page.notesOpen = !page.notesOpen;
    label.textContent = notesWords(count, page.notesOpen);
    toggle.setAttribute("aria-expanded", String(page.notesOpen));
    (page.notesOpen ? openNotes(list) : closeNotes(list)).catch(reportError);
  });
  box.append(toggle, list);
  return box;
}

async function openNotes(list) {
  notesTurn += 1;
  for (const old of list.getAnimations ? list.getAnimations() : []) old.cancel();
  list.hidden = false;
  fillNotes(list, true);
  await animateTo(list, [{ height: "0px", opacity: 0 }, { height: `${list.scrollHeight || 0}px`, opacity: 1 }], { dur: 280 });
}

async function closeNotes(list) {
  const turn = ++notesTurn;
  await byTime(animateTo(list, [{ height: `${list.offsetHeight || 0}px`, opacity: 1 }, { height: "0px", opacity: 0 }], { dur: 220, ease: "ease-in", fill: "forwards" }), 220);
  if (turn !== notesTurn) return;
  list.hidden = true;
  for (const old of list.getAnimations ? list.getAnimations() : []) old.cancel();
}

// The notes of the picked project, from /api/findings: the ones read last show at once, then the
// new read replaces them if they changed. Opened by a press (`lift`), they rise in 40 ms apart.
function fillNotes(list, lift) {
  const project = projectPath();
  const had = page.notes && page.notes.project === project ? page.notes.groups : null;
  const draw = (groups, delay) => {
    list.replaceChildren(...groups.map(noteNode));
    if (lift) rise([...list.children], { delay, step: 40 });
  };
  if (had) draw(had, 280);
  else list.replaceChildren(el("p", "muted", "Loading…"));
  getJson(`/api/findings${query({ project })}`).then((findings) => {
    const groups = noteGroups(findings.filter((x) => x.severity === "info"));
    page.notes = { project, groups };
    if (had && JSON.stringify(had.map(noteSentence)) === JSON.stringify(groups.map(noteSentence))) return;
    list.replaceChildren(...groups.map(noteNode));
    if (lift && !had) rise([...list.children], { step: 40 });
  }).catch(() => {
    if (!had) list.replaceChildren(el("p", "muted", "Could not load the notes."));
  });
}

// The notes by item: one group per name, in the order first seen. A note about several names
// (unknown on/off state) joins each name's group. A group has the clients of all its notes, the
// distinct note words, and its first note for opening its item.
export function noteGroups(findings) {
  const groups = new Map();
  for (const finding of findings) {
    const words = NOTE_WORDS[finding.type] || `has a note: ${finding.type.replaceAll("_", " ")}`;
    for (const name of new Set(finding.names)) {
      if (!groups.has(name)) groups.set(name, { name, clients: [], notes: [], first: finding });
      const group = groups.get(name);
      for (const client of finding.clients || []) if (!group.clients.includes(client)) group.clients.push(client);
      if (!group.notes.includes(words)) group.notes.push(words);
    }
  }
  return [...groups.values()];
}

// "docs has the same name as an entry from another source and is not connected to the gateway."
export function noteSentence(group) {
  return `${group.name} ${joinWords(group.notes)}.`;
}

// A note is one sentence with the info icon; a press opens its item.
function noteNode(group) {
  const node = el("button", "ov-note");
  node.type = "button";
  node.append(icon("info", 13), el("span", null, noteSentence(group)));
  node.addEventListener("click", () => showNote(group).catch(reportError));
  return node;
}

// The Library row a note names: the row that holds one of its note's items of that name. A note
// about several names (unknown on/off state) opens each name's own row.
export function noteItemRow(group, rows) {
  const { items, names } = group.first;
  const mine = items.filter((_, i) => names[i] === group.name);
  return rows.find((r) => Object.values(r.cells).some((cell) => (cell.items || []).some((id) => mine.includes(id)))) || null;
}

// The note is about an item on this computer: select it and open it in the Library.
async function showNote(group) {
  if (!current("map")) await loadMap();
  const map = current("map");
  const row = noteItemRow(group, (map && map.rows) || []);
  if (row) await follow({ view: "map", kind: row.kind, name: row.lookup });
  else toast("Could not find this item in the Library.");
}

// The "Your setup" map -------------------------------------------------------------------------

// Clients at x 0 (160 x 54, from y 22, 18 apart); the Kitden gateway at x 250, y 40 and the
// Library at y 148 (220 x 60).
const SETUP_COLUMNS = [
  { id: "clients", w: 160, h: 54, top: 22, rowGap: 18 },
  { id: "pages", w: 220, h: 60, colGap: 90, top: 40, rowGap: 48 },
];

// The map's tree from the Overview's `map`: a block per client with its version, the Kitden
// gateway and the Library with their counts, and a link from each client to what it reaches.
export function setupTree(map, progress) {
  const blocks = map.clients.map((c) => ({
    id: `client:${c.id}`, column: "clients", kind: "client", name: c.name, meta: c.on ? versionWords(c.version, progress, true) : "Not found",
    lamp: c.on ? "on" : "off", state: c.on ? "on" : "off", stateInMeta: true, client: c.id, ports: { right: true },
  }));
  const { gateway, library } = map;
  blocks.push(pageBlock("gateway", "Kitden gateway", "house", `${plural(gateway.servers, "server", "servers")} · ${plural(gateway.tools, "tool", "tools")}`, gateway.servers > 0));
  blocks.push(pageBlock("library", "Library", "library", `${plural(library.plugins, "plugin", "plugins")} · ${plural(library.skills, "skill", "skills")}`, library.plugins + library.skills > 0));
  const links = map.links.map((link) => ({ from: `client:${link.client}`, to: link.to, kind: "on" }));
  return { columns: SETUP_COLUMNS, blocks, links };
}

// A block that opens its page: its icon tile, its counts, and the arrow mark at its right.
function pageBlock(id, name, mark, meta, on) {
  return { id, column: "pages", kind: "page", name, meta, lamp: on ? "on" : "off", state: on ? "on" : "off", stateInMeta: true, icon: mark, label: { icon: "arrow-up-right", words: "" }, ports: { left: true } };
}

// What a card focuses on the map: its clients, its block, and the links between them that exist.
export function setupPath(model, { clients, block }) {
  const lit = new Set();
  for (const client of clients) {
    const id = `client:${client}`;
    if (!model.blocks.some((b) => b.id === id)) continue;
    lit.add(id);
    if (block && model.links.some((l) => l.from === id && l.to === block)) lit.add(`${id}>${block}`);
  }
  if (block) lit.add(block);
  return lit;
}

function setupTile(block) {
  if (block.kind === "client") return mark(block.client);
  const holder = el("span", "block-icon");
  holder.append(icon(block.icon, 15));
  return holder;
}

// The Kitden gateway and the Library open their pages; a client focuses its links (until the
// pointer next enters and leaves a card). Blocks are buttons, so Enter and Space do the same.
function pressSetup(id) {
  if (id === "gateway" || id === "library") go(id);
  else if (page.setup) page.setup.view.glance(litFrom(page.setup.model, id));
}

function focusSetup(focus) {
  const setup = page.setup;
  if (!setup || !setup.view.box.isConnected) return;
  setup.view.glance(focus ? setupPath(setup.model, focus) : null);
}

// The right column: "Your setup", the map (one map for the visit: a draw again moves what changed)
// and the foot.
function setupColumn(map, fresh) {
  const column = el("section", "ov-setup");
  const caption = el("h2", "ov-cap", "Your setup");
  const box = drawSetup(map, { fresh });
  const foot = el("p", "ov-foot");
  foot.append(icon("folder", 13), el("span", null, footWords(map.projects, map.own_rules)));
  column.append(caption, box, foot);
  return column;
}

function drawSetup(map, { fresh }) {
  if (fresh || !page.setup) page.setup = { view: mapView({ tile: setupTile, onSelect: pressSetup }), model: null };
  const model = setupTree(map, data.progress);
  page.setup.model = model;
  page.setup.view.draw(model, layoutTree(model, { narrow: false }), { motion: fresh ? "none" : "move" }).catch(reportError);
  return page.setup.view.box;
}

// "4 projects · 1 has its own rules".
export function footWords(projects, own) {
  return `${plural(projects, "project", "projects")} · ${own} ${own === 1 ? "has its own rules" : "have their own rules"}`;
}

// The clients' versions came in the background: the map's client blocks take them in place.
globalThis.document?.addEventListener("kitden:versions", async () => {
  let clients;
  try { clients = await getJson("/api/clients"); } catch { return; }
  data.clients = clients;
  const model = current("overview");
  if (!model) return;
  for (const shown of model.map.clients) {
    const read = clients.find((c) => c.id === shown.id);
    if (read) Object.assign(shown, { version: read.version, tested: read.version_supported });
  }
  if (state.view === "overview" && page.setup && page.setup.view.box.isConnected) drawSetup(model.map, { fresh: false });
});
