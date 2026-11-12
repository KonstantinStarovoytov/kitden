// Gateway: the clients, the gateways and the MCP servers they reach, as a Map or a List. Each
// row opens its Details beside the page (gateway-details.js).
import { $, button, byKeys, el, focusTreeRow, gridCell, gridKeys, icon, joinWords, pageWaits, plural, reportError, treeRow, withFocusKey } from "./dom.js";
import { setCancelFocus } from "./dock.js";
import { addKind, addName, onOpenAdd, openAdd, pageRead, wasAdded } from "./gateway-add.js";
import { addForm, connectAction, connectBody, followProject, heldServer, liveHeld, movesTo, NOT_REACHED, OUTSIDE_ICONS, removalIcon, ruleBody, SERVER_ICONS, SETUP_NOTE, showClient, showGateway, showHeld, showLink, showOutside, showTool } from "./gateway-details.js";
import { movingOn, placeMoved, pressGrip } from "./gateway-drag.js";
import { clearPick, keepPickable, pick, PICK_HINT, pressBand, togglePick } from "./gateway-pick.js";
import { flipToolPick, onToolPick, pickTools, setToolPick, toolPick } from "./tools.js";
import { collapseGroup, findIn, foldable, groupOfStack, groupsWith, isNarrow, keepFolded, keepOpen, landOwners, landStage, layoutTree, linkKey, litFor, litFrom, litPath, newBlocks, pagesNow, pagesWith, pressCount, pressOpen, pressStack, shownFound, toggleOpen, turnWords, wideWidth } from "./map.js";
import { addHeadButton, headActions, drawChip, glidePill, modeSwitch, switchedNow } from "./map-page.js";
import { mapView } from "./map-view.js";
import { afterOldPage, D, rise, riseHead } from "./motion.js";
import { closePanel, isPanelOpen, moveInto, openInfo, panelState, projectLabel, review } from "./panel.js";
import { banner, CLIENT_NAMES, folderName, gatewayName, kitdenClients, kitdenHouse, mark, opens, ORIGIN_WORDS, scopeBar, setHint, skeleton, STATE_WORDS, staleNote, WRITABLE } from "./parts.js";
import { arrival, busy, current, currentError, data, gatewayShows, onBusy, projectPath, render, retry, setState, state, takeArrival, toolSel, viewMode } from "./store.js";
import { say } from "./toast.js";
import { openAccess } from "./access-form.js";
import { inTray, keyFor, linksWait, onTray, TAKE_OUT, takeOut, toggleInTray, tray, trayRow, undone, writing } from "./tray.js";

// The group of servers outside the gateway: the List's words, and the map's, which asks for a drag.
const OUTSIDE = "Outside the gateway · calls skip Kitden's rules";
const OUTSIDE_MAP = "Outside the gateway · drag one in";
// ... and while the group pages, before which ones show ("Outside the gateway · 6–10 of 12").
const OUTSIDE_PAGED = "Outside the gateway";
// On the map these words take one line, wider than their column, and an outside server's block is
// 50 high.
const OUTSIDE_H = 16;
const OUTSIDE_BLOCK_H = 50;
// The groups of servers outside the gateway in /api/gateway-view, in the order the page lists them.
// A server's icon on the map is the one its panel shows (SERVER_ICONS, OUTSIDE_ICONS).
const OUTSIDE_GROUPS = ["move", "local", "plugin"];
// The card at the end of the gateway's groups that opens the add panel: a place, so no lamp,
// ports or links.
const ADD_CARD = { id: "addslot:servers", column: "servers", kind: "addslot", name: "Add a server", meta: "From the catalog", icon: "plus", h: OUTSIDE_BLOCK_H };
// What a block in preview says under the pointer: a press takes its row out of the tray (D12).
const IN_PREVIEW = "In preview. Click to take it out.";
// A server the Add panel adds grows out of the gateway in this long, and shrinks back into it; the
// blocks below make room as long (add-notes §3).
const ADD_GROW_MS = 260;
// A gateway's own groups, each with the icon of its caption.
const KINDS = [["remote", "Remote", "cloud"], ["local", "Local", "hard-drive"]];
// A gateway's block, or on a first run the slot of the Kitden gateway.
const GATEWAY_KINDS = ["gateway", "slot"];
// What the tray puts in a gateway's group on the map: the List shows none of it.
const ON_MAP_ONLY = ["preview", "slot"];
// What a client or an outside server says when Kitden does not know its state.
const NOT_KNOWN = "Not known";
// A tool's row says "Read" or "Write" only when the server says so; a guess from its name says
// "May write".
const HINT_TAGS = { reads: "Read", writes: "Write", "may write": "May write" };

// The hint line under the dock on the map (gateway-notes 8); the List has none.
const MAP_HINT = "Point at a link and press × to remove it · click anything for its Details · several changes wait in preview, then Apply all · drag a server onto a client · ⌘ or Ctrl-click tools in Details to pick several";

// What an arrival with a selection (Back, Forward or a link) opens, once: a server the Kitden
// gateway holds (`held`, and `tool` for one of its tools), a server outside it by its name (its
// row, `outside`, and its `group`; `direct:` skips a held server of that name), a client or a List
// group. Null for anything else (it stays in
// the address for the next page), and while a panel is open, so it never replaces what the person
// opened. Everything is found in the Gateway's own model: the Library's /api/map is never read.
export async function arrivalServer(view) {
  const selected = takeArrival();
  if (!selected || isPanelOpen()) return null;
  if (selected.kind === "mcp_server" || selected.kind === "direct") {
    const held = selected.kind === "mcp_server" && heldServer(view, selected);
    if (held) return { held };
    for (const group of OUTSIDE_GROUPS) {
      const row = (view.groups[group] || []).find((r) => r.name === selected.name);
      if (row) return { outside: row, group };
    }
    return null;
  }
  if (selected.kind === "tool") {
    const named = toolSel(selected.name);
    const held = named && heldServer(view, { kind: "mcp_server", name: named.server });
    return held ? { held, tool: named.tool } : null;
  }
  if (selected.kind === "client") return WRITABLE.includes(selected.name) ? { client: selected.name } : null;
  if (selected.kind === "group") return { group: selected.name };
  return null;
}

// How many blocks the Servers column holds: the Kitden gateway's servers and every row outside it.
export function serverCount(view) {
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  const outside = OUTSIDE_GROUPS.reduce((n, key) => n + (view.groups[key] || []).length, 0);
  return ((kitden && kitden.servers) || []).length + outside;
}

// Draws the page. It returns what the top search found on it (map.js findIn), or null with no
// search or no page to search: app.js shows the chip. The map keeps its blocks while the page
// draws `again`; a new visit, or the List, starts a new one. A new visit also lifts the head
// (title, lede, scope line), and then the map or List; a draw soon after goes on lifting it
// (riseHead). The skeleton, the error banner and "No gateway yet" rise as they come (riseUnder).
export function renderGateway(main, { again = false } = {}) {
  // A draw the view switch asked for: the view it draws comes in as one piece (below).
  const switched = switchedNow();
  if (!again) onMap.view = null;
  const head = el("div", "page-head");
  head.append(el("h1", null, "Gateway"));
  const lede = el("p", "lede", "Connect your agents. Shape what they can use.");
  main.append(head, lede);
  const view = current("gateway");
  if (!view) {
    riseHead(head, lede, null, { again });
    const failed = Boolean(currentError("gateway"));
    const under = failed ? banner("the gateway", retry) : skeleton("card", 2);
    main.append(under);
    riseUnder(failed ? "banner" : "skeleton", under, again);
    return;
  }
  // An open Add panel follows what Kitden read (gateway-add.js).
  pageRead(view).catch(reportError);
  // Under the head: what the page shows, the shared setup or a project's rules that differ from it.
  const scope = scopeBar(folderName(projectPath()), view.own_rules);
  main.append(scope);
  riseHead(head, lede, scope, { again });
  switchInPlace(again, scope);
  if (currentError("gateway")) main.append(staleNote(data.readAt.gateway));
  // Only without any gateway, the Kitden one included (no home folder to change).
  if (!view.gateways.length) {
    const card = noGateway();
    main.append(card);
    riseUnder("empty", card, again);
    return;
  }
  shownUnder = null;
  const mode = viewMode(state, serverCount(view));
  gatewayShows.mode = mode;
  const seg = modeSwitch("gateway", mode, { old: () => (mode === "map" ? onMap.view && onMap.view.box : onList.box), letGo: letGoIfSelected, shows: () => gatewayShows.mode });
  head.append(headActions(addHeadButton("+ Add servers", "add:servers", (node) => openAdd({ from: node })), seg));
  const model = treeFor(view, mode);
  setHint(mode === "map" ? mapHint() : "", mode === "map" ? hintActs() : []);
  // The search finds here: matches light up, the rest dims, and what hides a match opens (S.6).
  // It changes nothing in a client and moves no Details.
  const found = state.q.trim() ? findIn(model, state.q) : null;
  if (mode === "map") gatewayMap(main, model, found, { switched });
  else {
    onMap.view = null;
    gatewayList(main, view, model, found, { enter: !again });
  }
  if (switched) rise([mode === "map" ? onMap.view.box : onList.box], { delay: afterOldPage() });
  glidePill(seg, seg.querySelector('[aria-pressed="true"]'), "gateway-view");
  // A performance mark for the map probe (Part 4.1): the first time the page draws with data.
  if (!performance.getEntriesByName("kitden:gateway-drawn").length) performance.mark("kitden:gateway-drawn");
  openArrival(view, model, mode).catch(reportError);
  return mode === "map" ? shownFound(found, onMap.layout) : found;
}

// The project the page was drawn for last. A draw for another one on the same visit is a project
// switch in place (gateway-notes 7.4): the scope line rises with its new words (4 px, 320 ms CALM)
// and open Details follow the project (gateway-details.js followProject; an address's selection
// never opens over them). The map and the List change in place as they draw.
let drawnFor = null;
function switchInPlace(again, scope) {
  const switched = again && drawnFor !== null && drawnFor !== state.project;
  drawnFor = state.project;
  if (!switched) return;
  rise([scope], { y: 4, dur: 320 });
  followProject().catch(reportError);
}

// The Gateway as one tree, as the page shows it now: what Kitden read and the picked project, and
// on the map (`mode`) the tray's rows and a drag. The List shows what is set up, so its search
// finds only that.
function treeFor(view, mode = "map") {
  const onMapOnly = mode === "map" ? { rows: rowsOnMap(tray).map(withKind), ...movingOn(), addCard: true } : {};
  return growBack(gatewayTree(view, { setup: data.setupServer, clients: data.clients, held: liveHeld(view), picked: state.project, ...onMapOnly }));
}

// A row that adds a marketplace server, with its kind ("remote" or "local"), which the Add panel
// read: the map puts its preview in that group. Any other row as it is.
function withKind(row) {
  return row.body.action === "gateway.add" ? { ...row, kind: addKind(row.body.params.server) } : row;
}

// A server an Apply added from a marketplace since the page loaded shrinks back into the gateway
// when an Undo takes it out, as its preview did (ADD_GROW_MS).
function growBack(model) {
  for (const block of model.blocks) {
    if (block.kind === "held" && block.gateway.kind === "kitden" && wasAdded(block.name)) Object.assign(block, { growsFrom: `gateway:${block.gateway.id}`, growMs: ADD_GROW_MS });
  }
  return model;
}

// The tray rows the map draws: none once their change is applied, as the page then reads the result
// and shows the servers as they are. A row with no part yet is drawn only while it is asked: after
// a refused preview it has none, and nothing is asked for it.
export function rowsOnMap(t) {
  if (t.phase === "applied") return [];
  return t.phase === "asking" ? t.rows : t.rows.filter((row) => row.part || row.waits);
}

