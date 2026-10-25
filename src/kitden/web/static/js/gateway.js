// Gateway: the clients, the gateways and the MCP servers they reach, as a Map or a List. Each
// row opens its Details beside the page (gateway-details.js).
import { $, button, el, gridKey, icon, joinWords, plural, reportError, withFocusKey } from "./dom.js";
import { addForm, connectAction, heldServer, liveHeld, movesTo, OUTSIDE_ICONS, removalIcon, ruleBody, SERVER_ICONS, SETUP_NOTE, showClient, showGateway, showHeld, showLink, showOutside, showTool, TAKE_OUT } from "./gateway-details.js";
import { movingOn, placeMoved, pressGrip } from "./gateway-drag.js";
import { findIn, foldable, isNarrow, keepOpen, layoutTree, linkKey, litFrom, litPath, pressOpen, toggleOpen, wideWidth } from "./map.js";
import { mapView } from "./map-view.js";
import { afterOldPage, D, entrance, glide, rise, riseHead } from "./motion.js";
import { closePanel, isPanelOpen, moveInto, openInfo, panelState, projectLabel, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, folderName, gatewayName, kitdenClients, mark, opens, ORIGIN_WORDS, scopeBar, skeleton, STATE_WORDS, staleNote } from "./parts.js";
import { arrival, current, currentError, data, go, goTo, projectPath, render, retry, setState, state, takeArrival, toolSel, viewMode } from "./store.js";
import { addToTray, inTray, keyFor, onTray, takeOut, tray } from "./tray.js";

// Overview sets a client up with the same note. A server the Kitden gateway holds, and its
// links, are found where its Details are drawn.
export { heldServer, kitdenLinks, SETUP_NOTE } from "./gateway-details.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
// The group of servers outside the gateway: the List's words, and the map's, which asks for a drag.
const OUTSIDE = "Outside the gateway · calls skip Kitden's rules";
const OUTSIDE_MAP = "Outside the gateway · drag one in";
// On the map these words take one line, wider than their column, and an outside server's block is
// 50 high.
const OUTSIDE_H = 16;
const OUTSIDE_BLOCK_H = 50;
// The groups of servers outside the gateway in /api/gateway-view, in the order the page lists them.
// A server's icon on the map is the one its panel shows (SERVER_ICONS, OUTSIDE_ICONS).
const OUTSIDE_GROUPS = ["move", "local", "plugin"];
// What a block in preview says under the pointer: a press takes its row out of the tray (D12).
const IN_PREVIEW = "In preview. Click to take it out.";
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

