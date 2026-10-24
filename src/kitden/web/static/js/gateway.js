// Gateway: the clients, the gateways and the MCP servers they reach, as a Map or a List. Each
// row opens its Details beside the page (gateway-details.js).
import { $, button, el, gridKey, joinWords, plural, reportError, withFocusKey } from "./dom.js";
import { addForm, foundClients, liveHeld, movesTo, showClient, showGateway, showOutside } from "./gateway-details.js";
import { drawMap, layoutTree, toggleOpen } from "./map.js";
import { entrance, glide, reducedMotion } from "./motion.js";
import { closePanel, contextLinks, heldActions, heldButtons, isPanelOpen, keepFrom, linksRow, moveInto, openInfo, toolsSection } from "./panel.js";
import { banner, CLIENT_NAMES, flag, folderName, gatewayName, kitdenClients, mark, opens, ORIGIN_WORDS, scopeBar, skeleton, STATE_WORDS, staleNote, toolsNode } from "./parts.js";
import { current, currentError, data, go, projectPath, render, retry, setState, state, takeArrival, toolSel, viewMode } from "./store.js";

// Overview sets a client up with the same note.
export { SETUP_NOTE } from "./gateway-details.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
const OUTSIDE = "Outside the gateway · calls skip Kitden's rules";
// The groups of servers outside the gateway in /api/gateway-view, in the order the page lists them.
const OUTSIDE_GROUPS = ["move", "local", "plugin"];
// A gateway's own groups.
const KINDS = [["remote", "Remote"], ["local", "Local"]];
// A tool's row says "Read" or "Write" only when the server says so; a guess from its name says
// "May write".
const HINT_TAGS = { reads: "Read", writes: "Write", "may write": "May write" };

// A selected MCP server that the Kitden gateway holds, or null.
export function heldServer(model, selected) {
  if (!model || !selected || selected.kind !== "mcp_server") return null;
  const kitden = model.gateways.find((g) => g.kind === "kitden");
  return ((kitden && kitden.servers) || []).find((s) => s.name === selected.name) || null;
}

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