// How a preview block looks when its server waits for access (tray.js `waits`): the amber lamp,
// what it needs, and a press that opens the access panel (pressBlock); once a token works, the
// green lamp says so. Else nothing changes.
function accessLook(row) {
  if (row.waits) {
    const signIn = row.waits.kind === "sign-in";
    const title = signIn ? "Needs sign-in. Click to add a token instead." : "Needs a token. Click to add it.";
    return { needs: true, lamp: "warn", meta: signIn ? "Needs sign-in" : "Needs token", state: "needs", takeOut: null, title };
  }
  return row.works ? { lamp: "on", meta: "Token works" } : {};
}

function noGateway() {
  const card = el("section", "card");
  card.append(el("h2", null, "No gateway yet"));
  card.append(el("p", "muted", "A gateway keeps your MCP servers in one place: each client needs one entry, and you turn tools on or off once."));
  card.append(addForm());
  return card;
}

// What the page showed under its head on its last draw, while it has no map or List: "skeleton",
// "banner" or "empty" ("No gateway yet"). One that comes on this draw rises as the map or List
// would on a first visit (6 px, 260 ms CALM); drawn again, it stays still.
let shownUnder = null;
function riseUnder(kind, node, again) {
  const comes = !again || shownUnder !== kind;
  shownUnder = kind;
  if (comes) rise([node], { delay: afterOldPage() });
}

// The Gateway's map columns: clients, the gateway, servers, tools, each with its blocks' size,
// wide and narrow, and (wide) the space before it, the y of its first block and the space between
// its blocks (map.js). The numbers are the mockup's: columns at x 0, 196, 396 and 636, 836 wide.
// The mockup has no narrow map: narrow keeps its old sizes, the gateway a small tile and tools
// rows inside their server, 190 wide.
export const GATEWAY_COLUMNS = [
  { id: "clients", caption: "Clients", w: 150, h: 54, top: 124, rowGap: 18, narrowW: 140 },
  { id: "gateway", caption: "Gateway", w: 150, h: 124, colGap: 46, top: 124, rowGap: 18, narrowW: 56, narrowH: 56 },
  { id: "servers", caption: "Servers", w: 170, h: 60, colGap: 50, top: 58, rowGap: 10, narrowW: 220, narrowH: 54 },
  { id: "tools", caption: "Tools", w: 200, h: 34, colGap: 70, narrowW: 190, narrowH: 30 },
];

// The registered gateways, the one the clients use first.
function usedFirst(model, gateways) {
  return [...gateways].sort((a, b) => Number(model.used.includes(b.id)) - Number(model.used.includes(a.id)));
}

// What a server the Gateway lists is, in one word. MetaMCP says SSE or STREAMABLE_HTTP; Obot says
// how it runs the server: a remote address, or a program Obot hosts (uvx, npx, containerized).
function heldKind(server) {
  if (server.type === "SSE") return "SSE";
  if (!server.type || server.type === "STREAMABLE_HTTP" || server.type === "remote") return "Remote";
  return "Hosted";
}

// A held server's tag in a project view: "Only this project" when this project's own rule turns
// it on and no other known project has it on (`on_elsewhere`), "This project" for any other rule
// of its own.
function heldTag(server, on) {
  if (server.origin !== "project") return null;
  return on && server.differs && !server.on_elsewhere ? ORIGIN_WORDS.project : ORIGIN_WORDS.override;
}

// The Gateway as one tree for the map (map.js) and the List, from `view` (the /api/gateway-view
// answer) and `setup` (/api/setup-server):
// - the three clients, each joined to the Kitden gateway while its kitden entry is on;
// - the Kitden gateway, then each registered gateway (the used one first), joined to each client
//   it connects, with its servers in Remote and Local groups, joined to it unless off. A
//   registered gateway's servers come from the live read (`held`, gateway id -> its answer),
//   without tools;
// - the tools of every server the Kitden gateway holds, from its tool list, joined to it while
//   on (layoutTree shows them only for an open server);
// - the servers outside every gateway, each joined to each client that has it by a direct line,
//   with a grip where a move can take it, and in a project "This project" where the project's
//   own definition replaces the shared one. One that no client is known to load (`unknown`) is
//   "unk", and its lines are dashed (`unk`): they show who has the entry, not that it is on.
// On a first run (no client has the kitden entry, on or off, and the Kitden gateway holds nothing)
// the clients say they are found, with their version (`clients`, /api/clients), the gateway is a
// slot to set up, and nothing has a grip. `picked` is the picked project ("" for All projects).
// `rows` are the tray's rows (tray.js, as rowsOnMap gives them). A move into the Kitden gateway
// puts a preview block `preview:<name>` at the end of its group once its row has its part, joined
// to the gateway by a preview link and to its clients by their dotted lines: the server is drawn
// once, there, and the Outside list closes up (Task 4.7). While its row is asked the slot "Drop to
// add" shows there instead and the outside block stays, with no grip. A server taken out of the
// Kitden gateway, or a
// tool turned off in the scope shown, has its link drawn leaving. A client the tray connects gets
// a preview link to the Kitden gateway, one it disconnects has its link drawn leaving; a server
// moved out of the gateway shows outside (outsideParts), and a client's own entry removed has its
// line drawn leaving. Each block and link a row draws names it (`row`, its key); rows are drawn
// once they have their part. While a server is dragged (`drop`, `{ name, kind }`, kind "remote"
// or "local") the slot opens in that group too.
export function gatewayTree(view, { setup, clients = [], held = new Map(), picked = "", rows = [], drop = null, addCard = false } = {}) {
  const { linked, off, known, setup: offers } = kitdenClients(setup);
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  const first = known && !linked.length && !off.length && Boolean(kitden) && !kitden.problem && !(kitden.servers || []).length;
  const blocks = [];
  const links = [];
  // What the moves put in the groups of the Kitden gateway, and the outside rows they take.
  const { adds, moved } = movesIn(view, kitden, rows, drop);
  const waits = connectRows(rows, setup);
  const out = movesOut(rows);
  for (const id of WRITABLE) blocks.push(clientBlock(id, { setup, linked, known, first, clients, wait: waits.get(id) }));
  // A gateway block joined to the clients it `reaches` (null when not read), then its `servers` in
  // their groups (`kindOf` says which), but those that show elsewhere (`away`, by name); it counts
  // only those not in preview (gateway-notes 4.1), so a server moving out is not counted.
  // `server(block, word)` adds what each server's block says. `unread` says why Kitden does not
  // know what it holds, so no count shows: a problem is not an empty gateway. `ends` are blocks
  // for the end of a group (each `{ kind, block }`), which open that group if need be.
  // A gateway block speaks no state word: it says where it runs and its clients and servers, or
  // what Kitden could not read, and then its state is not known.
  const addGateway = (gateway, { reaches, servers, kindOf, server, unread = null, ends = [], away = new Map() }) => {
    const id = `gateway:${gateway.id}`;
    blocks.push({ id, column: "gateway", kind: "gateway", name: gatewayName(gateway), ...gatewayFace(gateway, reaches, servers.filter((s) => !away.has(s.name)), unread), state: unread ? "unk" : "on", stateInMeta: true, gateway, unread, ports: { left: true, right: true } });
    for (const client of reaches || []) links.push({ from: `client:${client}`, to: id, kind: "on" });
    for (const [kind, word, mark] of KINDS) {
      const mine = servers.filter((s) => kindOf(s) === kind && !away.has(s.name));
      const last = ends.filter((end) => end.kind === kind).map((end) => end.block);
      if (!mine.length && !last.length) continue;
      const group = `group:${gateway.id}:${kind}`;
      blocks.push({ id: group, column: "servers", kind: "group", name: word, icon: mark, before: 3, under: id, folds: true });
      for (const each of mine) {
        const block = { id: `held:${gateway.id}:${each.name}`, column: "servers", parent: group, kind: "held", name: each.name, state: "on", lamp: "on", icon: SERVER_ICONS[kind], ports: { left: true }, server: each, gateway };
        server(block, word);
        blocks.push(block);
        if (block.state === "on") links.push({ from: id, to: block.id, kind: "on" });
      }
      for (const end of last) {
        blocks.push({ ...end, parent: group });
        links.push({ from: id, to: end.id, kind: "preview", ...(end.row ? { row: end.row } : {}) });
      }
    }
  };
  const tools = [];
  if (kitden && first) {
    // One review sets up every client that has no kitden entry yet.
    const targets = offers.filter((o) => o.body.action === "setup_server.register").map((o) => ({ client: o.client }));
    const action = targets.length ? { action: "Set up…", setup: { action: "setup_server.register", targets, params: {} } } : {};
    blocks.push({ id: `gateway:${kitden.id}`, column: "gateway", kind: "slot", name: "No gateway yet", meta: "One place for servers, rules and logins.", gateway: kitden, unread: null, ...action });
  } else if (kitden) {
    const waiting = waitingTools(rows, picked);
    const server = (block, word) => {
      kitdenServer(block, word, picked, waiting);
      for (const tool of block.server.tool_list || []) {
        const shown = toolBlock(block, tool, picked, waiting);
        tools.push(shown);
        if (shown.state === "on") links.push({ from: block.id, to: shown.id, kind: "on" });
      }
    };
    const unread = kitden.problem ? "Could not read its settings." : null;
    addGateway(kitden, { reaches: known ? linked : null, servers: kitden.servers || [], kindOf: (s) => s.kind, server, unread, ends: adds, away: out });
    leaveParts(blocks, links, kitden, rows, picked);
    // The map ends the Kitden gateway's groups with a card that opens the add panel, before any
    // other gateway: once there is a gateway to add to.
    if (addCard && !kitden.problem) blocks.push({ ...ADD_CARD });
  }
  if (kitden) connectParts(links, kitden, waits);
  for (const other of usedFirst(view, view.gateways.filter((g) => g.kind !== "kitden"))) {
    const per = view.connections[other.id] || {};
    const answer = held.get(other.id);
    // A server the gateway runs itself (uvx, npx, a container) is local to it.
    const kindOf = (s) => (heldKind(s) === "Hosted" ? "local" : "remote");
    // Not read yet, or not readable here: no count; a failed read says NOT_REACHED.
    const unread = answer && answer.servers ? null : answer && answer.error ? NOT_REACHED : "";
    const server = (block) => {
      block.meta = heldKind(block.server);
    };
    addGateway(other, { reaches: WRITABLE.filter((c) => (per[c] || []).length), servers: (answer && answer.servers) || [], kindOf, server, unread });
  }
  blocks.push(...tools);
  const outside = outsideParts(view, kitden, { picked, first, moved, out, gone: directRemovals(rows) });
  return { columns: GATEWAY_COLUMNS, blocks: [...blocks, ...outside.blocks], links: [...links, ...outside.links] };
}

