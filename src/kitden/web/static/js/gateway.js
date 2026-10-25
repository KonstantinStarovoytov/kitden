// Gateway: the clients, the gateways and the MCP servers they reach, as a Map or a List. Each
// row opens its Details beside the page (gateway-details.js).
import { $, button, el, gridKey, joinWords, plural, reportError, withFocusKey } from "./dom.js";
import { addForm, heldServer, liveHeld, movesTo, ruleBody, SETUP_NOTE, showClient, showGateway, showHeld, showOutside, showTool } from "./gateway-details.js";
import { endedMove, movingOn, placeMoved, pressGrip } from "./gateway-drag.js";
import { leaveMap, mapReviewLeft, previewBar, redrawPreview, showMapReview } from "./map-review.js";
import { findIn, foldable, isNarrow, keepOpen, layoutTree, linkKey, litFrom, litPath, pressOpen, toggleOpen, wideWidth } from "./map.js";
import { mapView } from "./map-view.js";
import { afterOldPage, entrance, glide, rise, riseHead } from "./motion.js";
import { closePanel, isPanelOpen, moveInto, openInfo, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, folderName, gatewayName, kitdenClients, mark, opens, ORIGIN_WORDS, scopeBar, skeleton, STATE_WORDS, staleNote } from "./parts.js";
import { arrival, current, currentError, data, go, goTo, projectPath, render, retry, setState, state, takeArrival, toolSel, viewMode } from "./store.js";