// What an arrival with a selection (Back, Forward or a link) opens, once: a server the Kitden
// gateway holds (`held`, and `tool` for one of its tools), a server outside it by its name (its
// row, `outside`, and its `group`), a client or a List group. Null for anything else (it stays in
// the address for the next page), and while a panel is open, so it never replaces what the person
// opened. Everything is found in the Gateway's own model: the Library's /api/map is never read.
export async function arrivalServer(view) {
  const selected = takeArrival();
  if (!selected || isPanelOpen()) return null;
  if (selected.kind === "mcp_server") {
    const held = heldServer(view, selected);
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
// (title, lede, scope line), and then the map or List.
export function renderGateway(main, { again = false } = {}) {
  if (!again) onMap.view = null;
  const head = el("div", "page-head");
  head.append(el("h1", null, "Gateway"));
  const lede = el("p", "lede", "Connect your agents. Shape what they can use.");
  main.append(head, lede);
  const view = current("gateway");
  if (!view) {
    if (!again) riseHead(head, lede, null);
    if (currentError("gateway")) main.append(banner("the gateway", retry));
    else main.append(skeleton("card", 2));
    return;
  }
  // Under the head: what the page shows, the shared setup or a project's rules that differ from it.
  const scope = scopeBar(folderName(projectPath()), view.own_rules);
  main.append(scope);
  if (!again) riseHead(head, lede, scope);
  if (currentError("gateway")) main.append(staleNote(data.readAt.gateway));
  // Only without any gateway, the Kitden one included (no home folder to change).
  if (!view.gateways.length) {
    main.append(noGateway());
    return;
  }
  const mode = viewMode(state, serverCount(view));
  const seg = modeSwitch(mode);
  head.append(seg);
  const model = treeFor(view, mode);
  // The search finds here: matches light up, the rest dims, and what hides a match opens (S.6).
  // It changes nothing in a client and moves no Details.
  const found = state.q.trim() ? findIn(model, state.q) : null;
  if (mode === "map") gatewayMap(main, model, found);
  else {
    onMap.view = null;
    gatewayList(main, view, model, found, { enter: !again });
  }
  glide(seg, seg.querySelector('[aria-pressed="true"]'), "gateway-view", { duration: 280 });
  // A performance mark for the map probe (Part 4.1): the first time the page draws with data.
  if (!performance.getEntriesByName("kitden:gateway-drawn").length) performance.mark("kitden:gateway-drawn");
  openArrival(view, model, mode).catch(reportError);
  return found;
}

// The Gateway as one tree, as the page shows it now: what Kitden read and the picked project, and
// on the map (`mode`) the tray's rows and a drag. The List shows what is set up, so its search
// finds only that.
function treeFor(view, mode = "map") {
  const onMapOnly = mode === "map" ? { rows: rowsOnMap(tray), ...movingOn() } : {};
  return gatewayTree(view, { setup: data.setupServer, clients: data.clients, held: liveHeld(view), picked: state.project, ...onMapOnly });
}

// The tray rows the map draws: none once their change is applied, as the page then reads the result
// and shows the servers as they are. A row with no part yet is drawn only while it is asked: after
// a refused preview it has none, and nothing is asked for it.
export function rowsOnMap(t) {
  if (t.phase === "applied") return [];
  return t.phase === "asking" ? t.rows : t.rows.filter((row) => row.part);
}

function noGateway() {
  const card = el("section", "card");
  card.append(el("h2", null, "No gateway yet"));
  card.append(el("p", "muted", "A gateway keeps your MCP servers in one place: each client needs one entry, and you turn tools on or off once."));
  card.append(addForm());
  entrance("gateway", [card]);
  return card;
}

// Map or List. The address keeps the choice (view=map|list), and Back switches back.
function modeSwitch(mode) {
  const seg = el("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show as");
  for (const [id, label] of [["map", "Map"], ["list", "List"]]) {
    const choice = button(label, () => go("gateway", { mode: id }), "");
    choice.setAttribute("aria-pressed", String(mode === id));
    choice.dataset.focus = `view:${id}`;
    seg.append(choice);
  }
  return seg;
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
// puts a preview block `preview:<name>` at the end of its group once its row has its part (the
// slot "Drop to add" while it is asked), joined to the gateway by a preview link; the outside row
// it moves hides its direct lines and its grip. A server taken out of the Kitden gateway, or a
// tool turned off in the scope shown, has its link drawn leaving. Each block and link a row draws
// names it (`row`, its key). While a server is dragged (`drop`, `{ name, kind }`, kind "remote"
// or "local") the slot opens in that group too.
export function gatewayTree(view, { setup, clients = [], held = new Map(), picked = "", rows = [], drop = null } = {}) {
  const { linked, off, known, setup: offers } = kitdenClients(setup);
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  const first = known && !linked.length && !off.length && Boolean(kitden) && !kitden.problem && !(kitden.servers || []).length;
  const blocks = [];
  const links = [];
  // What the moves put in the groups of the Kitden gateway, and the outside rows they take.
  const { adds, moved } = movesIn(view, kitden, rows, drop);
  for (const id of WRITABLE) blocks.push(clientBlock(id, { setup, linked, known, first, clients }));
  // A gateway block joined to the clients it `reaches` (null when not read), then its servers in
  // their groups; `server(block, word)` adds what each server's block says. `unread` says why
  // Kitden does not know what it holds, so no count shows: a problem is not an empty gateway.
  // `ends` are blocks for the end of a group (each `{ kind, block }`), which open that group if
  // need be.
  // A gateway block speaks no state word: it says where it runs and its clients and servers, or
  // what Kitden could not read, and then its state is not known.
  const addGateway = (gateway, reaches, servers, kindOf, server, unread = null, ends = []) => {
    const id = `gateway:${gateway.id}`;
    blocks.push({ id, column: "gateway", kind: "gateway", name: gatewayName(gateway), ...gatewayFace(gateway, reaches, servers, unread), state: unread ? "unk" : "on", stateInMeta: true, gateway, unread, ports: { left: true, right: true } });
    for (const client of reaches || []) links.push({ from: `client:${client}`, to: id, kind: "on" });
    for (const [kind, word, mark] of KINDS) {
      const mine = servers.filter((s) => kindOf(s) === kind);
      const last = ends.filter((end) => end.kind === kind).map((end) => end.block);
      if (!mine.length && !last.length) continue;
      const group = `group:${gateway.id}:${kind}`;
      blocks.push({ id: group, column: "servers", kind: "group", name: word, icon: mark, before: 3, under: id });
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
    addGateway(kitden, known ? linked : null, kitden.servers || [], (s) => s.kind, (block, word) => {
      kitdenServer(block, word, picked);
      for (const tool of block.server.tool_list || []) {
        const shown = toolBlock(block, tool, picked, waiting);
        tools.push(shown);
        if (shown.state === "on") links.push({ from: block.id, to: shown.id, kind: "on" });
      }
    }, kitden.problem ? "Could not read its settings." : null, adds);
    leaveParts(blocks, links, kitden, rows, picked);
  }
  for (const other of usedFirst(view, view.gateways.filter((g) => g.kind !== "kitden"))) {
    const per = view.connections[other.id] || {};
    const answer = held.get(other.id);
    // A server the gateway runs itself (uvx, npx, a container) is local to it.
    const kindOf = (s) => (heldKind(s) === "Hosted" ? "local" : "remote");
    // Not read yet, or not readable from here: no count, and a failed read says so.
    const unread = answer && answer.servers ? null : (answer && answer.error) || "";
    addGateway(other, WRITABLE.filter((c) => (per[c] || []).length), (answer && answer.servers) || [], kindOf, (block) => {
      block.meta = heldKind(block.server);
    }, unread);
  }
  blocks.push(...tools);
  const outside = OUTSIDE_GROUPS.flatMap((key) => (view.groups[key] || []).map((row) => [key, row]));
  if (outside.length) blocks.push({ id: "group:outside", column: "servers", kind: "group", name: OUTSIDE_MAP, icon: "info", h: OUTSIDE_H, before: 21, rowGap: 6 });
  for (const [key, row] of outside) {
    const id = `outside:${key}:${row.name}`;
    const columns = (row.columns || row.clients).filter((c) => WRITABLE.includes(c));
    const meta = `In ${joinWords(columns.map((c) => CLIENT_NAMES[c]))}`;
    const targets = movesTo(view, key, row);
    const move = targets.length > 0;
    const tag = picked && row.override ? ORIGIN_WORDS.override : null;
    // A drop moves into the Kitden gateway only, so a grip needs it; a move already in the tray
    // needs no second one.
    const grip = targets.some((g) => g.kind === "kitden") && !first && !moved.has(id);
    const state = row.unknown ? "unk" : "on";
    blocks.push({ id, column: "servers", parent: "group:outside", kind: "outside", name: row.name, meta, tag, state, lamp: "out", h: OUTSIDE_BLOCK_H, icon: OUTSIDE_ICONS[key], ports: { left: "out" }, row, groupKey: key, columns, move, grip });
    const line = row.unknown ? { kind: "direct", unk: true } : { kind: "direct" };
    if (!moved.has(id)) for (const client of columns) links.push({ from: `client:${client}`, to: id, ...line });
  }
  return { columns: GATEWAY_COLUMNS, blocks, links };
}

// A client's block: Connected or Not connected, and on a first run that it is found, with its
// version; the change that disconnects it (`disconnect`) where its link's × can (connectAction).
function clientBlock(id, { setup, linked, known, first, clients }) {
  const on = linked.includes(id);
  const found = (clients || []).find((c) => c.id === id && c.status === "found");
  // Without the setup read, a client is neither connected nor not.
  let meta = known ? (on ? "Connected" : "Not connected") : NOT_KNOWN;
  // Found lights the lamp; the state stays what the link shows: no gateway reached yet. A client
  // whose state Kitden does not know has no lamp: a grey one would say off.
  let lamp = known ? (on ? "on" : "off") : null;
  if (first && found) [meta, lamp] = [found.version ? `Found · ${found.version}` : "Found", "on"];
  const action = on ? connectAction(id, setup) : null;
  const disconnect = action && !action.connect ? action.body : null;
  return { id: `client:${id}`, column: "clients", kind: "client", name: CLIENT_NAMES[id], meta, lamp, state: known ? (on ? "on" : "off") : "unk", client: id, ports: { right: true }, disconnect };
}

// The moves into the Kitden gateway the map shows: each one in the tray (`rows`), for the outside
// rows whose entries it takes, then a drag (`drop`). Each puts a block at the end of its group of
// the gateway (`adds`, each `{ kind, block }`): the preview block once its row has its part, else
// the slot. `moved` holds the ids of the outside rows they take.
function movesIn(view, kitden, rows, drop) {
  const adds = [];
  const moved = new Set();
  const slot = (name) => ({ id: `slot:${name}`, column: "servers", kind: "slot", name: "Drop to add", stateInMeta: true, state: "preview" });
  // The outside row `name` of `group` ("move" or "local") goes in as `block`.
  const add = (group, name, block) => {
    moved.add(`outside:${group}:${name}`);
    if (!adds.some((other) => other.block.id === block.id)) adds.push({ kind: group === "local" ? "local" : "remote", block });
  };
  for (const row of rows) {
    const { action, targets = [], params = {} } = row.body;
    if (action !== "gateway.move" || !kitden || params.gateway !== kitden.id) continue;
    const items = new Set(targets.map((target) => target.item));
    for (const group of ["move", "local"]) {
      for (const each of view.groups[group] || []) {
        if (!each.items.length || !each.items.every((item) => items.has(item))) continue;
        const outside = `outside:${group}:${each.name}`;
        const look = { icon: SERVER_ICONS[group === "local" ? "local" : "remote"], lamp: "preview", ports: { left: true }, takeOut: IN_PREVIEW };
        add(group, each.name, row.part ? { id: `preview:${each.name}`, column: "servers", kind: "preview", name: each.name, meta: "Preview", stateInMeta: true, state: "preview", ...look, row: row.key, outside } : slot(each.name));
      }
    }
  }
  if (drop) add(drop.kind === "local" ? "local" : "move", drop.name, slot(drop.name));
  return { adds, moved };
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
      if (server) server.leaving = true;
    } else if (action === "gateway.rule" && params.state === "off" && (params.project || "") === (picked || "")) key = `held:${kitden.id}:${params.server}>tool:${params.server}/${params.tool}`;
    const link = key && links.find((l) => linkKey(l) === key);
    if (link) Object.assign(link, { leaving: true, row: row.key });
  }
}

// The tools whose rule waits in the tray, once its row has its part, by "server/tool": for the
// scope shown (`picked`, "" for all projects) their mark is a dashed ring until Apply (`ring`);
// for other projects the tool names them (`others`, the project ids).
function waitingTools(rows, picked) {
  const ring = new Set();
  const others = new Map();
  for (const row of rows) {
    const { action, params = {} } = row.body;
    if (!row.part || action !== "gateway.rule" || !params.tool) continue;
    const key = `${params.server}/${params.tool}`;
    if ((params.project || "") === (picked || "")) ring.add(key);
    else if (params.project) others.set(key, [...(others.get(key) || []), params.project]);
  }
  return { ring, others };
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
function kitdenServer(block, word, picked) {
  const server = block.server;
  const list = server.tool_list || [];
  block.state = server.state === "off" ? "off" : "on";
  block.onCount = list.length ? `${server.on_count} of ${list.length} on` : null;
  block.onIn = !picked && server.on_in ? `On in ${plural(server.on_in, "project", "projects")}` : null;
  block.meta = block.onIn || block.onCount || word;
  // "On in 2 projects" says the state itself; a lone On or Off beside it would contradict it.
  block.stateInMeta = Boolean(block.onIn);
  block.tag = heldTag(server, block.state === "on");
  block.count = server.tools;
  block.lamp = (list.length ? server.on_count > 0 : block.state === "on") ? "on" : "off";
  block.ports = { left: true, right: typeof block.count === "number" };
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
  if (pending) {
    const words = pending.length === 1 ? projectLabel(pending[0]) : plural(pending.length, "project", "projects");
    projects = { words, said: `in preview for ${words}`, own: true, pending: pending.length };
  }
  const lamp = waiting.ring.has(key) ? "preview" : on ? "on" : "off";
  return { id: `tool:${server.name}/${tool.name}`, column: "tools", parent: held.id, kind: "tool", name: tool.name, state: on ? "on" : "off", lamp, projects, ports: { left: true }, tool, server };
}

// The List's rows, in order, from the tree: a "Clients" group of client rows; each gateway's own
// row, then its Remote and Local group rows with its servers and, under an open server (`open`),
// its tools; then the group outside the gateway. A group or a gateway the person folded
// (`folded`) shows no rows under it. What the tray draws on the map (a preview block, the slot of
// a move) is no row of the List, and a group that holds only that has no row either. Each row:
// { id, parent, depth, kind, name, usedBy (client ids), tools ("3 of 4 on"), meta (quiet words
// after the name), action ("open" for ›, "move" for "Move in…"), tag, scope (a tool's own rule),
// state, said (the state word a screen reader hears for a server or tool, none where its words say
// it), expanded (only on a row that folds), group }.
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
  const group = (id, name, parent, depth, items, draw) => {
    const expanded = !folded.has(id);
    rows.push({ id, parent, depth, kind: "group", name, usedBy: [], tools: null, meta: null, action: null, tag: null, scope: null, group: true, expanded });
    if (expanded) items.forEach(draw);
  };
  group("group:clients", "Clients", null, 0, model.blocks.filter((b) => b.kind === "client"), (b) => row(b, "group:clients", 1, { meta: b.meta }));
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
      });
    }
  }
  const outside = model.blocks.find((b) => b.id === "group:outside");
  // An outside server no client is known to load says so; the others are on.
  const outsideRow = (b) => row(b, outside.id, 1, { usedBy: b.columns, action: b.move ? "move" : "open", meta: b.state === "unk" ? NOT_KNOWN : null });
  if (outside) group(outside.id, OUTSIDE, null, 0, children.get(outside.id) || [], outsideRow);
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