// The servers outside every gateway, each joined to each client that has it by a direct line,
// with a grip where a move can take it, and in a project "This project" where the project's own
// definition replaces the shared one (`picked`). A row a move into the gateway takes (`moved`) is
// not drawn here once its preview is: its lines run to the preview block instead; while the move is
// asked it stays, with no grip. Taken out, it comes back from where its preview was (`from`). A
// client whose own entries of it all go in the tray (`gone`, by entry)
// has its line drawn leaving, and the server, once every client loses it, looks leaving too and
// has no grip. After the rows of its kind, a server whose move out of the Kitden gateway waits in
// the tray (`out`) shows in preview, "Moves to <Client>", joined to that client by a preview line;
// it is a block of its own, also where that server is outside the gateway already. It takes the
// place of the server's block in the gateway (`from`: it starts where that one shows, a drop's
// spot too, and glides into the list). Its link from the Kitden gateway is drawn leaving.
function outsideParts(view, kitden, { picked, first, moved, out, gone }) {
  const blocks = [];
  const links = [];
  for (const group of OUTSIDE_GROUPS) {
    for (const row of view.groups[group] || []) {
      const id = `outside:${group}:${row.name}`;
      const columns = (row.columns || row.clients).filter((c) => WRITABLE.includes(c));
      const line = row.unknown ? { kind: "direct", unk: true } : { kind: "direct" };
      const preview = moved.get(id);
      if (preview) {
        for (const client of columns) links.push({ from: `client:${client}`, to: preview.id, ...line, row: preview.row });
        continue;
      }
      // The clients whose line leaves, each with the keys of the rows that take its entries out.
      const leaves = new Map(columns.map((c) => [c, goneWith(row, c, gone)]).filter(([, by]) => by));
      const leaving = columns.length > 0 && leaves.size === columns.length;
      const meta = `In ${joinWords(columns.map((c) => CLIENT_NAMES[c]))}`;
      const targets = movesTo(view, group, row);
      const tag = picked && row.override ? ORIGIN_WORDS.override : null;
      // A drop moves into the Kitden gateway only, so a grip needs it; a move already in the tray
      // needs no second one, and a server on its way out has none.
      const grip = targets.some((g) => g.kind === "kitden") && !first && !moved.has(id) && !leaving;
      const state = row.unknown ? "unk" : "on";
      blocks.push({ id, column: "servers", parent: "group:outside", kind: "outside", name: row.name, meta, tag, state, lamp: "out", h: OUTSIDE_BLOCK_H, icon: OUTSIDE_ICONS[group], ports: { left: "out" }, row, groupKey: group, columns, move: targets.length > 0, grip, from: `preview:${row.name}`, ...(leaving ? { leaving } : {}) });
      for (const client of columns) links.push({ from: `client:${client}`, to: id, ...line, ...(leaves.has(client) ? leavesWith(leaves.get(client)) : {}) });
    }
    for (const [name, move] of out) {
      const server = ((kitden && kitden.servers) || []).find((s) => s.name === name);
      if (!server || (server.kind === "local" ? "local" : "move") !== group) continue;
      const id = `preview-out:${name}`;
      const backTo = `held:${kitden.id}:${name}`;
      blocks.push({ id, column: "servers", parent: "group:outside", kind: "preview", name, meta: `Moves to ${CLIENT_NAMES[move.client]}`, state: "preview", lamp: "preview", h: OUTSIDE_BLOCK_H, icon: OUTSIDE_ICONS[group], ports: { left: "out" }, takeOut: IN_PREVIEW, row: move.key, backTo, from: backTo });
      links.push({ from: `client:${move.client}`, to: id, kind: "direct", preview: true, row: move.key });
      links.push({ from: `gateway:${kitden.id}`, to: id, kind: "on", leaving: true, row: move.key });
    }
  }
  if (blocks.length) blocks.unshift({ id: "group:outside", column: "servers", kind: "group", name: OUTSIDE_MAP, pageName: OUTSIDE_PAGED, icon: "info", h: OUTSIDE_H, before: 21, rowGap: 6, folds: true });
  return { blocks, links };
}

// The keys of the tray rows that take out every entry of its own that `client` has of an outside
// `row` (`gone`, directRemovals), or null: a client with no entry of its own keeps its line.
function goneWith(row, client, gone) {
  const items = (row.client_items || {})[client] || [];
  return items.length && items.every((item) => gone.has(item)) ? [...new Set(items.map((item) => gone.get(item)))] : null;
}

// A line drawn leaving by those rows: `row`, the first, and `rows` when more than one empty it.
const leavesWith = (keys) => ({ leaving: true, row: keys[0], ...(keys.length > 1 ? { rows: keys } : {}) });

// The entries of clients that a removal in the tray takes out (mcp.remove_direct, once its row has
// its part), each with its row's key.
function directRemovals(rows) {
  const gone = new Map();
  for (const row of rows) {
    if (!row.part || row.body.action !== "mcp.remove_direct") continue;
    for (const target of row.body.targets || []) gone.set(target.item, row.key);
  }
  return gone;
}

// The servers of the Kitden gateway whose move out to one client waits in the tray, once its row
// has its part: by name, that client and the row's key.
function movesOut(rows) {
  const out = new Map();
  for (const row of rows) {
    const { action, targets = [], params = {} } = row.body;
    if (row.part && action === "gateway.move_out" && targets[0]) out.set(params.server, { client: targets[0].client, key: row.key });
  }
  return out;
}

// The changes that connect a client to the Kitden gateway: its kitden entry set up, an old one
// updated (Task 1), or one that is off turned on.
const CONNECTS = ["setup_server.register", "setup_server.update", "setup_server.enable"];

// The clients whose connection to the Kitden gateway waits in the tray, once its row has its part:
// by client, the row's key and whether it connects the client (`connect`) or disconnects it. An
// update names the client's old entry, which the setup read (`setup`) knows.
function connectRows(rows, setup) {
  const waits = new Map();
  for (const row of rows) {
    const { action, targets = [] } = row.body;
    if (!row.part || (!CONNECTS.includes(action) && action !== "client.disconnect")) continue;
    for (const target of targets) {
      const client = target.client || ((setup || []).find((e) => e.item && e.item === target.item) || {}).client;
      if (client) waits.set(client, { key: row.key, connect: action !== "client.disconnect" });
    }
  }
  return waits;
}

// The links a connect or a disconnect in the tray draws (`waits`, connectRows): a client it
// connects gets a preview link to the Kitden gateway, a client it disconnects has its link drawn
// leaving.
function connectParts(links, kitden, waits) {
  const to = `gateway:${kitden.id}`;
  for (const [client, { key, connect }] of waits) {
    const from = `client:${client}`;
    const link = links.find((l) => l.from === from && l.to === to);
    if (connect && !link) links.push({ from, to, kind: "preview", row: key });
    else if (!connect && link) Object.assign(link, { leaving: true, row: key });
  }
}

// A client's block: Connected or Not connected, and on a first run that it is found, with its
// version; and the change that disconnects it (`disconnect`) where its link's × can (connectAction).
// One that is not connected, past a first run, has the change that connects it (`connect`,
// connectBody) and can be dragged onto the gateway (`drags`). While a change that connects it waits
// in the tray (`wait`, connectRows), its lamp is the dashed ring and its meta says so (`wait`, in
// the accent), and it does not drag. Its meta says its state, so a screen reader hears no state
// word after it; on a first run, "Found" does not, and Off is heard, unless its connect waits:
// then "in preview" says it, once.
function clientBlock(id, { setup, linked, known, first, clients, wait = null }) {
  const on = linked.includes(id);
  const found = (clients || []).find((c) => c.id === id && c.status === "found");
  // Without the setup read, a client is neither connected nor not.
  let meta = known ? (on ? "Connected" : "Not connected") : NOT_KNOWN;
  // Found lights the lamp; the state stays what the link shows: no gateway reached yet. A client
  // whose state Kitden does not know has no lamp: a grey one would say off.
  let lamp = known ? (on ? "on" : "off") : null;
  const firstFound = Boolean(first && found);
  if (firstFound) [meta, lamp] = [found.version ? `Found · ${found.version}` : "Found", "on"];
  const action = on ? connectAction(id, setup) : null;
  const disconnect = action && !action.connect ? action.body : null;
  const connect = !on && !first ? connectBody(id, setup) : null;
  const block = { id: `client:${id}`, column: "clients", kind: "client", name: CLIENT_NAMES[id], meta, lamp, state: known ? (on ? "on" : "off") : "unk", stateInMeta: !firstFound, client: id, ports: { right: true }, disconnect, connect, drags: Boolean(connect) };
  if (!wait) return block;
  // The dot stays with the words before it (a no-break space), so a wrap never starts a line with it.
  // Its row lands on the map in its turn (`landsWith`, map.js landOwners).
  const waits = wait.connect ? { lamp: "preview", state: "preview", wait: "\u00a0· in preview", stateInMeta: true, connect: null, drags: false } : {};
  return { ...block, ...waits, landsWith: wait.key };
}

// The moves into the Kitden gateway the map shows: each one in the tray (`rows`), for the outside
// rows whose entries it takes, then a drag (`drop`). Each puts a block at the end of its group of
// the gateway (`adds`, each `{ kind, block }`): the preview block once its row has its part, which
// takes the outside block's place (`from`), else the slot. `moved` maps the ids of the outside rows
// the moves in the tray take to their preview block, or null while it is the slot.
function movesIn(view, kitden, rows, drop) {
  const adds = [];
  const moved = new Map();
  // The slot grows out of the gateway and shrinks back into it (map-view.js `growsFrom`).
  const slot = (name) => ({ id: `slot:${name}`, column: "servers", kind: "slot", name: "Drop to add", stateInMeta: true, state: "preview", growsFrom: `gateway:${kitden.id}` });
  // `block` goes at the end of `group` ("move" or "local"); a move in the tray takes the outside
  // row `name` of that group, while a drag keeps its block as it is.
  const put = (group, block) => {
    if (!adds.some((other) => other.block.id === block.id)) adds.push({ kind: group === "local" ? "local" : "remote", block });
  };
  const add = (group, name, block) => {
    moved.set(`outside:${group}:${name}`, block.kind === "preview" ? block : null);
    put(group, block);
  };
  for (const row of rows) {
    const { action, targets = [], params = {} } = row.body;
    const added = action === "gateway.add" && addPreview(kitden, row);
    if (added) adds.push(added);
    if (action !== "gateway.move" || !kitden || params.gateway !== kitden.id) continue;
    const items = new Set(targets.map((target) => target.item));
    for (const group of ["move", "local"]) {
      for (const each of view.groups[group] || []) {
        if (!each.items.length || !each.items.every((item) => items.has(item))) continue;
        const backTo = `outside:${group}:${each.name}`;
        const look = { icon: SERVER_ICONS[group === "local" ? "local" : "remote"], lamp: "preview", ports: { left: true }, takeOut: IN_PREVIEW };
        add(group, each.name, row.part || row.waits ? { id: `preview:${each.name}`, column: "servers", kind: "preview", name: each.name, meta: "Preview", stateInMeta: true, state: "preview", ...look, row: row.key, backTo, from: backTo, ...accessLook(row) } : slot(each.name));
      }
    }
  }
  if (drop) put(drop.kind === "local" ? "local" : "move", slot(drop.name));
  return { adds, moved };
}

// A row that adds a marketplace server (gateway.add), once it has its part and its kind
// (withKind): its preview block, for the end of that group of the Kitden gateway (`{ kind, block }`,
// as movesIn gives them). It takes no outside server's place: it grows out of the gateway's right
// side and shrinks back into it (ADD_GROW_MS), and focus on it goes to the gateway when it goes.
// After a drop it takes the place of the drop's slot instead (`from`), where that one shows.
function addPreview(kitden, row) {
  if (!kitden || !(row.part || row.waits) || !KINDS.some(([kind]) => kind === row.kind)) return null;
  const name = addName(row.body.params.server);
  const gateway = `gateway:${kitden.id}`;
  const block = { id: `preview:${name}`, column: "servers", kind: "preview", name, meta: "Preview", stateInMeta: true, state: "preview", icon: SERVER_ICONS[row.kind], lamp: "preview", ports: { left: true }, takeOut: IN_PREVIEW, row: row.key, backTo: gateway, growsFrom: gateway, growMs: ADD_GROW_MS, from: `slot:${name}`, ...accessLook(row) };
  return { kind: row.kind, block };
}