// Overview sets a client up with the same note. A server the Kitden gateway holds, and its
// links, are found where its Details are drawn.
export { heldServer, kitdenLinks, SETUP_NOTE } from "./gateway-details.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
const OUTSIDE = "Outside the gateway · calls skip Kitden's rules";
// On the map these words take two lines in their column, and an outside server's block is 50 high.
const OUTSIDE_H = 36;
const OUTSIDE_BLOCK_H = 50;
// The groups of servers outside the gateway in /api/gateway-view, in the order the page lists them.
const OUTSIDE_GROUPS = ["move", "local", "plugin"];
// The icon of a server outside the gateway, by its group.
const OUTSIDE_ICONS = { move: "remote", local: "local", plugin: "plugin" };
// A gateway's own groups, each with the icon of its caption.
const KINDS = [["remote", "Remote", "cloud"], ["local", "Local", "hard-drive"]];
// A gateway's block, or on a first run the slot of the Kitden gateway.
const GATEWAY_KINDS = ["gateway", "slot"];
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
  // A preview started on the map lives there: the List leaves one that is only previewed.
  if (mode !== "map") leaveMap();
  const seg = modeSwitch(mode);
  head.append(seg);
  const model = gatewayTree(view, { setup: data.setupServer, clients: data.clients, held: liveHeld(view), picked: state.project, ...movingOn() });
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
// Narrow, the gateway is a small tile and tools are rows inside their server.
export const GATEWAY_COLUMNS = [
  { id: "clients", caption: "Clients", w: 150, h: 54, top: 124, rowGap: 18, narrowW: 140 },
  { id: "gateway", caption: "Gateway", w: 150, h: 124, colGap: 46, top: 124, rowGap: 18, narrowW: 56, narrowH: 56 },
  { id: "servers", caption: "Servers", w: 170, h: 60, colGap: 50, top: 58, rowGap: 10, narrowW: 220, narrowH: 54 },
  { id: "tools", caption: "Tools", w: 200, h: 34, colGap: 70, narrowH: 30 },
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
// A move started on the map (S.8, 4.6) is `{ name, kind }` (kind "remote" or "local"): while it is
// dragged or prepared (`drop`) the slot "Drop to add" opens in that group of the Kitden gateway,
// and while its preview shows (`preview`) a preview block `preview:<name>` stands there; either
// way a preview link joins it to the gateway, the outside row it moves hides its direct lines,
// and no block has a grip: one preview at a time.
export function gatewayTree(view, { setup, clients = [], held = new Map(), picked = "", preview = null, drop = null } = {}) {
  const { linked, off, known, setup: offers } = kitdenClients(setup);
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  const first = known && !linked.length && !off.length && Boolean(kitden) && !kitden.problem && !(kitden.servers || []).length;
  const blocks = [];
  const links = [];
  const moving = preview || drop;
  // What the move puts in its group of the Kitden gateway.
  let extra = null;
  if (preview) extra = { id: `preview:${preview.name}`, column: "servers", kind: "preview", name: preview.name, meta: "Preview", stateInMeta: true, state: "preview", icon: preview.kind };
  else if (drop) extra = { id: `slot:${drop.name}`, column: "servers", kind: "slot", name: "Drop to add", stateInMeta: true, state: "preview" };
  for (const id of WRITABLE) {
    const on = linked.includes(id);
    const found = (clients || []).find((c) => c.id === id && c.status === "found");
    // Without the setup read, a client is neither connected nor not.
    let meta = known ? (on ? "Connected" : "Not connected") : NOT_KNOWN;
    // Found lights the dot; the state stays what the link shows: no gateway reached yet.
    let dot = null;
    if (first && found) [meta, dot] = [found.version ? `Found · ${found.version}` : "Found", "on"];
    blocks.push({ id: `client:${id}`, column: "clients", kind: "client", name: CLIENT_NAMES[id], meta, dot, state: known ? (on ? "on" : "off") : "unk", client: id });
  }
  // A gateway block joined to the clients it `reaches` (null when not read), then its servers in
  // their groups; `server(block, word)` adds what each server's block says. `unread` says why
  // Kitden does not know what it holds, so no count shows: a problem is not an empty gateway.
  // `adds` is a block for the end of one group (`adds.kind`), which opens that group if need be.
  // A gateway block speaks no state word: its meta says its clients and servers, or what Kitden
  // could not read, and then its state is not known.
  const addGateway = (gateway, reaches, servers, kindOf, server, unread = null, adds = null) => {
    const id = `gateway:${gateway.id}`;
    const n = plural(servers.length, "server", "servers");
    const counts = reaches ? `${plural(reaches.length, "client", "clients")} · ${n}` : n;
    blocks.push({ id, column: "gateway", kind: "gateway", name: gatewayName(gateway), meta: unread === null ? counts : unread || null, state: unread ? "unk" : "on", stateInMeta: true, gateway, unread });
    for (const client of reaches || []) links.push({ from: `client:${client}`, to: id, kind: "on" });
    for (const [kind, word, mark] of KINDS) {
      const mine = servers.filter((s) => kindOf(s) === kind);
      const end = adds && adds.kind === kind ? adds.block : null;
      if (!mine.length && !end) continue;
      const group = `group:${gateway.id}:${kind}`;
      blocks.push({ id: group, column: "servers", kind: "group", name: word, icon: mark, before: 3, under: id });
      for (const each of mine) {
        const block = { id: `held:${gateway.id}:${each.name}`, column: "servers", parent: group, kind: "held", name: each.name, state: "on", icon: kind, server: each, gateway };
        server(block, word);
        blocks.push(block);
        if (block.state === "on") links.push({ from: id, to: block.id, kind: "on" });
      }
      if (end) {
        blocks.push({ ...end, parent: group });
        links.push({ from: id, to: end.id, kind: "preview" });
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
    addGateway(kitden, known ? linked : null, kitden.servers || [], (s) => s.kind, (block, word) => {
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
      for (const tool of list) {
        // `effective` counts the server's switch too: a tool of a server that is off is off.
        const on = (tool.effective ?? tool.state) === "on";
        const id = `tool:${server.name}/${tool.name}`;
        tools.push({ id, column: "tools", parent: block.id, kind: "tool", name: tool.name, state: on ? "on" : "off", tag: tool.origin === "project" ? ORIGIN_WORDS.override : null, tool, server });
        if (on) links.push({ from: block.id, to: id, kind: "on" });
      }
    }, kitden.problem ? "Could not read its settings." : null, extra && { kind: moving.kind, block: extra });
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
  const rows = OUTSIDE_GROUPS.flatMap((key) => (view.groups[key] || []).map((row) => [key, row]));
  if (rows.length) blocks.push({ id: "group:outside", column: "servers", kind: "group", name: OUTSIDE, icon: "info", h: OUTSIDE_H, before: 21, rowGap: 6 });
  // The outside row a move on the map takes.
  const moved = moving ? `outside:${moving.kind === "local" ? "local" : "move"}:${moving.name}` : null;
  for (const [key, row] of rows) {
    const id = `outside:${key}:${row.name}`;
    const columns = (row.columns || row.clients).filter((c) => WRITABLE.includes(c));
    const meta = `In ${joinWords(columns.map((c) => CLIENT_NAMES[c]))}`;
    const targets = movesTo(view, key, row);
    const move = targets.length > 0;
    const tag = picked && row.override ? ORIGIN_WORDS.override : null;
    // A drop moves into the Kitden gateway only, so a grip needs it.
    const grip = targets.some((g) => g.kind === "kitden") && !first && !moving;
    const state = row.unknown ? "unk" : "on";
    blocks.push({ id, column: "servers", parent: "group:outside", kind: "outside", name: row.name, meta, tag, state, h: OUTSIDE_BLOCK_H, icon: OUTSIDE_ICONS[key], row, groupKey: key, columns, move, grip });
    const line = row.unknown ? { kind: "direct", unk: true } : { kind: "direct" };
    if (id !== moved) for (const client of columns) links.push({ from: `client:${client}`, to: id, ...line });
  }
  return { columns: GATEWAY_COLUMNS, blocks, links };
}

// The List's rows, in order, from the tree: a "Clients" group of client rows; each gateway's own
// row, then its Remote and Local group rows with its servers and, under an open server (`open`),
// its tools; then the group outside the gateway. A group or a gateway the person folded
// (`folded`) shows no rows under it. Each row: { id, parent, depth, kind, name, usedBy (client
// ids), tools ("3 of 4 on"), meta (quiet words after the name), action ("open" for ›, "move" for
// "Move in…"), tag, scope (a tool's own rule), state, said (the state word a screen reader hears
// for a server or tool, none where its words say it), expanded (only on a row that folds), group }.
export function listRows(model, open = new Set(), folded = new Set()) {
  const rows = [];
  const children = new Map();
  for (const block of model.blocks) {
    if (!block.parent) continue;
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
  for (const gateway of model.blocks.filter((b) => GATEWAY_KINDS.includes(b.kind))) {
    const groups = model.blocks.filter((b) => b.kind === "group" && b.under === gateway.id);
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
        if (opened) for (const t of tools) row(t, server.id, 3, { tag: HINT_TAGS[t.tool.hint] || null, scope: t.tag || null });
      });
    }
  }
  const outside = model.blocks.find((b) => b.id === "group:outside");
  // An outside server no client is known to load says so; the others are on.
  const outsideRow = (b) => row(b, outside.id, 1, { usedBy: b.columns, action: b.move ? "move" : "open", meta: b.state === "unk" ? NOT_KNOWN : null });
  if (outside) group(outside.id, outside.name, null, 0, children.get(outside.id) || [], outsideRow);
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

// The map lays out narrow by the window rule (isNarrow: under 1024 px, or under 1280 px with
// Details beside the page), and also when its box (null before it is measured) is too small for
// the wide map, so it never needs to scroll sideways where the narrow one fits.
export function narrowFor(model, { window: width, box = null, docked = false }) {
  return isNarrow(width, docked) || (box !== null && box < wideWidth(model));
}

// The map: the blocks open and the one selected, its view (map-view.js, one per visit) and the
// tree it shows, what the search found, and the box's width as last measured. Kept across redraws
// of one project. What the map showed of a move started on it (`shows`; the move is
// gateway-drag.js's).
const onMap = {
  project: null, open: new Set(), selected: null, view: null, model: null, found: null, width: null, narrow: false, watch: null,
  shows: "", unfolds: false,
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
  Object.assign(onMap, { model, found, shows: JSON.stringify(movingOn()) });
  drawOnMap(model, { fresh, projectChanged });
  const bar = previewBar(redrawMove);
  if (bar) main.append(bar);
}

// What the × of a link does, as `{ tip, body }` (`body` is the change to preview), or null where
// the map does not act on the link: a server in the Kitden gateway comes out of it, and a tool of
// such a server turns off, for the picked project (`picked`, "" for all).
export function linkRemoval(model, link, picked) {
  const from = model.blocks.find((b) => b.id === link.from);
  const to = model.blocks.find((b) => b.id === link.to);
  if (!from || !to || !from.gateway || from.gateway.kind !== "kitden") return null;
  if (from.kind === "gateway" && to.kind === "held") {
    return { tip: `Remove ${to.name} from the gateway`, body: { action: "gateway.remove", targets: [], params: { server: to.name } } };
  }
  if (from.kind === "held" && to.kind === "tool") {
    return { tip: `Turn off ${to.name}`, body: ruleBody(from.name, to.name, "off", picked || null) };
  }
  return null;
}

// The hooks of the links the map acts on (the model is the one drawn last). A press on a link
// selects it and opens the Details of its far block, until a link has a panel of its own.
const LINK_HOOKS = {
  canHit: (link) => Boolean(linkRemoval(onMap.model, link, state.project)),
  tip: (link) => linkRemoval(onMap.model, link, state.project)?.tip ?? "",
  onClick: (link) => {
    const far = onMap.model.blocks.find((b) => b.id === link.to);
    if (far) selectOnMap(far, linkKey(link));
  },
  onRemove: (link) => {
    const removal = linkRemoval(onMap.model, link, state.project);
    if (removal) review(removal.body).catch(reportError);
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

// A new width of the box (the window, or Details beside the page) may change the layout: it is
// drawn again, at once in its new shape. Details closing (Escape, Close or
// another place) clears what the map lights; the panel's class says when it closes. A preview
// shown in Details ends on the map when its review leaves there without Apply.
function watchMap(box) {
  if (!onMap.watch) {
    onMap.watch = new ResizeObserver((entries) => {
      const entry = entries[entries.length - 1];
      if (!entry.target.isConnected) return;
      onMap.width = entry.contentRect.width;
      if (narrowNow(onMap.model) !== onMap.narrow) drawAgain();
    });
    new MutationObserver(() => {
      if (mapReviewLeft()) {
        redrawMove();
        return;
      }
      if (isPanelOpen() || !onMap.selected) return;
      onMap.selected = null;
      drawAgain();
    }).observe($("#drawer"), { attributes: true, attributeFilter: ["class"], childList: true });
  }
  onMap.watch.disconnect();
  onMap.watch.observe(box);
}

function narrowNow(model) {
  const docked = isPanelOpen() && $(".shell").classList.contains("docked");
  return narrowFor(model, { window: innerWidth, box: onMap.width, docked });
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

// Draw the map as it is now, as `mapMotion` says. With `lightLater` the selection shows, but its
// path lights (the dims and the accent lines) when every motion of this draw has ended: a server's
// tools come in first. The promise ends with the last motion.
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
  const drawn = view.draw(model, layout, { selected: lit.size ? selected : null, lit: lightLater ? new Set() : lit, found: onMap.found, open, motion });
  // A block a move took off its place stays where it is shown (gateway-drag.js).
  placeMoved({ view, model, layout, redraw: redrawMove });
  if (lightLater && lit.size) drawn.then(() => onMap.view === view && onMap.selected === selected && drawAgain());
  return drawn;
}

// Draw the map again in place; its blocks keep their nodes, so focus stays where it is.
function drawAgain(options) {
  const { view, model } = onMap;
  if (!view || !view.box.isConnected) return Promise.resolve();
  return drawOnMap(model, options);
}

// Let go of the selection: the map shows none and Details close. Focus stays where it is.
function letGoOnMap() {
  onMap.selected = null;
  if (isPanelOpen()) closePanel({ focus: false });
  else setState({ selected: null });
  drawAgain();
}

// A click on empty map, or the start of a drag, lets go of what is selected.
function letGoIfSelected() {
  if (onMap.selected) letGoOnMap();
}

// A press on a block (a held server opened or folded first, by onOpen). "N more" opens the List
// at its group, focused there, so Details close first. A second press on the selected block lets
// go. The first run's slot opens the review that sets every client up; the slot of a drag does
// nothing. A preview opens its full review in Details, as "Show changes" does. Any other block is
// selected.
function pressBlock(model, id) {
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
  else if (block.kind === "preview") showMapReview(redrawMove);
  else if (block.kind !== "slot" || block.gateway) selectOnMap(block);
}

// Select a block: the map lights it and is drawn again, then its Details open beside the page.
// The List takes the Tab key on the same row. A press on a link selects it (`selected` is its key)
// and opens the Details of its far block.
function selectOnMap(block, selected = block.id) {
  // What a search opened to show it stays open, so the selection is still on the map when the
  // search ends.
  onMap.open = keepOpen(onMap.model, onMap.open, block);
  onMap.selected = selected;
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

// The page drawn again for the preview of a move on the map (map-review.js and the drag call it).
// Only the bar changes while the map shows the same of the move as when it was drawn. A move that
// ended gives focus to its server where it is now: in the gateway after Apply, outside after
// Cancel.
function redrawMove() {
  const ended = endedMove();
  const same = !ended && JSON.stringify(movingOn()) === onMap.shows;
  redrawPreview(redrawMove, { same, ended: ended ? [`held:kitden:${ended.name}`, ended.id] : [] });
}

const SVG = "http://www.w3.org/2000/svg";
// Small line icons on a 16-unit grid, in the text color: a remote server (a globe), a local one
// (a terminal) and one that comes with a plugin (a box).
const ICONS = {
  remote: "M8 1.75a6.25 6.25 0 1 0 0 12.5a6.25 6.25 0 1 0 0-12.5M1.75 8h12.5M8 1.75c-2.2 2.4-2.2 10.1 0 12.5M8 1.75c2.2 2.4 2.2 10.1 0 12.5",
  local: "M1.75 3.25h12.5v9.5H1.75zM4.5 6.25l2 1.75-2 1.75M8 10h3.5",
  plugin: "M8 1.75l5.5 3v6.5L8 14.25l-5.5-3v-6.5zM2.5 4.75L8 7.75l5.5-3M8 7.75v6.5",
};

function icon(name) {
  const svg = document.createElementNS(SVG, "svg");
  for (const [key, value] of Object.entries({ viewBox: "0 0 16 16", width: "16", height: "16", fill: "none", stroke: "currentColor", "stroke-width": "1.3", "stroke-linecap": "round", "stroke-linejoin": "round" })) svg.setAttribute(key, value);
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", ICONS[name] || ICONS.remote);
  svg.append(path);
  const holder = el("span", "block-icon");
  holder.append(svg);
  return holder;
}

// What a block shows before its name: a client's tile, the Kitden house (it keeps its own color),
// a registered gateway's mark, or what kind of server it is. The slot of a drag shows nothing.
function tile(block) {
  if (block.kind === "client") return mark(block.client);
  if (GATEWAY_KINDS.includes(block.kind) && block.gateway) {
    if (block.gateway.kind !== "kitden") return mark("gateway");
    const house = el("img", "block-house");
    house.src = "/static/brand/kitden.svg";
    house.alt = "";
    return house;
  }
  return block.icon ? icon(block.icon) : null;
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