// "N more" (`more:group:<id>`) and a group (`group:<id>`) open the List at that group.
export function listAt(id) {
  return { mode: "list", selected: { kind: "group", name: id.replace(/^more:/, "").replace(/^group:/, "") } };
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
// for one that takes keyboard focus (newMap).
export function bringBeside(box, node) {
  if (!node || !floatingNow()) return;
  const by = besideBy(node.getBoundingClientRect().right, $("#drawer").offsetLeft);
  if (!by) return;
  box.classList.add("beside");
  box.scrollBy({ left: by, behavior: scrolls() });
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
// tree it shows, what the search found, and the box's width as last measured. Kept across redraws
// of one project.
const onMap = {
  project: null, open: new Set(), selected: null, view: null, model: null, found: null, width: null, narrow: false, watch: null,
  unfolds: false,
};

// What a selection lights: a link's key lights its two ends and itself, a client what it reaches,
// any other block every client's path to it and what it holds on (the gateway's servers, a server's
// tools). Nothing selected, or a selection the model no longer has, lights nothing.
export function litFor(model, selected) {
  if (!selected) return new Set();
  const link = model.links.find((l) => linkKey(l) === selected);
  if (link) return new Set([link.from, link.to, selected]);
  const block = model.blocks.find((b) => b.id === selected);
  if (!block) return new Set();
  if (block.kind === "client") return litFrom(model, block.id);
  const lit = litPath(model, block.id);
  for (const own of model.links.filter((l) => l.from === block.id && l.kind === "on")) {
    lit.add(own.to);
    lit.add(linkKey(own));
  }
  return lit;
}

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
function gatewayMap(main, model, found) {
  let fresh = false;
  let projectChanged = false;
  if (onMap.project !== state.project) {
    Object.assign(onMap, { project: state.project, open: new Set(), selected: null });
    projectChanged = true;
  }
  if (!onMap.view) {
    onMap.view = newMap();
    fresh = true;
  }
  main.append(onMap.view.box);
  // A new map knows its width before its first draw, so the observer's first report does not flip
  // it to narrow in the middle of its entrance.
  if (fresh) onMap.width = contentWidth(onMap.view.box) ?? onMap.width;
  Object.assign(onMap, { model, found });
  drawOnMap(model, { fresh, projectChanged });
}

// The blocks of a model by id. Every link asks, so it is built once for a model.
const indexes = new WeakMap();
function blocksById(model) {
  if (!indexes.has(model)) indexes.set(model, new Map(model.blocks.map((b) => [b.id, b])));
  return indexes.get(model);
}

// What the × of a link does, as `{ tip, body }` (`body` is the change to preview), or null where
// the map does not act on the link: a client disconnects from the Kitden gateway (not one a
// plugin connects: clientBlock), a server in the Kitden gateway comes out of it, and a tool of
// such a server turns off, for the picked project (`picked`, "" for all).
export function linkRemoval(model, link, picked) {
  const byId = blocksById(model);
  const from = byId.get(link.from);
  const to = byId.get(link.to);
  if (!from || !to) return null;
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

// The tray's change is being written or has just been: as in the bar, nothing can be added to it
// or taken out of it now.
const writing = () => tray.phase === "applying" || tray.phase === "applied";

// What the × of a link does, in words: a link the tray draws is taken out of it, and the map acts
// on the others as linkRemoval says. "" where it does not act on the link, and while the tray's
// change is written: the link then has no ×.
export function linkTip(model, link, picked) {
  if (writing()) return "";
  if (rowOfLink(model, link)) return TAKE_OUT;
  return linkRemoval(model, link, picked)?.tip ?? "";
}

// The × of a link: a link the tray draws, or whose change is in the tray already (still being
// asked), is taken out of it; any other the map acts on adds its change to the tray. Null where the
// map does not act on the link.
export function removeLink(model, link, picked) {
  const drawn = rowOfLink(model, link);
  if (drawn) return takeOutHere(model, drawn);
  const removal = linkRemoval(model, link, picked);
  if (!removal) return null;
  const key = keyFor(removal.body);
  return inTray(key) ? takeOut(key) : addToTray(removal.body, { icon: removalIcon(removal.body) });
}

// A press on a link: one the tray draws is taken out of it (D12); a second press on the link
// picked lets go of it; any other is picked and opens its Connection panel.
export function clickLink(model, link) {
  const key = rowOfLink(model, link);
  if (key) {
    takeOutHere(model, key).catch(reportError);
    return;
  }
  if (onMap.selected === linkKey(link)) letGoOnMap();
  else pickLink(linkKey(link));
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

// A row taken out on the map. A move's preview block and link go with it, so focus on either goes
// to the server outside the gateway that it would have moved. Nothing happens while the tray's
// change is written.
function takeOutHere(model, key) {
  if (writing()) return Promise.resolve();
  const box = onMap.view ? onMap.view.box : null;
  const shown = model.blocks.find((b) => b.row === key && b.outside);
  const focus = box && shown ? document.activeElement?.dataset?.focus : null;
  const taken = takeOut(key);
  const lost = Boolean(focus) && (focus === `block:${shown.id}` || focus.endsWith(`>${shown.id}`));
  if (lost) withFocusKey(box, `block:${shown.outside}`)?.focus({ preventScroll: true });
  return taken;
}

// The hooks of the links the map acts on (the model is the one drawn last): a link has a hit while
// its × does something.
const LINK_HOOKS = {
  canHit: (link) => Boolean(linkTip(onMap.model, link, state.project)),
  tip: (link) => linkTip(onMap.model, link, state.project),
  onClick: (link) => clickLink(onMap.model, link),
  onRemove: (link) => {
    const done = removeLink(onMap.model, link, state.project);
    if (done) done.catch(reportError);
  },
};

// A new map for this visit, with what its box listens to, once.
function newMap() {
  const view = mapView({
    tile,
    onOpen: openBlock,
    onSelect: (id) => pressBlock(onMap.model, id),
    onEmpty: letGoIfSelected,
    onHover: (id) => view.glance(glanceFor(onMap.model, id)),
    links: LINK_HOOKS,
  });
  // Escape clears the selection first; open Details then close too (panel.js).
  view.box.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !onMap.selected) return;
    onMap.selected = null;
    if (!isPanelOpen()) setState({ selected: null });
    drawAgain();
  });
  view.box.addEventListener("pointerdown", (event) => pressGrip(event, letGoIfSelected));
  view.box.addEventListener("scroll", () => {
    if (!view.box.scrollLeft && !floatingNow()) view.box.classList.remove("beside");
  }, { passive: true });
  // Keyboard focus never sits under floating Details (WCAG 2.4.11).
  view.box.addEventListener("focusin", (event) => bringBeside(view.box, event.target.closest("[data-focus]")));
  watchMap(view.box);
  return view;
}

// A press on a block that folds opens or folds it, before it is selected. `unfolds` says that the
// press opened it: what it holds comes in before the path of the selection lights.
function openBlock(id) {
  const { model } = onMap;
  onMap.open = pressOpen(model, onMap.open, onMap.found, id);
  onMap.unfolds = onMap.open.has(id);
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

// How a draw of the map shows: a new map enters (each block rises into its place), another
// project or a new width shows at once, and anything else moves what changed.
export function mapMotion({ fresh, projectChanged, narrowChanged }) {
  if (fresh) return "enter";
  return projectChanged || narrowChanged ? "none" : "move";
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

// Draw the map as it is now, as `mapMotion` says. With `lightLater` (a press that opened a block)
// the selection shows, but its path lights (the dims and the accent lines) when every motion of
// this draw has ended: a server's tools come in first. The promise ends with the last motion.
function drawOnMap(model, { fresh = false, projectChanged = false, lightLater = false } = {}) {
  const narrow = narrowNow(model);
  const flipped = narrow !== onMap.narrow;
  onMap.narrow = narrow;
  const open = openNow();
  const layout = layoutTree(model, { open, narrow });
  // A selected block lights every client's path to it; a selected client lights what it reaches; a
  // selected link its two ends. A selection the model no longer has is none.
  const lit = litFor(model, onMap.selected);
  const motion = mapMotion({ fresh, projectChanged, narrowChanged: flipped });
  const { view, selected } = onMap;
  const later = lightsLater({ unfolds: lightLater, lit });
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, lit: later ? new Set() : lit, found: onMap.found, open, motion });
  // A block a move took off its place stays where it is shown (gateway-drag.js).
  placeMoved({ view, model, layout });
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
  onMap.selected = null;
  if (isPanelOpen() && letGoCloses(panelState.current)) closePanel({ focus: false });
  else setState({ selected: null });
  drawAgain();
}

// A click on empty map, or the start of a drag, lets go of what is selected.
function letGoIfSelected() {
  if (onMap.selected) letGoOnMap();
}

// A press on a block (a held server opened or folded first, by onOpen). "N more" opens the List
// at its group, focused there, so Details close first. A second press on the selected block lets
// go. The first run's slot adds the change that sets every client up; the slot of a drag does
// nothing. A preview block takes its row out of the tray (D12). Any other block is selected.
export function pressBlock(model, id) {
  if (id.startsWith("more:")) {
    closePanel({ instant: true, focus: false });
    const { mode, selected } = listAt(id);
    goTo("gateway", selected, { mode }).catch(reportError);
    return;
  }
  const block = model.blocks.find((b) => b.id === id);
  if (!block) return;
  if (afterPress({ selected: onMap.selected, id, opened: foldable(model).has(id) && onMap.open.has(id) }) === "letGo") {
    letGoOnMap();
    return;
  }
  if (block.kind === "slot" && block.setup) review(block.setup, { note: SETUP_NOTE }).catch(reportError);
  else if (block.kind === "preview") takeOutHere(model, block.row).catch(reportError);
  else if (block.kind !== "slot" || block.gateway) selectOnMap(block);
}

// Select a block: the map lights it and is drawn again, then its Details open beside the page.
// The List takes the Tab key on the same row.
function selectOnMap(block) {
  // What a search opened to show it stays open, so the selection is still on the map when the
  // search ends.
  onMap.open = keepOpen(onMap.model, onMap.open, block);
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
onTray(trayChanged);

// The tray changed: the map draws its rows again in place, while it shows. Not while its change is
// applied: the page reads the result first and draws that. Once it has landed (the tray empties),
// focus it took away goes to the gateway block.
function trayChanged(t) {
  const landed = trayWas === "applied" && t.phase === "idle";
  trayWas = t.phase;
  if (t.phase === "applied") return;
  const drawn = drawRows();
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
  Object.assign(onMap, { model, found: state.q.trim() ? findIn(model, state.q) : null });
  return drawOnMap(model);
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
// own except outside the gateway, style.css). The slot of a drag shows nothing.
function tile(block) {
  if (block.kind === "client") return mark(block.client);
  if (GATEWAY_KINDS.includes(block.kind) && block.gateway) {
    if (block.gateway.kind !== "kitden") return mark("gateway");
    const house = el("img", "block-house");
    house.src = "/static/brand/kitden.svg";
    house.alt = "";
    return house;
  }
  if (!block.icon) return null;
  const holder = el("span", "block-icon");
  holder.append(icon(block.icon, 15));
  return holder;
}

// The List, a tree grid: the servers that show their tools (`open`), the groups and gateways the
// person folded, and the row that takes the Tab key, kept across redraws of one project.
const onList = { project: null, open: new Set(), folded: new Set(), current: null };

function gatewayList(main, view, model, found, { enter = false } = {}) {
  if (onList.project !== state.project) Object.assign(onList, { project: state.project, open: new Set(), current: null });
  const rows = findRows(model, found, onList.open, onList.folded);
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  if (!rows.some((r) => r.id === onList.current)) onList.current = rows.length ? rows[0].id : null;
  const chosen = selectedRow(rows, byId);
  const grid = el("div", found ? "treegrid finding" : "treegrid");
  grid.setAttribute("role", "treegrid");
  grid.setAttribute("aria-label", "Clients, gateways and MCP servers");
  const head = el("div", "tg-head");
  head.setAttribute("role", "row");
  for (const name of ["Name", "Used by", "Tools", "Action"]) {
    const cell = el("div", null, name);
    cell.setAttribute("role", "columnheader");
    head.append(cell);
  }
  grid.append(head);
  // A row a search showed stays shown when the search ends: what holds it unfolds for good.
  const press = { toggle: toggleRow, open: (row) => { unfoldAbove(model, row.id); openRow(row, byId.get(row.id)); } };
  for (const row of rows) grid.append(listRow(row, byId.get(row.id), { current: row.id === onList.current, selected: row.id === chosen, view, press }));
  // One row takes the Tab key; the arrows move between rows, Right and Left fold, Enter opens.
  // Keys on a row's own button stay that button's.
  grid.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || !event.target.dataset.row) return;
    const next = gridKey(rows, rows.findIndex((r) => r.id === event.target.dataset.row), event.key);
    if (!next) return;
    event.preventDefault();
    const row = rows[next.at];
    if (next.toggle) toggleRow(row);
    else if (next.details) press.open(row);
    else focusRow(grid, row.id);
  });
  main.append(grid);
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
    if (selected.kind === "tool") return row.id === `tool:${selected.name}`;
    return selected.kind === "client" && row.id === `client:${selected.name}`;
  });
  const own = matches.find((row) => row.id === onList.current);
  return (own || matches[0] || {}).id || null;
}