// What a change in the tray takes out, once its row has its part: a server's link from the Kitden
// gateway, and the server itself, which looks leaving; and a tool's link from its server when the
// rule is for the scope shown (`picked`, "" for all projects). The links are drawn leaving.
function leaveParts(blocks, links, kitden, rows, picked) {
  for (const row of rows) {
    if (!row.part) continue;
    const { action, params = {} } = row.body;
    let key = null;
    if (action === "gateway.remove") {
      key = `gateway:${kitden.id}>held:${kitden.id}:${params.server}`;
      const server = blocks.find((b) => b.id === `held:${kitden.id}:${params.server}`);
      if (server) Object.assign(server, { leaving: true, landsWith: row.key });
    } else if (action === "gateway.rule" && params.state === "off" && (params.project || "") === (picked || "")) key = `held:${kitden.id}:${params.server}>tool:${params.server}/${params.tool}`;
    const link = key && links.find((l) => linkKey(l) === key);
    if (link) Object.assign(link, { leaving: true, row: row.key });
  }
}

// The rules that wait in the tray, once their row has its part. For a tool, by "server/tool": in
// the scope shown (`picked`, "" for all projects) its mark is a dashed ring until Apply (`ring`,
// with the row's key); for other projects the tool names them (`others`, the project ids). A rule
// for a whole server (no tool) is named the same way by the server's name, for other projects only.
function waitingTools(rows, picked) {
  const ring = new Map();
  const others = new Map();
  for (const row of rows) {
    const { action, params = {} } = row.body;
    if (!row.part || action !== "gateway.rule") continue;
    const key = params.tool ? `${params.server}/${params.tool}` : params.server;
    if (params.tool && (params.project || "") === (picked || "")) ring.set(key, row.key);
    else if (params.project && params.project !== (picked || "")) others.set(key, [...(others.get(key) || []), params.project]);
  }
  return { ring, others };
}

// What a tool's or a server's tag of projects says while rules for other projects wait: that
// project's name or how many, in the accent (`pending`, their count).
function pendingProjects(ids) {
  const words = ids.length === 1 ? projectLabel(ids[0]) : plural(ids.length, "project", "projects");
  return { words, said: `in preview for ${words}`, own: true, pending: ids.length };
}

// What a gateway's block says under its name: the Kitden gateway's lamp and where it runs, then
// how many clients it reaches (when the setup was read, `reaches`) and how many servers it holds,
// each with its icon. A gateway Kitden could not read says why instead (`unread`), and one it is
// still reading says nothing.
function gatewayFace(gateway, reaches, servers, unread) {
  if (unread !== null) return { meta: unread || null, stats: null };
  const stats = [{ icon: "server", words: plural(servers.length, "server", "servers") }];
  if (reaches) stats.unshift({ icon: "monitor", words: plural(reaches.length, "client", "clients") });
  return gateway.kind === "kitden" ? { meta: gateway.where, lamp: "on", stats } : { meta: null, stats };
}

// A server of the Kitden gateway (`block`, with `word`, Remote or Local, for one whose tools Kitden
// does not know): how many of its tools are on ("3 of 4 on") or, with All projects, in how many
// projects it is on; its lamp, on while any of its tools is on (by its switch while Kitden knows
// none); its tag in a project; its tool count, so it folds; and then a right port too.
function kitdenServer(block, word, picked, waiting) {
  const server = block.server;
  const list = server.tool_list || [];
  block.state = server.state === "off" ? "off" : "on";
  block.onCount = list.length ? `${server.on_count} of ${list.length} on` : null;
  block.onIn = !picked && server.on_in ? `On in ${plural(server.on_in, "project", "projects")}` : null;
  block.meta = block.onIn || block.onCount || word;
  // "On in 2 projects" says the state itself; a lone On or Off beside it would contradict it.
  block.stateInMeta = Boolean(block.onIn);
  block.tag = heldTag(server, block.state === "on");
  // A rule for the whole server that waits for other projects: the block names them like a tool.
  const pending = waiting.others.get(server.name);
  if (pending) block.projects = pendingProjects(pending);
  block.count = server.tools;
  block.lamp = (list.length ? server.on_count > 0 : block.state === "on") ? "on" : "off";
  // Its sign-in ended and could not be refreshed: it needs the person (amber), not a count.
  if (server.needs === "sign-in") Object.assign(block, { lamp: "warn", meta: "Needs sign-in", stateInMeta: true });
  // It turned down a call through the gateway: it needs a token, or a new one.
  if (server.needs === "token") Object.assign(block, { lamp: "warn", meta: "Needs token", stateInMeta: true });
  block.ports = { left: true, right: typeof block.count === "number" };
  // Back from a move out taken out of the tray, it starts where its preview was.
  block.from = `preview-out:${server.name}`;
}

// "This project" for a tool whose rule is the picked project's own.
const ownTag = (tool) => (tool.origin === "project" ? ORIGIN_WORDS.override : null);
// What a screen reader hears for a tool's projects: what the folder tag means.
const OWN_HERE = "own rule in this project";

// A tool of a server in the Kitden gateway (`held`, its block): on or off (`effective` counts the
// server's switch too: a tool of a server that is off is off), its mark (a dashed ring while a rule
// for it in the scope shown waits in the tray, `waiting.ring`), and which projects have a rule of
// their own for it: with All projects how many (`own_in`), in a project "This project" when it is
// one; while rules for other projects wait (`waiting.others`), that project's name or how many, in
// the accent (`pending`, their count). `said` is what a screen reader hears for it.
function toolBlock(held, tool, picked, waiting) {
  const server = held.server;
  const key = `${server.name}/${tool.name}`;
  const on = (tool.effective ?? tool.state) === "on";
  const own = picked ? ownTag(tool) : null;
  let projects = own ? { words: own, said: OWN_HERE, own: true } : null;
  if (!picked && tool.own_in) {
    const words = plural(tool.own_in, "project", "projects");
    projects = { words, said: `own rule in ${words}`, own: false };
  }
  const pending = waiting.others.get(key);
  if (pending) projects = pendingProjects(pending);
  const lamp = waiting.ring.has(key) ? "preview" : on ? "on" : "off";
  const lands = waiting.ring.has(key) ? { landsWith: waiting.ring.get(key) } : {};
  return { id: `tool:${server.name}/${tool.name}`, column: "tools", parent: held.id, kind: "tool", name: tool.name, state: on ? "on" : "off", lamp, projects, ports: { left: true }, tool, server, ...lands };
}

// The List's rows, in order, from the tree: a "Clients" group of client rows; each gateway's own
// row, then its Remote and Local group rows with its servers and, under an open server (`open`),
// its tools; then the group outside the gateway. A group or a gateway the person folded
// (`folded`) shows no rows under it. What the tray draws on the map (a preview block, the slot of
// a move) is no row of the List, and a group that holds only that has no row either. Each row:
// { id, parent, depth, kind, name, usedBy (client ids), tools ("3 of 4 on"), meta (quiet words
// after the name), action ("open" for ›, "move" for "Move in…"), tag, scope (a tool's own rule),
// state, said (the state word a screen reader hears for a server or tool, none where its words say
// it), expanded (only on a row that folds), group, icon (a group's) }.
export function listRows(model, open = new Set(), folded = new Set()) {
  const rows = [];
  const children = new Map();
  for (const block of model.blocks) {
    if (!block.parent || ON_MAP_ONLY.includes(block.kind)) continue;
    if (!children.has(block.parent)) children.set(block.parent, []);
    children.get(block.parent).push(block);
  }
  const reaches = (id) => model.links.filter((l) => l.to === id && l.from.startsWith("client:")).map((l) => l.from.slice("client:".length));
  const row = (block, parent, depth, fields = {}) => {
    const spoken = ["held", "tool"].includes(block.kind) && !block.stateInMeta;
    const said = spoken ? (block.state === "on" ? STATE_WORDS.on : STATE_WORDS.off) : null;
    rows.push({ id: block.id, parent, depth, kind: block.kind, name: block.name, usedBy: [], tools: null, meta: null, action: "open", tag: block.tag || null, scope: null, state: block.state, said, group: false, ...fields });
  };
  const group = (id, name, parent, depth, items, draw, icon) => {
    const expanded = !folded.has(id);
    rows.push({ id, parent, depth, kind: "group", name, usedBy: [], tools: null, meta: null, action: null, tag: null, scope: null, group: true, expanded, icon });
    if (expanded) items.forEach(draw);
  };
  group("group:clients", "Clients", null, 0, model.blocks.filter((b) => b.kind === "client"), (b) => row(b, "group:clients", 1, { meta: b.meta }), "monitor");
  // The blocks of the Gateway column; the slot of a move sits in a group, so it is not one.
  for (const gateway of model.blocks.filter((b) => GATEWAY_KINDS.includes(b.kind) && b.column === "gateway")) {
    const groups = model.blocks.filter((b) => b.kind === "group" && b.under === gateway.id && children.has(b.id));
    const linked = reaches(gateway.id);
    const count = groups.reduce((n, g) => n + (children.get(g.id) || []).length, 0);
    const expanded = groups.length ? !folded.has(gateway.id) : undefined;
    // What it holds, or why Kitden does not know ("" while a live read runs: nothing to say). A
    // first run's slot says what a gateway is for.
    let meta = gateway.unread === null ? plural(count, "server", "servers") : gateway.unread || null;
    if (gateway.kind === "slot") meta = gateway.meta;
    row(gateway, null, 0, { usedBy: linked, meta, expanded });
    if (!expanded) continue;
    for (const g of groups) {
      group(g.id, g.name, gateway.id, 1, children.get(g.id) || [], (server) => {
        const tools = children.get(server.id) || [];
        const opened = tools.length ? open.has(server.id) : undefined;
        const own = server.gateway.kind === "kitden";
        row(server, g.id, 2, { usedBy: server.state === "on" ? linked : [], tools: own ? server.onCount : null, meta: own ? server.onIn : server.meta, expanded: opened });
        if (opened) for (const t of tools) row(t, server.id, 3, { tag: HINT_TAGS[t.tool.hint] || null, scope: ownTag(t.tool) });
      }, g.icon);
    }
  }
  const outside = model.blocks.find((b) => b.id === "group:outside");
  // An outside server no client is known to load says so; the others are on.
  const outsideRow = (b) => row(b, outside.id, 1, { usedBy: b.columns, action: b.move ? "move" : "open", meta: b.state === "unk" ? NOT_KNOWN : null });
  if (outside) group(outside.id, OUTSIDE, null, 0, children.get(outside.id) || [], outsideRow, outside.icon);
  return rows;
}

// The List's rows for a search (`found`, from findIn; null for none): a match's row is lit
// (`found: true`), the servers above a match show their tools, and the groups and gateways above
// one unfold. Those rows are `kept`: they stay open while the search runs, so a press on one does
// nothing. Only for this view: `open` and `folded` stay as the person left them.
export function findRows(model, found, open, folded) {
  if (!found) return listRows(model, open, folded);
  const above = new Set(found.open);
  for (const id of found.matches) for (const row of rowsAbove(model, id)) above.add(row);
  const unfolded = new Set([...folded].filter((id) => !above.has(id)));
  return listRows(model, new Set([...open, ...found.open]), unfolded).map((row) => ({ ...row, found: found.matches.has(row.id), kept: above.has(row.id) }));
}