export function renderGateway(main) {
  const head = el("div", "page-head");
  head.append(el("h1", null, "Gateway"));
  main.append(head, el("p", "lede", "Connect your agents. Shape what they can use."));
  const view = current("gateway");
  if (!view) {
    if (currentError("gateway")) main.append(banner("the gateway", retry));
    else main.append(skeleton("card", 2));
    return;
  }
  // Under the head: what the page shows, the shared setup or a project's rules that differ from it.
  main.append(scopeBar(folderName(projectPath()), view.own_rules));
  if (currentError("gateway")) main.append(staleNote(data.readAt.gateway));
  // Only without any gateway, the Kitden one included (no home folder to change).
  if (!view.gateways.length) {
    main.append(noGateway());
    return;
  }
  const mode = viewMode(state, serverCount(view));
  const seg = modeSwitch(mode);
  head.append(seg);
  const model = gatewayTree(view, { setup: data.setupServer, clients: data.clients, held: liveHeld(view), picked: state.project });
  if (mode === "map") gatewayMap(main, model);
  else gatewayList(main, view, model);
  glide(seg, seg.querySelector('[aria-pressed="true"]'), "gateway-view");
  // A performance mark for the map probe (Part 4.1): the first time the page draws with data.
  if (!performance.getEntriesByName("kitden:gateway-drawn").length) performance.mark("kitden:gateway-drawn");
  openArrival(view, model, mode).catch(reportError);
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
// wide and narrow. Narrow, the gateway is a small tile and tools are rows inside their server.
export const GATEWAY_COLUMNS = [
  { id: "clients", w: 150, h: 54, narrowW: 132 },
  { id: "gateway", w: 150, h: 124, narrowW: 56, narrowH: 56 },
  { id: "servers", w: 170, h: 54, narrowW: 220 },
  { id: "tools", w: 190, h: 34, narrowH: 30 },
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

// A held server's tag in a project view: "Only this project" when only this project turns it on,
// "This project" for any other rule of its own.
function heldTag(server, on) {
  if (server.origin !== "project") return null;
  return on && server.differs ? ORIGIN_WORDS.project : ORIGIN_WORDS.override;
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
// - the servers outside every gateway, each joined to each client that has it by a direct line.
// `picked` is the picked project ("" for All projects).
export function gatewayTree(view, { setup, held = new Map(), picked = "" } = {}) {
  const { linked, known } = kitdenClients(setup);
  const blocks = [];
  const links = [];
  for (const id of WRITABLE) {
    const on = linked.includes(id);
    // Without the setup read, a client is neither connected nor not.
    const meta = known ? (on ? "Connected" : "Not connected") : "Not known";
    blocks.push({ id: `client:${id}`, column: "clients", kind: "client", name: CLIENT_NAMES[id], meta, state: known ? (on ? "on" : "off") : "unk", client: id });
  }
  // A gateway block joined to the clients it `reaches`, then its servers in their groups;
  // `server(block, word)` adds what each server's block says. `unread` says why Kitden does not
  // know what it holds, so no count shows: a problem is not an empty gateway.
  const addGateway = (gateway, reaches, servers, kindOf, server, unread = null) => {
    const id = `gateway:${gateway.id}`;
    blocks.push({ id, column: "gateway", kind: "gateway", name: gatewayName(gateway), state: "on", gateway, unread });
    for (const client of reaches) links.push({ from: `client:${client}`, to: id, kind: "on" });
    for (const [kind, word] of KINDS) {
      const mine = servers.filter((s) => kindOf(s) === kind);
      if (!mine.length) continue;
      const group = `group:${gateway.id}:${kind}`;
      blocks.push({ id: group, column: "servers", kind: "group", name: word, under: id });
      for (const each of mine) {
        const block = { id: `held:${gateway.id}:${each.name}`, column: "servers", parent: group, kind: "held", name: each.name, state: "on", server: each, gateway };
        server(block, word);
        blocks.push(block);
        if (block.state === "on") links.push({ from: id, to: block.id, kind: "on" });
      }
    }
  };
  const tools = [];
  const kitden = view.gateways.find((g) => g.kind === "kitden");
  if (kitden) {
    addGateway(kitden, linked, kitden.servers || [], (s) => s.kind, (block, word) => {
      const server = block.server;
      const list = server.tool_list || [];
      block.state = server.state === "off" ? "off" : "on";
      block.onCount = list.length ? `${server.on_count} of ${list.length} on` : null;
      block.onIn = !picked && server.on_in ? `On in ${plural(server.on_in, "project", "projects")}` : null;
      block.meta = block.onIn || block.onCount || word;
      block.tag = heldTag(server, block.state === "on");
      block.count = server.tools;
      for (const tool of list) {
        // `effective` counts the server's switch too: a tool of a server that is off is off.
        const on = (tool.effective ?? tool.state) === "on";
        const id = `tool:${server.name}/${tool.name}`;
        tools.push({ id, column: "tools", parent: block.id, kind: "tool", name: tool.name, state: on ? "on" : "off", tag: tool.origin === "project" ? ORIGIN_WORDS.override : null, tool, server });
        if (on) links.push({ from: block.id, to: id, kind: "on" });
      }
    }, kitden.problem ? "Could not read its settings." : null);
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
  if (rows.length) blocks.push({ id: "group:outside", column: "servers", kind: "group", name: OUTSIDE });
  for (const [key, row] of rows) {
    const id = `outside:${key}:${row.name}`;
    const columns = (row.columns || row.clients).filter((c) => WRITABLE.includes(c));
    const meta = `In ${joinWords(columns.map((c) => CLIENT_NAMES[c]))}`;
    blocks.push({ id, column: "servers", parent: "group:outside", kind: "outside", name: row.name, meta, state: "on", row, groupKey: key, columns, move: movesTo(view, key, row).length > 0 });
    for (const client of columns) links.push({ from: `client:${client}`, to: id, kind: "direct" });
  }
  return { columns: GATEWAY_COLUMNS, blocks, links };
}

// The List's rows, in order, from the tree: a "Clients" group of client rows; each gateway's own
// row, then its Remote and Local group rows with its servers and, under an open server (`open`),
// its tools; then the group outside the gateway. A group or a gateway the person folded
// (`folded`) shows no rows under it. Each row: { id, parent, depth, kind, name, usedBy (client
// ids), tools ("3 of 4 on"), meta (quiet words after the name), action ("open" for ›, "move" for
// "Move in…"), tag, scope (a tool's own rule), state, expanded (only on a row that folds), group }.
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
    rows.push({ id: block.id, parent, depth, kind: block.kind, name: block.name, usedBy: [], tools: null, meta: null, action: "open", tag: block.tag || null, scope: null, state: block.state, group: false, ...fields });
  };
  const group = (id, name, parent, depth, items, draw) => {
    const expanded = !folded.has(id);
    rows.push({ id, parent, depth, kind: "group", name, usedBy: [], tools: null, meta: null, action: null, tag: null, scope: null, group: true, expanded });
    if (expanded) items.forEach(draw);
  };
  group("group:clients", "Clients", null, 0, model.blocks.filter((b) => b.kind === "client"), (b) => row(b, "group:clients", 1, { meta: b.meta }));
  for (const gateway of model.blocks.filter((b) => b.kind === "gateway")) {
    const groups = model.blocks.filter((b) => b.kind === "group" && b.under === gateway.id);
    const linked = reaches(gateway.id);
    const count = groups.reduce((n, g) => n + (children.get(g.id) || []).length, 0);
    const expanded = groups.length ? !folded.has(gateway.id) : undefined;
    // What it holds, or why Kitden does not know ("" while a live read runs: nothing to say).
    const meta = gateway.unread === null ? plural(count, "server", "servers") : gateway.unread || null;
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
  if (outside) group(outside.id, outside.name, null, 0, children.get(outside.id) || [], (b) => row(b, outside.id, 1, { usedBy: b.columns, action: b.move ? "move" : "open" }));
  return rows;
}

// The map at #gateway?view=map, the probe of Part 4.1: what is open and the links drawn already.
// A held server opens on a click; its tools are in the tree already.
const onMap = { project: null, open: new Set(), drawn: new Set() };

function gatewayMap(main, model) {
  if (onMap.project !== state.project) Object.assign(onMap, { project: state.project, open: new Set() });
  const layout = layoutTree(model, { open: onMap.open, width: innerWidth });
  const box = el("div");
  main.append(box);
  drawMap(box, model, layout, { onOpen: (id) => openOnMap(model, id), drawn: onMap.drawn, reduced: reducedMotion.matches });
}

function openOnMap(model, id) {
  const block = model.blocks.find((b) => b.id === id);
  if (!block || block.kind !== "held") return;
  onMap.open = toggleOpen(model, onMap.open, id);
  render();
}

// The List, a tree grid: the servers that show their tools (`open`), the groups and gateways the
// person folded, and the row that takes the Tab key, kept across redraws of one project.
const onList = { project: null, open: new Set(), folded: new Set(), current: null };

function gatewayList(main, view, model) {
  if (onList.project !== state.project) Object.assign(onList, { project: state.project, open: new Set(), current: null });
  const rows = listRows(model, onList.open, onList.folded);
  const byId = new Map(model.blocks.map((block) => [block.id, block]));
  if (!rows.some((r) => r.id === onList.current)) onList.current = rows.length ? rows[0].id : null;
  const chosen = selectedRow(rows, byId);
  const grid = el("div", "treegrid");
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
  const press = { toggle: toggleRow, open: (row) => openRow(row, byId.get(row.id)) };
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
  entrance("gateway", [grid]);
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
  else if (row.kind === "gateway") name.append(mark(block.gateway.kind === "kitden" ? "kitden" : "gateway"));
  else if (row.kind === "held" || row.kind === "tool") {
    const dot = el("span", row.state === "on" ? "tg-dot on" : "tg-dot");
    dot.setAttribute("aria-hidden", "true");
    name.append(dot);
  }
  const words = el("span", row.group ? "words" : "words mono", row.name);
  words.title = row.name;
  name.append(words);
  if (row.kind === "held" || row.kind === "tool") name.append(el("span", "sr-only", row.state === "on" ? STATE_WORDS.on : STATE_WORDS.off));
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
  const set = row.kind === "held" ? onList.open : onList.folded;
  if (set.has(row.id)) set.delete(row.id);
  else set.add(row.id);
  onList.current = row.id;
  render();
}

// A row's Details, beside the page. A server, a tool or a client goes into the address; a
// gateway does not.
function openRow(row, block) {
  onList.current = row.id;
  for (const node of document.querySelectorAll(".treegrid [data-row]")) node.setAttribute("aria-selected", String(node.dataset.row === row.id && row.kind !== "gateway"));
  if (row.kind === "client") {
    setState({ selected: { kind: "client", name: block.client } });
    showClient(block.client);
  } else if (row.kind === "gateway") {
    setState({ selected: null });
    showGateway(block.gateway.id);
  } else if (row.kind === "held") {
    if (block.gateway.kind === "kitden") showKitdenServer(block.server);
    else showHeld(block.server, block.gateway);
  } else if (row.kind === "tool") {
    showKitdenServer(block.server, { focus: `tool:${block.name}` });
    setState({ selected: { kind: "tool", name: `${block.server.name}/${block.name}` } });
  } else if (row.kind === "outside") showOutside(block.groupKey, block.name).catch(reportError);
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

// Show a row in the List and focus it, so its Details open from it and Escape comes back to it:
// every row above it unfolds (and a group itself with `unfold`).
function showRow(model, id, { unfold = false } = {}) {
  for (const above of rowsAbove(model, id)) {
    onList.folded.delete(above);
    if (above.startsWith("held:")) onList.open.add(above);
  }
  if (unfold) onList.folded.delete(id);
  onList.current = id;
  render();
  const node = withFocusKey($("#main"), `row:${id}`);
  if (node) node.focus();
}

async function openArrival(view, model, mode) {
  const found = await arrivalServer(view);
  if (!found) return;
  const listed = mode === "list";
  if (found.held) {
    const name = found.held.name;
    if (listed) showRow(model, found.tool ? `tool:${name}/${found.tool}` : `held:kitden:${name}`);
    showKitdenServer(found.held, found.tool ? { focus: `tool:${found.tool}` } : {});
    if (found.tool) setState({ selected: { kind: "tool", name: `${name}/${found.tool}` } });
  } else if (found.outside) {
    if (listed) showRow(model, `outside:${found.group}:${found.outside.name}`);
    await showOutside(found.group, found.outside.name);
  } else if (listed && found.client) showRow(model, `client:${found.client}`);
  else if (listed && found.group) showRow(model, `group:${found.group}`, { unfold: true });
}

// Details of a server a registered gateway holds: what it is and where it is set. The address
// stays behind Details, as on the other lists.
function showHeld(server, gateway) {
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

// The links in the Kitden gateway's own panel of a held server: the same server in the Library,
// which has a row for it only while some client reaches it through the gateway here.
export function kitdenLinks(model, name) {
  const reached = model && Object.values(model.connections.kitden || {}).some((names) => names.includes(name));
  return reached ? contextLinks({ kind: "mcp_server", name }, [], "gateway") : [];
}

// Details of a server in the Kitden gateway: what it is, its tools for the project picked at the
// top, then a link to the same server in the Library. `next` goes to the tool list (see
// toolsSection). The address keeps the server.
function showKitdenServer(server, next = {}) {
  setState({ selected: { kind: "mcp_server", name: server.name } });
  const body = el("div", "body");
  const row = el("div", "layer");
  const middle = el("div");
  middle.append(el("div", "name", `In the Kitden gateway · ${server.kind === "local" ? "Runs on this Mac" : "Remote"}`));
  const count = toolsNode(server);
  if (count) middle.append(count);
  row.append(mark("kitden"), middle);
  const stack = el("div", "stack");
  stack.append(row);
  body.append(stack, toolsSection(server.name, (again) => showKitdenServer(server, again), next));
  const links = kitdenLinks(current("gateway"), server.name);
  if (links.length) body.append(linksRow(links));
  if (!openInfo("MCP server", server.name, body, heldButtons(heldActions(server.name, foundClients(), server.plain_secrets)))) return;
  // A review opened from here (Remove, Put back, the Keychain) comes back to this panel. When
  // the settings changed since its preview, it is drawn from the page's latest read of the
  // gateway (the rescan reads it again); a server gone from it closes the panel.
  const readAgain = () => {
    const now = heldServer(current("gateway"), { kind: "mcp_server", name: server.name });
    if (now) showKitdenServer(now);
    else closePanel();
  };
  keepFrom(() => showKitdenServer(server), [body, $("#drawer footer")], readAgain);
}