function cell(className, text) {
  const node = el("div", className, text);
  node.setAttribute("role", "gridcell");
  return node;
}

// One row: a fold mark where it folds, what it is (a client's tile, a gateway's mark, the dot of a
// server or tool, filled when on), its name, tags and quiet words; then the clients that use it,
// its tools, and › or "Move in…". A click opens its Details, or folds it on the fold mark; a
// group row folds.
function listRow(row, block, { current, selected, view, press }) {
  const node = el("div", row.group ? "tg-row group" : `tg-row ${row.kind}`);
  if (row.found) node.classList.add("found");
  node.setAttribute("role", "row");
  node.setAttribute("aria-level", String(row.depth + 1));
  if (row.expanded !== undefined) node.setAttribute("aria-expanded", String(row.expanded));
  node.setAttribute("aria-selected", String(selected));
  node.tabIndex = current ? 0 : -1;
  node.dataset.row = row.id;
  node.dataset.focus = `row:${row.id}`;
  const name = cell("tg-name");
  name.style.setProperty("--depth", String(row.depth));
  const caret = el("span", row.expanded === undefined ? "caret none" : "caret", "▸");
  caret.setAttribute("aria-hidden", "true");
  name.append(caret);
  if (row.kind === "client") name.append(mark(block.client));
  else if (GATEWAY_KINDS.includes(row.kind)) name.append(mark(block.gateway.kind === "kitden" ? "kitden" : "gateway"));
  else if (row.kind === "held" || row.kind === "tool") {
    const dot = el("span", row.state === "on" ? "tg-dot on" : "tg-dot");
    dot.setAttribute("aria-hidden", "true");
    name.append(dot);
  }
  const words = el("span", row.group ? "words" : "words mono", row.name);
  words.title = row.name;
  name.append(words);
  if (row.said) name.append(el("span", "sr-only", row.said));
  // A tool's tag says whether it reads or writes; an accent tag says a rule of this project.
  const accent = row.kind === "tool" ? row.scope : row.tag;
  if (accent) name.append(el("span", "tag", accent));
  if (row.kind === "tool" && row.tag) name.append(flag({ text: row.tag, level: "info" }));
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
  for (const node of grid.querySelectorAll("[data-row]")) {
    const on = node.dataset.row === id;
    node.tabIndex = on ? 0 : -1;
    for (const control of node.querySelectorAll("button")) control.tabIndex = on ? 0 : -1;
    if (on) node.focus();
  }
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