// The map lays out narrow by the window rule (isNarrow: under 1024 px), and also when its box (null
// before it is measured) is too small for the wide map, so it never needs to scroll sideways where
// the narrow one fits. Details float over it, so they never make it narrow.
export function narrowFor(model, { window: width, box = null }) {
  return isNarrow(width) || (box !== null && box < wideWidth(model));
}

// Details float over the right of the map (panel.js). How far the map scrolls so a block whose
// right edge is at `right` ends 16 px before their left edge at `left` (both in the window); 0
// when it is clear of them.
export function besideBy(right, left) {
  return Math.max(0, Math.round(right + 16 - left));
}

const floatingNow = () => isPanelOpen() && $("#drawer").classList.contains("floating");
const scrolls = () => (D(1) ? "smooth" : "instant");

// A block or link of the map (`node`) that floating Details cover scrolls left into view beside
// them; the map takes room at its right for that (`.beside`, style.css). For the selected one, and
// for one that takes keyboard focus (focusBeside).
export function bringBeside(box, node) {
  if (!node || !floatingNow()) return;
  const by = besideBy(node.getBoundingClientRect().right, $("#drawer").offsetLeft);
  if (!by) return;
  box.classList.add("beside");
  box.scrollBy({ left: by, behavior: scrolls() });
}

// Keyboard focus never sits under floating Details (WCAG 2.4.11): focus that comes in (`target`)
// brings its block or link beside them. A mouse press focuses it too, and then nothing moves under
// the pointer (`byKeys`, which also works for a link in Safari).
export function focusBeside(box, target) {
  if (!byKeys()) return;
  bringBeside(box, target.closest("[data-focus]"));
}

// While Details float over part of the map, the map keeps that room so it can scroll sideways to
// what they cover, and the selected block or link comes beside them. When they close the map
// scrolls home, and gives the room back once it is there (newMap).
function keepBeside() {
  const box = onMap.view && onMap.view.box;
  if (!box || !box.isConnected) return;
  if (!floatingNow()) {
    if (box.scrollLeft) box.scrollTo({ left: 0, behavior: scrolls() });
    else box.classList.remove("beside");
    return;
  }
  const area = $(".map-area", box);
  if (area && besideBy(area.getBoundingClientRect().right + box.scrollLeft, $("#drawer").offsetLeft)) box.classList.add("beside");
  const { selected } = onMap;
  bringBeside(box, withFocusKey(box, `block:${selected}`) || withFocusKey(box, `link:${selected}`));
}

// The map: the blocks open and the one selected, its view (map-view.js, one per visit) and the
// tree it shows, what the search found, and the box's width as last measured. Kept across redraws,
// and across projects. `pages`: the page each group that pages shows (map.js);
// `spread`, the groups open out of their stacks (all fold when the page loads); `searched`, the
// search text whose matches brought their pages; `back`, the block a row taken out
// gives back, whose page the next draw brings; `layout`, what the last draw laid out; `folds`, the
// blocks the count folded during the search `foldsFor` (keepFolds).
const onMap = {
  project: null, open: new Set(), selected: null, view: null, model: null, found: null, width: null, narrow: false, watch: null,
  unfolds: false, pages: new Map(), spread: new Set(), searched: "", back: null, layout: null, folds: new Set(), foldsFor: "",
};

// What pointing at a block lights while nothing is selected: a client's paths, or the lines from the
// clients to a server outside the gateway. Any other block lights nothing (null).
export function glanceFor(model, id) {
  const block = model.blocks.find((b) => b.id === id);
  if (!block) return null;
  if (block.kind === "client") return litFrom(model, id);
  return block.kind === "outside" ? litPath(model, id) : null;
}

// A press on the block that is selected lets go, unless the press itself opened it (a block that
// folds is open now): then it is still the one selected.
export function afterPress({ selected, id, opened }) {
  return selected === id && !opened ? "letGo" : "select";
}

// The width of a box's content, as its ResizeObserver reports it first; null while the box is off
// the page or not laid out.
export function contentWidth(box) {
  if (!box.isConnected || !box.clientWidth) return null;
  const style = getComputedStyle(box);
  return box.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
}

// Every render puts the same map back on the page, so its blocks keep their nodes and focus.
function gatewayMap(main, model, found, { switched = false } = {}) {
  let fresh = false;
  let projectChanged = false;
  // Another project changes the map in place: what is open, selected or paged stays.
  if (onMap.project !== state.project) {
    onMap.project = state.project;
    projectChanged = true;
    // A pick is of servers in one project's map: another project starts with none.
    clearPick();
  }
  if (!onMap.view) {
    onMap.view = newMap();
    fresh = true;
  }
  main.append(onMap.view.box);
  // A new map knows its width before its first draw, so the observer's first report does not flip
  // it to narrow in the middle of its entrance.
  if (fresh) onMap.width = contentWidth(onMap.view.box) ?? onMap.width;
  const was = onMap.model;
  Object.assign(onMap, { model, found: keepFolds(found) });
  // A card that comes with a change or a rescan opens its group: it never lands inside a stack.
  if (was && !fresh && !projectChanged) onMap.spread = groupsWith(model, onMap.spread, newBlocks(was, model));
  bringPages(model, { fresh, projectChanged });
  // An Undo the page has just read: the map plays its rows back (landRows).
  const undid = undone.id;
  undone.id = null;
  if (fresh || projectChanged) landing.due = null;
  else if (landRows(was, model, undid)) return;
  drawOnMap(model, { fresh, projectChanged, switched });
}

// The pages a draw shows, before it: those of groups that still page, then the page of a block a
// row taken out gives back, of a search's matches when its text is new (or the map or the project
// is: so a turn during a search stays, and the page stays after it), and on a new map (a visit, or
// the List before) of what is selected. A search does not turn the selected block away: its page
// counts as one with a match. A selection a search still hides (a link whose end it turns away)
// is let go, as a turn by hand does.
function bringPages(model, { fresh = false, projectChanged = false } = {}) {
  const text = state.q.trim();
  const matches = onMap.found && (fresh || projectChanged || text !== onMap.searched) ? [...onMap.found.matches] : [];
  const ids = [onMap.back, matches.length && onMap.selected, ...matches, fresh && onMap.selected].filter(Boolean);
  Object.assign(onMap, { searched: text, back: null });
  onMap.pages = pagesWith(model, pagesNow(model, onMap.pages), ids);
  onMap.spread = groupsWith(model, onMap.spread, ids);
  if (matches.length) letGoHidden(model);
}

// Let go of a selection the map has but does not show now, before the draw that follows (so it
// draws nothing again itself).
function letGoHidden(model) {
  const { selected } = onMap;
  const known = selected && (model.blocks.some((b) => b.id === selected) || model.links.some((l) => linkKey(l) === selected));
  if (known && !shownOnMap(model, selected)) dropSelection();
}

// The map selects nothing, and Details close (letGoCloses) or the address forgets the selection.
function dropSelection() {
  onMap.selected = null;
  if (isPanelOpen() && letGoCloses(panelState.current)) closePanel({ focus: false });
  else setState({ selected: null });
}

// The server a row taken out gives back (the `backTo` of its preview on the map `model`), so the
// draw brings its page; null for any other row.
function givenBack(model, keys) {
  const shown = model && keys.length ? model.blocks.find((b) => keys.includes(b.row) && b.backTo) : null;
  return shown ? shown.backTo : null;
}

// The blocks of a model by id. Every link asks, so it is built once for a model.
const indexes = new WeakMap();
function blocksById(model) {
  if (!indexes.has(model)) indexes.set(model, new Map(model.blocks.map((b) => [b.id, b])));
  return indexes.get(model);
}

// What the × of a link does, as `{ tip, body }` (`body` is the change to preview), or null where
// the map does not act on the link: a client disconnects from the Kitden gateway, a client's own
// entries of a server it sets up on its own go (the row's `client_items` for that client: none
// for a plugin's server), a server in the Kitden gateway comes out of it, and a tool of such a
// server turns off, for the picked project (`picked`, "" for all). A registered gateway's links
// have none.
export function linkRemoval(model, link, picked) {
  const byId = blocksById(model);
  const from = byId.get(link.from);
  const to = byId.get(link.to);
  if (!from || !to) return null;
  if (from.kind === "client" && to.kind === "outside") {
    const items = (to.row.client_items || {})[from.client] || [];
    const body = { action: "mcp.remove_direct", targets: items.map((item) => ({ item })), params: {} };
    return items.length ? { tip: `Remove ${to.name} from ${from.name}`, body } : null;
  }
  if (from.kind === "client") {
    const kitden = to.kind === "gateway" && to.gateway.kind === "kitden";
    return kitden && from.disconnect ? { tip: `Disconnect ${from.name}`, body: from.disconnect } : null;
  }
  if (!from.gateway || from.gateway.kind !== "kitden") return null;
  if (from.kind === "gateway" && to.kind === "held") {
    return { tip: `Remove ${to.name} from the gateway`, body: { action: "gateway.remove", targets: [], params: { server: to.name } } };
  }
  if (from.kind === "held" && to.kind === "tool") {
    return { tip: `Turn off ${to.name}`, body: ruleBody(from.name, to.name, "off", picked || null) };
  }
  return null;
}

// The key of the tray row a link of the map draws (a preview link, or one leaving), else null.
function rowOfLink(model, link) {
  const shown = model.links.find((l) => linkKey(l) === linkKey(link));
  return (shown && shown.row) || null;
}

// Every row a link of the map draws: a line two rows empty takes both out. Empty when none.
function rowsOfLink(model, link) {
  const shown = model.links.find((l) => linkKey(l) === linkKey(link));
  return shown && shown.row ? shown.rows || [shown.row] : [];
}

// What the × of a link does, in words: a link the tray draws, or whose removal waits in the tray,
// is taken out of it, and the map acts on the others as linkRemoval says. "" where it does not act
// on the link: the link then has no ×.
export function linkTip(model, link, picked) {
  if (rowOfLink(model, link)) return TAKE_OUT;
  const removal = linkRemoval(model, link, picked);
  if (!removal) return "";
  return inTray(keyFor(removal.body)) ? TAKE_OUT : removal.tip;
}

// The × of a link: a link the tray draws, or whose change is in the tray already (still being
// asked), is taken out of it; any other the map acts on adds its change to the tray. Null where the
// map does not act on the link.
export function removeLink(model, link, picked) {
  const drawn = rowsOfLink(model, link);
  if (drawn.length) return takeOutHere(model, drawn);
  const removal = linkRemoval(model, link, picked);
  if (!removal) return null;
  return toggleInTray(removal.body, { icon: removalIcon(removal.body) });
}

// A press on a link: a second press on the link picked, while its panel is open, lets go of it,
// also when its change waits in the tray; one the tray draws is taken out of it (D12); any other
// is picked and opens its Connection panel.
export function clickLink(model, link) {
  const key = linkKey(link);
  if (onMap.selected === key && isPanelOpen()) {
    letGoOnMap();
    return;
  }
  const rows = rowsOfLink(model, link);
  if (rows.length) takeOutHere(model, rows).catch(reportError);
  else pickLink(key);
}

// What a link's Connection panel is drawn from (gateway-details.js linkCard): its two blocks,
// whether Kitden knows its client loads it, what its × does and the tray row it draws. Null when
// the model has no link of that key.
export function linkParts(model, key, picked) {
  const link = model && model.links.find((l) => linkKey(l) === key);
  if (!link) return null;
  const byId = blocksById(model);
  return { from: byId.get(link.from), to: byId.get(link.to), unk: Boolean(link.unk), removal: linkRemoval(model, link, picked), row: rowOfLink(model, link) };
}

// Pick a link: the map lights its two ends and keeps its ×, and its Connection panel opens beside
// the page, drawn each time from the Gateway as the page has it then (after Apply all too). A link
// does not go into the address: what it selected before leaves it.
function pickLink(key) {
  onMap.selected = key;
  setState({ selected: null });
  drawAgain();
  showLink(key, () => {
    const view = current("gateway");
    return view ? linkParts(treeFor(view), key, state.project) : null;
  });
}

// Rows taken out on the map (a key, or the keys of a line two rows empty). A move's preview block
// and link go with it, so focus on either goes to the server the move would have taken (`backTo`):
// outside the gateway for a move in, in it for a move out. Nothing happens while the tray's change
// is written.
function takeOutHere(model, keys) {
  if (writing()) return Promise.resolve();
  const gone = [].concat(keys);
  const box = onMap.view ? onMap.view.box : null;
  const shown = model.blocks.find((b) => gone.includes(b.row) && b.backTo);
  const focus = box && shown ? document.activeElement?.dataset?.focus : null;
  // The server comes back on its page: the draw the take-out starts brings it (trayChanged).
  const taken = takeOut(gone);
  const lost = Boolean(focus) && (focus === `block:${shown.id}` || focus.endsWith(`>${shown.id}`));
  if (lost) withFocusKey(box, `block:${shown.backTo}`)?.focus({ preventScroll: true });
  return taken;
}

// The hooks of the links of the map (the model is the one drawn last): every link has a hit, and a
// × while it does something (linkTip); the × waits while a change is written (linksWait).
const LINK_HOOKS = {
  canHit: () => true,
  tip: (link) => linkTip(onMap.model, link, state.project),
  waits: linksWait,
  onClick: (link) => clickLink(onMap.model, link),
  onRemove: (link) => {
    if (linksWait()) return;
    const done = removeLink(onMap.model, link, state.project);
    if (done) done.catch(reportError);
  },
};

// A new map for this visit, with what its box listens to, once.
function newMap() {
  const view = mapView({
    tile,
    onOpen: openBlock,
    onFold: foldBlock,
    onSelect: (id) => {
      const toggles = withModifier;
      withModifier = false;
      if (toggles && pickToolHere(id, toggles)) return;
      if (toggles) togglePickHere(id);
      else {
        // A plain click on another block lets go of the pick, as it opens that block's Details.
        if (clearPick()) pickChanged();
        if (toolPick.tools.size) setToolPick(null, new Set());
        pressBlock(onMap.model, id);
      }
    },
    // An empty click clears the pick, but not one with Shift or Cmd held (a pick being built).
    onEmpty: () => {
      letGoIfSelected();
      if (!withModifier && clearPick()) pickChanged();
      if (!withModifier && toolPick.tools.size) setToolPick(null, new Set());
      withModifier = false;
    },
    onHover: (id) => view.glance(glanceFor(onMap.model, id)),
    links: LINK_HOOKS,
    enterDelay: afterOldPage(),
  });
  holdKeys(view.box);
  // Escape clears the selection first; open Details then close too (panel.js).
  // The pick's Escape is heard on the page, wherever focus is (the map box takes none).
  document.removeEventListener("keydown", escapePick);
  document.addEventListener("keydown", escapePick);
  view.box.addEventListener("keydown", (event) => {
    // A key on the map is no Shift-click.
    withModifier = false;
    if (event.key !== "Escape" || !onMap.selected) return;
    onMap.selected = null;
    if (!isPanelOpen()) setState({ selected: null });
    drawAgain();
  });
  view.box.addEventListener("pointerdown", (event) => {
    withModifier = event.shiftKey ? "range" : event.metaKey || event.ctrlKey ? "add" : false;
    const base = withModifier ? new Set(toolPick.tools) : new Set();
    pressGrip(event, letGoIfSelected, pickChanged);
    // A press on empty map space may draw a band, but not while a change is written or the page
    // waits; once it does, the selection lets go.
    const onSomething = event.target && event.target.closest && event.target.closest("button, .hit");
    if (!onSomething && !withModifier && !busy.change && !pageWaits()) {
      pressBand(event, { map: onMap, onPick: () => {
        letGoIfSelected();
        pickChanged();
      }, onTools: (ids) => bandTools(ids, base) });
    }
  });
  view.box.addEventListener("scroll", () => {
    if (!view.box.scrollLeft && !floatingNow()) view.box.classList.remove("beside");
  }, { passive: true });
  view.box.addEventListener("focusin", (event) => focusBeside(view.box, event.target));
  watchMap(view.box);
  return view;
}

// While another project is read the map and the List take no key but Tab (design.md Project
// switch): a key on a link, a block or a row would act on the project they were drawn for. The
// box hears the key first and keeps it from them.
function holdKeys(box) {
  const hold = (event) => {
    if (event.key === "Tab" || !pageWaits()) return;
    event.preventDefault();
    event.stopPropagation();
  };
  box.addEventListener("keydown", hold, true);
  box.addEventListener("keyup", hold, true);
}

// A press on a block that folds opens or folds it, before it is selected. `unfolds` says that the
// press opened it: what it holds comes in before the path of the selection lights.
function openBlock(id) {
  const { model } = onMap;
  onMap.open = pressOpen(model, onMap.open, onMap.found, id);
  onMap.unfolds = onMap.open.has(id);
}

// A press on the count of a server opens or folds it and nothing else: the selection and Details stay,
// unless the fold hides the selected block (a tool of this server), which is let go like a turn
// of a page does.
function foldBlock(id) {
  const { model } = onMap;
  onMap.open = pressCount(model, onMap.open, onMap.found, id, onMap.folds);
  onMap.unfolds = false;
  if (onMap.selected && !shownOnMap(model, onMap.selected)) letGoOnMap();
  else drawAgain();
}

// A search's `found` with the blocks its count folded still folded (map.js keepFolded); a new search
// text starts with none, so the fold lasts for that search.
function keepFolds(found) {
  const text = state.q.trim();
  if (onMap.foldsFor !== text) Object.assign(onMap, { folds: new Set(), foldsFor: text });
  return keepFolded(found, onMap.folds);
}

// A new width of the box (the window) may change the layout: it is drawn again, at once in its new
// shape. Details closing (Escape, Close or another place) clears what the map lights; the panel's
// class says when it closes. Details that open, close or show another block keep it beside them.
function watchMap(box) {
  if (!onMap.watch) {
    onMap.watch = new ResizeObserver((entries) => {
      const entry = entries[entries.length - 1];
      if (!entry.target.isConnected) return;
      onMap.width = entry.contentRect.width;
      if (narrowNow(onMap.model) !== onMap.narrow) drawAgain();
    });
    new MutationObserver(() => {
      keepBeside();
      if (isPanelOpen() || !onMap.selected) return;
      onMap.selected = null;
      drawAgain();
    }).observe($("#drawer"), { attributes: true, attributeFilter: ["class"], childList: true });
  }
  onMap.watch.disconnect();
  onMap.watch.observe(box);
}

function narrowNow(model) {
  return narrowFor(model, { window: innerWidth, box: onMap.width });
}

// The blocks open now: those the person opened, and those a search opens to show a match (a
// group with a match shows all its blocks). The search keeps them for the view only.
function openNow() {
  return onMap.found ? new Set([...onMap.open, ...onMap.found.open]) : onMap.open;
}

// How a draw of the map shows: a new map enters (each block rises into its place), except one the
// view switch brings, which comes in as one piece (renderGateway); a new width shows at once;
// another project changes the map in place (map-view.js "project"), and anything else moves what
// changed.
export function mapMotion({ fresh, projectChanged, narrowChanged, switched = false, undo = false }) {
  if (fresh) return switched ? "none" : "enter";
  if (narrowChanged) return "none";
  if (projectChanged) return "project";
  return undo ? "undo" : "move";
}

// A press that opened a block (`unfolds`) draws its selection first and lights its path when the
// motions end, as its tools come in first. With no path there is nothing to wait for.
export function lightsLater({ unfolds, lit }) {
  return Boolean(unfolds) && lit.size > 0;
}

// When those motions end, the path lights only if the map and the selection are still the ones that
// were drawn (`drawn`, against `now`: { view, selected }); a newer selection lights its own.
export function stillSelected(drawn, now) {
  return drawn.view === now.view && drawn.selected === now.selected;
}

// Draw the map as it is now, as `mapMotion` says (`undo`: what an Undo put back). With `lightLater`
// (a press that opened a block) the selection shows, but its path lights (the dims and the accent
// lines) when every motion of this draw has ended: a server's tools come in first. The promise ends
// with the last motion. Any draw but a step of a landing (`staged`) ends the landing that runs.
function drawOnMap(model, { fresh = false, projectChanged = false, lightLater = false, switched = false, undo = false, staged = false } = {}) {
  if (!staged) stopLanding();
  const narrow = narrowNow(model);
  const flipped = narrow !== onMap.narrow;
  onMap.narrow = narrow;
  const open = openNow();
  const layout = layoutTree(model, { open, pages: onMap.pages, spread: onMap.spread, narrow });
  onMap.layout = layout;
  drawChip(shownFound(onMap.found, layout));
  // A selected block lights every client's path to it; a selected client lights what it reaches; a
  // selected link its two ends. A selection the model no longer has is none.
  const lit = litFor(model, onMap.selected);
  const motion = mapMotion({ fresh, projectChanged, narrowChanged: flipped, switched, undo });
  const { view, selected } = onMap;
  const later = lightsLater({ unfolds: lightLater, lit });
  keepPickable(model);
  setHint(mapHint(), hintActs());
  const chosen = new Set([...pick.ids, ...[...toolPick.tools].map((name) => `tool:${toolPick.server}/${name}`)]);
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, chosen, lit: later ? new Set() : lit, found: onMap.found, open, motion });
  // A block a move took off its place stays where it is shown (gateway-drag.js); a drag draws the
  // map again in place as its slot opens or closes.
  placeMoved({ view, model, layout, redraw: drawRows });
  if (later) drawn.then(() => stillSelected({ view, selected }, onMap) && drawAgain());
  return drawn;
}

// Draw the map again in place; its blocks keep their nodes, so focus stays where it is.
function drawAgain(options) {
  const { view, model } = onMap;
  if (!view || !view.box.isConnected) return Promise.resolve();
  return drawOnMap(model, options);
}

// Letting go of the selection closes the Details it opened, unless they show a row's review
// (`current`, panelState's): that review belongs to the tray, not to the selection.
export function letGoCloses(current) {
  return !(current && current.type === "row-review");
}

// Let go of the selection: the map shows none and Details close (letGoCloses). Focus stays where
// it is.
function letGoOnMap() {
  dropSelection();
  drawAgain();
}

// A click on empty map, or the start of a drag, lets go of what is selected.
function letGoIfSelected() {
  if (onMap.selected) letGoOnMap();
}

// Picking several servers outside the gateway (gateway-pick.js): a press with Shift or Cmd held
// makes the click that follows pick or unpick its block instead of selecting it.
let withModifier = false;
function togglePickHere(id) {
  if (togglePick(onMap.model, id)) {
    letGoIfSelected();
    pickChanged();
  } else pressBlock(onMap.model, id);
}

// Picking tools on the map: the tools column shows one server's tools, the one whose Details are
// open, and the pick is the same as in its Details' list (tools.js toolPick), whose bar turns them
// off or on. Cmd or Ctrl and a click picks one more, Shift a run; a band over the tools picks them.
const toolBlocks = (model) => model.blocks.filter((block) => block.kind === "tool");
// Which tools of `server` are on, and where a rule for them goes: what Turn off and Space need.
const toolStates = (server) => ({
  states: new Map(toolBlocks(onMap.model).filter((b) => b.server.name === server).map((b) => [b.name, b.state === "on"])),
  project: state.project || null,
});
function pickToolHere(id, how) {
  const block = onMap.model.blocks.find((b) => b.id === id);
  if (!block || block.kind !== "tool") return false;
  const server = block.server.name;
  const keys = toolBlocks(onMap.model).filter((b) => b.server.name === server).map((b) => b.name);
  const now = toolPick.server === server ? toolPick.tools : new Set();
  const next = pickTools(now, keys, block.name, { add: how === "add", range: how === "range", anchor: toolPick.anchor });
  setToolPick(server, next.picked, next.anchor, toolStates(server));
  return true;
}
function bandTools(ids, base) {
  const met = toolBlocks(onMap.model).filter((block) => ids.includes(block.id));
  if (!met.length) return;
  const server = met[0].server.name;
  const kept = toolPick.server === server ? base : new Set();
  setToolPick(server, new Set([...kept, ...met.filter((b) => b.server.name === server).map((b) => b.name)]), toolPick.anchor, toolStates(server));
}
// The map draws the tool pick, and the hint counts it.
onToolPick(() => {
  if (!onMap.view || !onMap.view.box.isConnected) return;
  setHint(mapHint(), hintActs());
  drawAgain();
});

// The hint line's own buttons while tools are picked: they turn them off or on from the map, with
// or without their server's Details open.
function hintActs() {
  if (!toolPick.tools.size) return [];
  const act = (label, value) => button(label, () => flipToolPick(value));
  return [act("Turn off", "off"), act("Turn on", "on"), button("Clear", () => setToolPick(null, new Set()))];
}

// Escape on the Gateway map's page clears the pick.
function escapePick(event) {
  if (event.key !== "Escape" || state.view !== "gateway" || !onMap.view || !onMap.view.box.isConnected) return;
  if (clearPick()) pickChanged();
}

// The pick changed: the map draws it, and the hint counts it.
function pickChanged() {
  setHint(mapHint(), hintActs());
  drawAgain();
}

// The map's hint: the pick's count while something is picked, or what the band left out.
function mapHint() {
  if (toolPick.tools.size) return `${plural(toolPick.tools.size, "tool", "tools")} picked · Space turns them off · Esc clears`;
  return pick.ids.size || pick.stuck ? PICK_HINT(pick.ids.size, pick.stuck) : MAP_HINT;
}

// The Add a server panel (gateway-add.js) lets go of what is selected first, from both its doors:
// "+ Add servers" in the page header and Details' More.
onOpenAdd(letGoIfSelected);

// A press on a block (a held server opened or folded first, by onOpen). A stack opens or turns its
// group, and Collapse folds it (foldOnMap). A second press on the selected block lets go. The
// first run's slot adds the change that sets every client up; the slot of a drag does nothing. A
// preview block takes its row out of the tray (D12), unless it waits for access: then it opens the
// access panel. Any other block is selected.
export function pressBlock(model, id) {
  if (id.startsWith("stack:") || id.startsWith("collapse:")) {
    foldOnMap(model, id);
    return;
  }
  const block = model.blocks.find((b) => b.id === id);
  if (!block) return;
  // The Add a server card opens the add panel; focus comes back to the card.
  if (block.kind === "addslot") {
    openAdd({ from: withFocusKey($("#main"), `block:${id}`) }).catch(reportError);
    return;
  }
  if (afterPress({ selected: onMap.selected, id, opened: foldable(model).has(id) && onMap.open.has(id) }) === "letGo") {
    letGoOnMap();
    return;
  }
  if (block.kind === "slot" && block.setup) review(block.setup, { note: SETUP_NOTE }).catch(reportError);
  else if (block.kind === "preview" && block.needs) {
    // A server that waits for access opens its token field; the dock row's × takes it out.
    const row = trayRow(block.row);
    if (row && row.waits) openAccess(row);
  } else if (block.kind === "preview") takeOutHere(model, block.row).catch(reportError);
  else if (block.kind !== "slot" || block.gateway) selectOnMap(block);
}

// A press on a stack opens its group or turns its page, and Collapse folds the group. A turn says
// the caption to a screen reader ("Remote · 6–10 of 12"). A selection the press hides is let go.
// Focus stays on a stack that still shows; else it goes to the first card shown, or after Collapse
// to the group's stack.
function foldOnMap(model, id) {
  const view = { spread: onMap.spread, pages: onMap.pages };
  Object.assign(onMap, id.startsWith("collapse:") ? collapseGroup(view, id) : pressStack(model, view, id));
  const words = id.startsWith("stack:") ? turnWords(model, onMap.pages, id) : "";
  if (words) say(words);
  if (onMap.selected && !shownOnMap(model, onMap.selected)) letGoOnMap();
  else drawAgain();
  const shown = onMap.layout ? onMap.layout.blocks : [];
  if (!onMap.view || shown.some((at) => at.id === id)) return;
  const group = groupOfStack(id);
  const next = id.startsWith("collapse:") ? `stack:${group}:all` : shown.find((at) => at.turns === group)?.id;
  if (next) onMap.view.node(next)?.focus({ preventScroll: true });
}

// Whether the map shows a block, or both ends of a link (its key), as it lays out now.
function shownOnMap(model, selected) {
  const link = model.links.find((l) => linkKey(l) === selected);
  const shown = new Set(layoutTree(model, { open: openNow(), pages: onMap.pages, spread: onMap.spread, narrow: onMap.narrow }).blocks.map((at) => at.id));
  return (link ? [link.from, link.to] : [selected]).every((id) => shown.has(id));
}

// Select a block: the map lights it and is drawn again, then its Details open beside the page.
// The List takes the Tab key on the same row.
function selectOnMap(block) {
  // Its page shows, and what a search opened to show it stays open, so the selection is still on
  // the map when the search ends.
  onMap.pages = pagesWith(onMap.model, onMap.pages, [block.id]);
  onMap.spread = groupsWith(onMap.model, onMap.spread, [block.id]);
  onMap.open = keepOpen(onMap.model, onMap.open, block, onMap.pages);
  onMap.selected = block.id;
  onList.current = block.id;
  const lightLater = onMap.unfolds;
  onMap.unfolds = false;
  drawAgain({ lightLater });
  openDetails(block);
}

// An arrival on the map selects its block as a press does, and opens a tool's server first (a
// tool its server no longer lists selects the server). A group opens the List there, in place of
// this address, so Back does not come back to a map that leaves again.
function arriveOnMap(model, found) {
  if (found.group && !found.outside) {
    setState({ mode: "list" });
    arrival.pending = true;
    render();
    return;
  }
  const byId = new Map(model.blocks.map((b) => [b.id, b]));
  let id = `client:${found.client}`;
  if (found.held) {
    const server = `held:kitden:${found.held.name}`;
    const tool = found.tool ? `tool:${found.held.name}/${found.tool}` : null;
    id = tool && byId.has(tool) ? tool : server;
    if (id === tool && !onMap.open.has(server)) onMap.open = toggleOpen(model, onMap.open, server);
  } else if (found.outside) id = `outside:${found.group}:${found.outside.name}`;
  if (byId.has(id)) selectOnMap(byId.get(id));
}

// The tray as the map last heard it, so it knows when an applied change has landed.
let trayWas = tray.phase;
let trayKeys = tray.rows.map((row) => row.key);
onTray(trayChanged);
// A change that starts or stops being written: the × of the link pointed at says so.
onBusy(() => onMap.view?.aimAgain());
// Cancel in the dock with focus there: a single move gives focus to the server it would have taken.
// The draw the Cancel starts brings that server's page (trayChanged).
setCancelFocus((rows) => (onMap.view && onMap.view.box.isConnected ? cancelFocusFor(onMap.model, rows) : null));

// The focus key of the server a single move in the tray would have taken (its preview's `backTo`
// on the map `model`), else null.
export function cancelFocusFor(model, rows) {
  if (!model || rows.length !== 1) return null;
  const shown = model.blocks.find((b) => b.row === rows[0].key && b.backTo);
  return shown ? `block:${shown.backTo}` : null;
}

// The tray changed: the map draws its rows again in place, while it shows. Not while its change is
// applied: the page reads the result first, and its rows land on the map one by one (landRows).
// Once it has landed (the tray empties), focus it took away goes to the gateway block. A row taken
// out by any way (the map, the bar's ×, Cancel, Details) gives its server back on its page.
function trayChanged(t) {
  const applied = trayWas === "applied";
  const landed = applied && t.phase === "idle";
  const left = trayKeys.filter((key) => !t.rows.some((row) => row.key === key));
  trayWas = t.phase;
  trayKeys = t.rows.map((row) => row.key);
  if (t.phase === "applied") {
    if (onMap.view && onMap.view.box.isConnected) landing.due = { keys: t.rows.map((row) => row.key), id: t.change.id, view: current("gateway") };
    return;
  }
  onMap.back = applied ? null : givenBack(onMap.model, left);
  const drawn = drawRows();
  onMap.back = null;
  // A result the page could not read again lands nothing later.
  if (landed) landing.due = null;
  if (!landed) return;
  focusGateway({ fromDock: true });
  drawn.then(() => focusGateway({ fromDock: false }));
}

// The map drawn again in place with the tray as it is now: not on the List or another place.
// The promise ends with its motions.
function drawRows() {
  const view = current("gateway");
  if (!view || !onMap.view || !onMap.view.box.isConnected) return Promise.resolve();
  const model = treeFor(view);
  const was = onMap.model;
  Object.assign(onMap, { model, found: keepFolds(state.q.trim() ? findIn(model, state.q) : null) });
  bringPages(model);
  return landRows(was, model) || drawOnMap(model);
}

// Landing (motion-spec M4 step 6): after a verified Apply all the map shows each row's change in
// tray order, 60 ms apart; an Undo of it plays them back in reverse, 120 ms apart, and a link that
// comes back draws in over 480 ms. `due`: an Apply whose result the page has not read yet ({ keys,
// id, view }: its rows, its change and the read it was applied on). `last`: what each part of the
// map belonged to in the last landing, for its Undo. While one runs: its timers, the end of its
// promise (`end`) and the promise (`done`).
const landing = { due: null, last: null, timers: [], end: null, done: null };
const LAND_GAP = 60;
const UNDO_GAP = 120;

// A draw of what Kitden read again (`model`, after `was`): the rows of an Apply whose result it is
// land in turn; an Undo (`undid`, its change's id) plays the rows of the last landing back, and any
// other Undo moves at once with the Undo's draw-in. While a landing runs the draw waits for it: its
// last step draws the newest tree. Null when the caller draws as usual.
function landRows(was, model, undid = null) {
  if (landing.timers.length) return landing.done;
  const { due, last } = landing;
  if (due && current("gateway") !== due.view) {
    landing.due = null;
    const owners = landOwners(was, model, due.keys);
    landing.last = { id: due.id, keys: due.keys, owners };
    return playRows(was, model, due.keys, owners, { gap: LAND_GAP });
  }
  if (!undid) return null;
  if (!last || last.id !== undid) return drawOnMap(model, { undo: true });
  landing.last = null;
  const keys = [...last.keys].reverse();
  return playRows(was, model, keys, landOwners(was, model, keys, last.owners), { gap: UNDO_GAP, undo: true });
}

// The rows' changes one at a time, `gap` ms apart: at each step the rows after it still wait
// (map.js landStage). The promise ends with the motions of the last step, or when another draw
// ends the landing. Reduced motion draws the end at once.
function playRows(was, model, keys, owners, { gap, undo = false }) {
  const end = keys.length - 1;
  const step = (i) => drawOnMap(landStage(was, i === end ? onMap.model : model, owners, new Set(keys.slice(i + 1))), { undo, staged: true });
  if (end < 1 || !D(gap)) return step(end);
  stopLanding();
  landing.done = new Promise((resolve) => {
    landing.end = resolve;
    step(0);
    for (let i = 1; i <= end; i++) {
      landing.timers.push(setTimeout(() => {
        if (i < end) {
          step(i);
          return;
        }
        landing.timers = [];
        landing.end = null;
        step(end).then(resolve);
      }, D(i * gap)));
    }
  });
  return landing.done;
}

// A landing that runs stops where it is; the draw that stops it shows the map as it is now.
function stopLanding() {
  for (const timer of landing.timers) clearTimeout(timer);
  landing.timers = [];
  if (landing.end) landing.end();
  landing.end = null;
}

// After an applied change, focus on nothing or on the page itself (a block or link that went) goes
// to the Kitden gateway's block, when the map shows it; so does focus in the dock as its bar
// leaves (`fromDock`, only right away: later a toast may hold it). Focus anywhere else stays.
function focusGateway({ fromDock }) {
  const active = document.activeElement;
  const lost = !active || active === document.body || active === $("#main") || (fromDock && $("#dock").contains(active));
  const node = lost ? withFocusKey($("#main"), "block:gateway:kitden") : null;
  if (node) node.focus({ preventScroll: true });
}

// What a block shows before its name: a client's tile, the Kitden house (it keeps its own color),
// a registered gateway's mark, or the icon of what kind of server it is (15 px, on a tile of its
// own except outside the gateway, a move out's preview too: `.bare` in style.css). The slot of a
// drag shows nothing.
function tile(block) {
  if (block.kind === "client") return mark(block.client);
  if (GATEWAY_KINDS.includes(block.kind) && block.gateway) {
    return block.gateway.kind === "kitden" ? kitdenHouse("block-house") : mark("gateway");
  }
  if (!block.icon) return null;
  const holder = el("span", block.parent === "group:outside" ? "block-icon bare" : "block-icon");
  holder.append(icon(block.icon, 15));
  return holder;
}

// The List, a tree grid: the servers that show their tools (`open`), the groups and gateways the
// person folded, and the row that takes the Tab key, kept across redraws and other projects (a row
// that is gone gives the Tab key to the first).
const onList = { open: new Set(), folded: new Set(), current: null, box: null };

function gatewayList(main, view, model, found, { enter = false } = {}) {
  const rows = findRows(model, found, onList.open, onList.folded);
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  if (!rows.some((r) => r.id === onList.current)) onList.current = rows.length ? rows[0].id : null;
  const chosen = selectedRow(rows, byId);
  const grid = el("div", found ? "treegrid finding" : "treegrid");
  grid.setAttribute("role", "treegrid");
  grid.setAttribute("aria-label", "Clients, gateways and MCP servers");
  const head = el("div", "tg-head");
  head.setAttribute("role", "row");
  // The last column has no title on the page; a screen reader hears "Action".
  for (const name of ["Name", "Used by", "Tools", ""]) {
    const cell = el("div", null, name);
    cell.setAttribute("role", "columnheader");
    if (!name) cell.append(el("span", "sr-only", "Action"));
    head.append(cell);
  }
  grid.append(head);
  // A row a search showed stays shown when the search ends: what holds it unfolds for good.
  const press = { toggle: toggleRow, open: (row) => { unfoldAbove(model, row.id); openRow(row, byId.get(row.id)); } };
  for (const row of rows) grid.append(listRow(row, byId.get(row.id), { current: row.id === onList.current, selected: row.id === chosen, view, press }));
  // One row takes the Tab key; the arrows move between rows, Right and Left fold, Enter opens.
  // Keys on a row's own button stay that button's.
  holdKeys(grid);
  gridKeys(grid, rows, { toggle: toggleRow, details: press.open, focus: (id) => focusRow(grid, id) });
  main.append(grid);
  onList.box = grid;
  if (enter) rise([grid], { delay: afterOldPage() });
}

// The row of what the address selects: a server (the row that takes the Tab key when both of a
// name's rows match), a tool or a client.
function selectedRow(rows, byId) {
  const selected = state.selected;
  if (!selected) return null;
  const matches = rows.filter((row) => {
    const block = byId.get(row.id);
    if (selected.kind === "mcp_server") return (row.kind === "outside" || (row.kind === "held" && block.gateway.kind === "kitden")) && row.name === selected.name;
    if (selected.kind === "direct") return row.kind === "outside" && row.name === selected.name;
    if (selected.kind === "tool") return row.id === `tool:${selected.name}`;
    return selected.kind === "client" && row.id === `client:${selected.name}`;
  });
  const own = matches.find((row) => row.id === onList.current);
  return (own || matches[0] || {}).id || null;
}

const cell = (className, text) => gridCell("gridcell", className, text);

// One row: a fold mark where it folds, what it is (a client's tile, a gateway's mark, the dot of a
// server or tool, filled when on), its name, tags and quiet words; then the clients that use it,
// its tools, and › or "Move in…". A click opens its Details, or folds it on the fold mark; a
// group row folds.
function listRow(row, block, { current, selected, view, press }) {
  const { node, name } = treeRow(row.group ? "tg-row group" : `tg-row ${row.kind}`, row, { current, selected });
  if (row.found) node.classList.add("found");
  if (row.kind === "client") name.append(mark(block.client));
  else if (GATEWAY_KINDS.includes(row.kind)) name.append(mark(block.gateway.kind === "kitden" ? "kitden" : "gateway"));
  else if (row.kind === "held" || row.kind === "tool") {
    const dot = el("span", row.state === "on" ? "tg-dot on" : "tg-dot");
    dot.setAttribute("aria-hidden", "true");
    name.append(dot);
  }
  const words = el("span", row.group ? "words" : "words name", row.name);
  words.title = row.name;
  name.append(words);
  if (row.said) name.append(el("span", "sr-only", row.said));
  // A tool's tag says whether it reads or writes; an accent tag says a rule of this project.
  const accent = row.kind === "tool" ? row.scope : row.tag;
  if (accent) name.append(el("span", "tag", accent));
  if (row.kind === "tool" && row.tag) name.append(el("span", "hint", row.tag));
  if (row.meta) name.append(el("span", "meta", row.meta));
  if (row.group) {
    name.setAttribute("aria-colspan", "4");
    node.append(name);
    node.addEventListener("click", () => press.toggle(row));
    return node;
  }
  const used = cell("tg-used");
  used.append(...row.usedBy.map((client) => mark(client)));
  if (row.usedBy.length) used.append(el("span", "sr-only", joinWords(row.usedBy.map((c) => CLIENT_NAMES[c]))));
  const action = cell("tg-action");
  if (row.action === "move") {
    // The drag's keyboard path: the same review as "Move into the gateway…" in Details.
    const move = button("Move in…", () => moveInto(movesTo(view, block.groupKey, block.row), block.row.items, block.name), "btn small");
    move.tabIndex = current ? 0 : -1;
    move.dataset.focus = `move:${row.id}`;
    action.append(move);
  } else action.append(opens());
  node.append(name, used, cell("tg-tools", row.tools || ""), action);
  node.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    if (row.expanded !== undefined && event.target.closest(".caret")) press.toggle(row);
    else press.open(row);
  });
  return node;
}

// Move the Tab key, and focus, to another row (and to its own button).
function focusRow(grid, id) {
  onList.current = id;
  focusTreeRow(grid.querySelectorAll("[data-row]"), id, (node) => node.querySelectorAll("button"));
}

// Fold or unfold a row: a server shows its tools; a group or a gateway hides its rows.
function toggleRow(row) {
  if (row.kept) return; // a search holds it open
  const set = row.kind === "held" ? onList.open : onList.folded;
  if (set.has(row.id)) set.delete(row.id);
  else set.add(row.id);
  onList.current = row.id;
  render();
}

// A row's Details, beside the page; the map selects the same block.
function openRow(row, block) {
  onList.current = row.id;
  onMap.selected = row.id;
  for (const node of document.querySelectorAll(".treegrid [data-row]")) node.setAttribute("aria-selected", String(node.dataset.row === row.id && !GATEWAY_KINDS.includes(row.kind)));
  openDetails(block);
}

// A block's Details, beside the page. A server, a tool or a client goes into the address; a
// gateway does not.
function openDetails(block) {
  if (block.kind === "client") {
    setState({ selected: { kind: "client", name: block.client } });
    showClient(block.client);
  } else if (GATEWAY_KINDS.includes(block.kind)) {
    setState({ selected: null });
    showGateway(block.gateway.id);
  } else if (block.kind === "held") {
    if (block.gateway.kind === "kitden") showHeld(block.server.name).catch(reportError);
    else showRegistered(block.server, block.gateway);
  } else if (block.kind === "tool") showTool(block.server.name, block.name).catch(reportError);
  else if (block.kind === "outside") showOutside(block.groupKey, block.name).catch(reportError);
}

// The rows above `id` in the List, so an arrival can unfold them.
function rowsAbove(model, id) {
  if (id.startsWith("client:")) return ["group:clients"];
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  const above = [];
  for (let block = byId.get(id); block && (block.parent || block.under); block = byId.get(block.parent || block.under)) {
    above.push(block.parent || block.under);
  }
  return above;
}

// Unfold every row above `id`: a server shows its tools, a group or a gateway shows its rows.
function unfoldAbove(model, id) {
  for (const above of rowsAbove(model, id)) {
    onList.folded.delete(above);
    if (above.startsWith("held:")) onList.open.add(above);
  }
}

// Show a row in the List and focus it, so its Details open from it and Escape comes back to it:
// every row above it unfolds (and a group itself with `unfold`).
function showRow(model, id, { unfold = false } = {}) {
  unfoldAbove(model, id);
  if (unfold) onList.folded.delete(id);
  onList.current = id;
  render();
  const node = withFocusKey($("#main"), `row:${id}`);
  if (node) node.focus();
}

async function openArrival(view, model, mode) {
  const found = await arrivalServer(view);
  if (!found) return;
  if (mode === "map") {
    arriveOnMap(model, found);
    return;
  }
  if (found.held) {
    const name = found.held.name;
    showRow(model, found.tool ? `tool:${name}/${found.tool}` : `held:kitden:${name}`);
    // A tool the server no longer lists opens its server.
    const listsIt = found.tool && (found.held.tool_list || []).some((t) => t.name === found.tool);
    if (listsIt) await showTool(name, found.tool);
    else await showHeld(name);
  } else if (found.outside) {
    showRow(model, `outside:${found.group}:${found.outside.name}`);
    await showOutside(found.group, found.outside.name);
  } else if (found.client) showRow(model, `client:${found.client}`);
  else if (found.group) showRow(model, `group:${found.group}`, { unfold: true });
}

// Details of a server a registered gateway holds: what it is and where it is set. The address
// stays behind Details, as on the other lists.
function showRegistered(server, gateway) {
  const body = el("div", "body");
  const row = el("div", "layer");
  const middle = el("div");
  const kind = heldKind(server);
  middle.append(el("div", "name", `In ${gatewayName(gateway)} · ${kind === "Remote" ? "Streamable HTTP" : kind === "Hosted" ? `Hosted by ${gatewayName(gateway)} (${server.type})` : kind}`));
  const url = el("div", "why mono", server.url || "");
  url.title = server.url || "";
  if (server.url) middle.append(url);
  row.append(mark("gateway"), middle);
  const stack = el("div", "stack");
  stack.append(row);
  body.append(stack, el("p", "muted", `Tools and access are set in ${gatewayName(gateway)} itself.`));
  openInfo("MCP server", server.name, body);
}

