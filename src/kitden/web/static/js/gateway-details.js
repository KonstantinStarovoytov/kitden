// Details on the Gateway page for a client, a gateway, a link of the map, a server outside the
// gateway, a server in the Kitden gateway and one of its tools: a card builder each (a plain object
// that detailsCard draws, so a test reads it without a page), and a show… that opens it beside the
// page. The forms to add a gateway and to connect clients live here too, with what each registered
// gateway holds.
import { getJson, postJson, query } from "./api.js";
import { $, busyWhile, button, el, icon, joinWords, plural, reportError, withFocusKey } from "./dom.js";
import { ADD_SERVER, openAdd } from "./gateway-add.js";
import { loadLibraryFor, raceSlow } from "./library.js";
import { animateTo, fold } from "./motion.js";
import { projectNote } from "./offer.js";
import { callsText, closePanel, contextLinks, detailsCard, drawQuietly, followTray, heldActions, holdPanel, isPanelOpen, keepFrom, linksRow, loadPanel, moveBody, moveInto, moveTargets, NO_TOOLS, offerLabel, offNote, openPanel, panelState, previewButton, refreshTools, review, showInPreview, stepTo, swapContent, switchList, techRows, technical, toast, toolRows, toolsHead, writingToolsOn } from "./panel.js";
import { ALL_PROJECTS, callout, CLIENT_NAMES, clientCheck, FIND_PROJECT, folderName, GATEWAY_NOTE, gatewayName, kindOf, kitdenClients, mark, menuItems, originText, STATE_WORDS, versionsOpen } from "./parts.js";
import { arrival, current, data, freshness, gatewayShows, go, libraryChoice, projectPath, reload, render, setState, state, switchProject } from "./store.js";
import { addToTray, iconFor, inTray, keyFor, takeOut, tray } from "./tray.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
// The kitden entry is the same one that lets agents read this setup.
export const SETUP_NOTE = "The kitden entry shows your setup to agents and offers the tools in the Kitden gateway.";
// What Disconnect takes from a client, as the review's after line says it (views/after.py).
const disconnectNote = (name) => `${name} loses the Kitden gateway's servers and Kitden's own read of your setup. Servers it sets up on its own stay.`;
// The kind word each card shows at its top, and its skeleton too while it loads: one source, so a
// card never comes after a skeleton of another kind. The Add a server panel (gateway-add.js) is
// about the gateway too.
export const KIND = { client: "Client", gateway: "Gateway", server: "Server", tool: "Tool", connection: "Connection", add: "Gateway" };
// What a server outside the gateway is, by the Gateway's group for it.
const GROUP_KINDS = { move: "Remote", local: "Local", plugin: "From a plugin" };
// The icon of a server, by what it is: one reached over the network, one that runs on this Mac,
// one that comes with a plugin (Kitden knows no icon of a server's own); and of a server outside
// the gateway, by its group. The map and the panels show the same.
export const SERVER_ICONS = { remote: "globe", local: "hard-drive", plugin: "package-open" };
export const OUTSIDE_ICONS = { move: SERVER_ICONS.remote, local: SERVER_ICONS.local, plugin: SERVER_ICONS.plugin };
// Each client opens its own Mac app through the link scheme the app registers: Claude, Cursor,
// and ChatGPT for Codex. The server reads the scheme from the installed app's Info.plist at scan
// time (`app_url`); without the app there is nothing to open.
const CLIENT_APPS = { claude_code: "Claude", codex: "ChatGPT", cursor: "Cursor" };

// The found clients Kitden can write.
export function foundClients() {
  return (data.clients || []).filter((c) => WRITABLE.includes(c.id) && c.status === "found").map((c) => c.id);
}

// "Use this gateway…" moves the clients from another registered gateway to this one. The
// Kitden gateway sits beside the registered ones: it is never switched to or away from.
export function offersSwitch(model, gateway) {
  if (gateway.kind === "kitden") return false;
  const used = model.used.filter((id) => id !== "kitden");
  return used.length > 0 && !used.includes(gateway.id);
}

// The gateways that can take an outside row now, in the order offered; none when it has no
// entries to take or something keeps it out (`stays`). The List's "Move in…", Details and
// "Move all" agree by asking here.
export function movesTo(model, key, row) {
  if (!row.items.length || row.stays) return [];
  return moveTargets(model, key);
}

// Client tiles and their words, as a Facts value; `text` says the same in words alone.
export function tiles(clients, text) {
  const node = el("span", "fact-tiles");
  node.append(...clients.map((client) => mark(client)), el("span", null, text));
  return node;
}

function clientsFact(clients) {
  const text = clients.length ? plural(clients.length, "client", "clients") : "No clients yet";
  return { label: "Clients", value: tiles(clients, text), text };
}

// What a panel's head shows beside its title: a client's tile, the Kitden house, a registered
// gateway's mark, or a server's icon on a tile.
export function headTile(...nodes) {
  const tile = el("span", "p-tile");
  tile.append(...nodes);
  return tile;
}

// A server's icon on a 28 px tile.
export function iconTile(look) {
  const tile = headTile(icon(look, 15));
  tile.classList.add("p-icon");
  return tile;
}

function houseTile() {
  const house = el("img", "p-house");
  house.src = "/static/brand/kitden.svg";
  house.alt = "";
  return headTile(house);
}

// A 6 px lamp (style.css): green "on", grey "off", the grey ring "out" of a server outside the
// gateway, the dashed "pv" of a change in preview.
export function lamp(look) {
  const node = el("span", `lamp ${look}`);
  node.setAttribute("aria-hidden", "true");
  return node;
}

// Words in the accent that show while the tray row `key` waits there, and are gone otherwise.
function waitWords(key, words) {
  const node = el("span", "accent");
  followTray(node, key, (waiting) => {
    node.textContent = waiting ? words : "";
  });
  return node;
}

// What connects a client to the Kitden gateway, or takes it off again, by its kitden entry (its row
// in the setup): `{ connect, update, body }`, Connect being the entry's set up (`update` for an old
// entry, which it replaces) and Disconnect its removal (Task 1). Null where Kitden cannot do
// either: the setup was not read, a plugin gives the entry, the client is not on this Mac, or its
// own entry is turned off.
export function connectAction(client, setup) {
  const entry = (setup || []).find((e) => e.client === client);
  if (entry && entry.state === "added" && entry.enabled !== false) {
    return { connect: false, update: false, body: { action: "client.disconnect", targets: [{ client }], params: {} } };
  }
  const offer = kitdenClients(setup).setup.find((s) => s.client === client);
  return offer ? { connect: true, update: offer.body.action === "setup_server.update", body: offer.body } : null;
}

// What connects a client that is not connected, for a drag onto the gateway: its Connect
// (connectAction), or the switch of its own entry where that is off and Kitden can write it. Null
// where Kitden can do neither.
export function connectBody(client, setup) {
  const action = connectAction(client, setup);
  if (action) return action.connect ? action.body : null;
  const entry = (setup || []).find((e) => e.client === client);
  const turnsOn = entry && entry.state === "added" && entry.enabled === false && TURNS_ON.includes(client);
  return turnsOn ? { action: "setup_server.enable", targets: [{ client }], params: {} } : null;
}

// Why a client has no Connect or Disconnect, in a few words for a gateway row: a plugin gives its
// entry, its own entry is off, or Kitden did not find it here (or could not read its settings, by
// the scan's `found`). Null where it has a button, or Kitden cannot say.
function noButtonWords(entry, found) {
  if (!entry) return null;
  if (entry.state === "not_installed") return found && found.status === "unreadable" ? "settings not readable" : "not on this Mac";
  if (entry.enabled === false) return "its entry is off";
  return entry.state === "plugin" ? "from a plugin" : null;
}

// Whether Kitden knows the tools of every server in `servers`.
const toolsKnown = (servers) => servers.every((s) => (s.tool_list || []).length);

// What reaches a client through the Kitden gateway (`view`, the picked project's or all
// projects'): its servers that are on, and their tools that are on (null while Kitden does not
// know the tools of one of them). Null when Kitden could not read the gateway.
function throughKitden(view) {
  const kitden = view && view.gateways.find((g) => g.kind === "kitden");
  if (!kitden || kitden.problem) return null;
  const on = (kitden.servers || []).filter((s) => s.state === "on");
  return { servers: on.length, tools: toolsKnown(on) ? on.reduce((n, s) => n + (s.on_count || 0), 0) : null };
}

// Clients ------------------------------------------------------------------------------------

// Under a client's name: its version on this Mac, or why there is none: still read in the
// background, or not known.
function clientWhere(found, progress) {
  if (!found || found.status === "not_found") return STATE_WORDS.missing;
  if (found.status === "unreadable") return STATE_WORDS.unread;
  if (found.version) return `Version ${found.version} · on this Mac`;
  return versionsOpen(progress) ? "Checking the version… · on this Mac" : "Version not known · on this Mac";
}

// The clients whose own kitden entry Kitden turns on again, by the key their docs name: the twin
// of views/setup_server.py ENABLE_KEYS (checked 2026-10-24). Others say where to do it.
const TURNS_ON = ["codex"];

// The Gateway fact: the lamp and Connected or Not connected ("Not known" with no lamp, without the
// setup read), then " · change in preview" in the accent while its Connect or Disconnect waits in
// the tray (`key`).
function gatewayFact(known, on, key) {
  const text = known ? (on ? "Connected" : "Not connected") : "Not known";
  const value = el("span", "fact-mark");
  const words = el("span", null, text);
  if (key) words.append(waitWords(key, " · change in preview"));
  if (known) value.append(lamp(on ? "on" : "off"));
  value.append(words);
  return { label: "Gateway", value, text };
}

// The Through Kitden fact: the servers that are on in the Kitden gateway and their tools that are
// on ("1 server · 3 tools on"), for a client that uses it; "Nothing yet" for one that does not, or
// while none is on; "Not known" without the setup or the gateway read.
function throughFact(known, on, through) {
  if (known && !on) return { label: "Through Kitden", value: "Nothing yet", quiet: true };
  if (!known || !through) return { label: "Through Kitden", value: "Not known" };
  if (!through.servers) return { label: "Through Kitden", value: "Nothing yet", quiet: true };
  const servers = plural(through.servers, "server", "servers");
  return { label: "Through Kitden", value: through.tools === null ? servers : `${servers} · ${plural(through.tools, "tool", "tools")} on` };
}

// The servers a client sets up on its own, as the map draws them for it: each row outside the
// gateway that it loads, with the icon of its group.
function ownServers(view, client) {
  const groups = (view && view.groups) || {};
  return Object.entries(OUTSIDE_ICONS).flatMap(([group, look]) => (groups[group] || [])
    .filter((row) => (row.columns || row.clients).includes(client)).map((row) => ({ name: row.name, look })));
}

// The On its own fact: a small chip with its icon for each, or "Nothing".
function ownFact(own) {
  if (!own.length) return { label: "On its own", value: "Nothing", quiet: true };
  const value = el("span", "chips");
  for (const server of own) {
    const chip = el("span", "chip-s");
    chip.append(icon(server.look, 12), el("span", null, server.name));
    value.append(chip);
  }
  return { label: "On its own", value, text: joinWords(own.map((server) => server.name)) };
}

// What a client that uses the Kitden gateway gets there, as a sentence: the servers it calls
// through it (in the picked project, `place`), or that none is on; and whether it said Kitden's
// rules, so the next sentence can say "those rules".
function throughSay(name, through, place) {
  if (!through) return { say: `${name} reaches the Kitden gateway through its kitden entry.`, rules: false };
  if (!through.servers) return { say: `${name} uses the Kitden gateway, but no server in it is on ${place}.`, rules: false };
  return { say: `${name} calls ${plural(through.servers, "server", "servers")} through Kitden, so Kitden's rules apply to them.`, rules: true };
}

// What the client panel says (gateway-notes 3.5): whether the client calls servers through Kitden,
// so its rules apply, or why not (not on this Mac, its entry off); the servers it sets up on its
// own, which skip those rules; and why there is no Disconnect for a plugin's entry.
function clientSay(name, { known, on, entry, found, turnsOn, through, place, own }) {
  if (!known) return "Kitden could not read which clients use it.";
  let said = { say: `${name} does not use the Kitden gateway yet.`, rules: false };
  if (entry && entry.state === "not_installed") {
    const unread = found && found.status === "unreadable";
    said.say = unread ? `Kitden could not read ${name}'s settings, so it cannot connect it.` : `Kitden did not find ${name} on this Mac, so it cannot connect it.`;
  } else if (on) said = throughSay(name, through, place);
  else if (entry && entry.state === "old") said.say = `${name} has an old Kitden entry, so it does not use the gateway yet.`;
  else if (entry && entry.enabled === false) {
    said.say = `${name} has the kitden entry turned off, so it does not reach the gateway.`;
    if (!turnsOn) said.say = [said.say, `Turn it on in ${name}'s own MCP settings.`].join(" ");
  }
  const words = [said.say];
  if (own.length) {
    const many = own.length > 1;
    words.push(`${joinWords(own.map((s) => s.name))} ${many ? "are" : "is"} set up in ${name} on its own and skip${many ? "" : "s"} ${said.rules ? "those rules" : "Kitden's rules"}.`);
  }
  if (on && entry.state === "plugin") words.push(`${name} gets Kitden from a plugin: turn the plugin off to disconnect it.`);
  return words.join(" ");
}

// The Library at its MCP servers, where each client's column shows what it loads. The panel
// closes first; the tab is read first, as a link from Details reads it.
async function seeInLibrary() {
  const choice = libraryChoice({ kind: "mcp_server" });
  closePanel({ focus: false });
  await raceSlow(loadLibraryFor(choice), 300);
  go("library", choice);
}

// Details of a client, as the mockup's client panel (gateway-notes 3.5): its tile, its version on
// this Mac; whether it uses the Kitden gateway, what it gets through it (`view`, the Gateway's
// read, for the picked project and its folder), the servers it sets up on its own, and the scope;
// a sentence. "Connect to the gateway…" (the kitden entry's set up, primary) or "Disconnect from
// the gateway…" (its removal), where Kitden can do either (connectAction), and the Library. Under
// More (D18): "Turn it on in <client>…" where its own entry is off and Kitden can write the switch,
// and its Mac app, when Kitden found its link scheme.
export function clientCard(client, { setup, clients, progress = data.progress, view = null, picked = "", folder = "" } = {}) {
  const name = CLIENT_NAMES[client];
  const found = (clients || []).find((c) => c.id === client);
  const { linked, off, known } = kitdenClients(setup);
  const on = linked.includes(client);
  const entry = (setup || []).find((e) => e.client === client);
  const action = connectAction(client, setup);
  const through = throughKitden(view);
  const own = ownServers(view, client);
  const facts = [
    gatewayFact(known, on, action && keyFor(action.body)),
    throughFact(known, on, through),
    ownFact(own),
    { label: "Projects", value: picked ? folder : ALL_PROJECTS },
  ];
  // A plugin's entry that is off is the plugin's switch, not the entry's.
  const turnsOn = off.includes(client) && entry.state === "added" && TURNS_ON.includes(client);
  const why = clientSay(name, { known, on, entry, found, turnsOn, through, place: placeWords(picked, folder), own });
  const actions = [];
  if (action && action.connect) actions.push({ label: action.update ? "Update the Kitden entry…" : "Connect to the gateway…", body: action.body, note: SETUP_NOTE, primary: true });
  else if (action) actions.push({ label: "Disconnect from the gateway…", body: action.body, note: disconnectNote(name) });
  actions.push({ label: "See what it loads in Library", run: seeInLibrary });
  const more = [];
  if (turnsOn) more.push({ label: `Turn it on in ${name}…`, body: { action: "setup_server.enable", targets: [{ client }], params: {} }, note: SETUP_NOTE });
  if (found && found.app_url) {
    const url = found.app_url;
    // The browser asks once before it opens the app.
    more.push({ label: `Open ${CLIENT_APPS[client]}`, run: () => { window.location.href = url; } });
  }
  return { kind: KIND.client, title: name, id: clientWhere(found, progress), tile: headTile(mark(client)), facts, why, actions, more };
}

// Gateways -----------------------------------------------------------------------------------

// What each registered gateway holds, read from the gateway itself when the page draws and again
// after every reload. An answer that fails never blocks the rest of the page.
const held = new Map(); // gateway id -> { servers, error, at, loading }

async function loadHeld(gateway) {
  const at = performance.now();
  // The last answer stays while it is read again, so the map's links do not go and draw again.
  held.set(gateway.id, { ...held.get(gateway.id), loading: true, at });
  let answer;
  try {
    answer = await getJson(`/api/gateways/${encodeURIComponent(gateway.id)}/servers`);
  } catch {
    answer = { servers: null, error: "Could not read what the gateway holds." };
  }
  held.set(gateway.id, { ...answer, at });
  if (state.view !== "gateway") return;
  render();
  // Its open Details say what it holds now.
  if (panelState.current && panelState.current.gateway === gateway.id) showGateway(gateway.id);
}

// The live reads of the registered gateways Kitden can read, started again after a reload.
export function liveHeld(view) {
  for (const gateway of view.gateways) {
    if (gateway.kind === "kitden" || !gateway.managed) continue;
    const entry = held.get(gateway.id);
    if (!entry || entry.at < freshness.reloadStartedAt) loadHeld(gateway);
  }
  return held;
}

// The gateway's own page: the saved link, or the address it serves.
function gatewayPage(gateway) {
  if (gateway.ui_url) return gateway.ui_url;
  try { return new URL(gateway.url).origin; } catch { return null; }
}

// Only clients without an entry in any registered gateway are offered. One that uses another
// gateway moves with "Use this gateway…"; connecting it here too would load its servers twice.
// The Kitden gateway holds other servers, so its clients can connect here too.
function waitingClients(model, found) {
  const registered = Object.entries(model.connections).filter(([id]) => id !== "kitden").map(([, per]) => per);
  return found.filter((c) => !registered.some((per) => (per[c] || []).length));
}

// How many tools of the gateway's servers are on, for the picked project or all projects:
// "3 of 6 on"; "Not known yet" while Kitden does not know the tools of one of them.
function toolsWords(servers) {
  if (!servers.length) return "Nothing yet";
  if (!toolsKnown(servers)) return "Not known yet";
  const on = servers.reduce((n, s) => n + (s.on_count || 0), 0);
  return `${on} of ${servers.reduce((n, s) => n + s.tool_list.length, 0)} on`;
}

// The gateway panel's clients (gateway-notes 3.6): a row each with its tile, its name over its lamp
// and whether it is connected (" · in preview" in the accent while its change waits in the tray),
// and its own "Connect…", "Update…" or "Disconnect…" where Kitden can do it (connectAction), else
// why not (noButtonWords; `clientList`, the scan's clients).
function clientRows(setup, clientList) {
  const { linked } = kitdenClients(setup);
  const list = el("div", "sw-list client-rows");
  for (const client of WRITABLE) {
    const on = linked.includes(client);
    const action = connectAction(client, setup);
    const why = action ? null : noButtonWords((setup || []).find((e) => e.client === client), (clientList || []).find((c) => c.id === client));
    const said = el("span", null, [on ? "Connected" : "Not connected", why].filter(Boolean).join(" · "));
    const state = el("small");
    state.append(lamp(on ? "on" : "off"), said);
    const words = el("div", "sw-tx");
    words.append(el("b", null, CLIENT_NAMES[client]), state);
    const row = el("div", "sw-row");
    row.append(mark(client), words);
    if (action) {
      said.append(waitWords(keyFor(action.body), " · in preview"));
      row.append(rowButton(client, action));
    }
    list.append(row);
  }
  const section = el("section", "clients");
  section.append(el("h2", "sw-head", "Clients"), list);
  return section;
}

// A client row's button: it adds the client's Connect (Update, for an old entry) or Disconnect to
// the tray and says "In preview" while it waits there. A screen reader hears the client's name
// after its words, and the hover text says the whole change.
const ROW_WORDS = {
  connect: ["Connect…", (name) => `Connect ${name} to the gateway…`],
  update: ["Update…", (name) => `Update ${name}'s Kitden entry…`],
  disconnect: ["Disconnect…", (name) => `Disconnect ${name} from the gateway…`],
};
function rowButton(client, { connect, update, body }) {
  const name = CLIENT_NAMES[client];
  const [label, hover] = ROW_WORDS[update ? "update" : connect ? "connect" : "disconnect"];
  const node = previewButton(label, body, { note: connect ? SETUP_NOTE : disconnectNote(name), look: "btn small" });
  node.append(el("span", "sr-only", ` ${name}`));
  node.title = hover(name);
  node.dataset.focus = `conn:${client}`;
  return node;
}

// The Servers fact, "2 in the gateway · 4 outside". A server whose move out waits in the tray, once
// its row has its part, counts as outside already, as the map draws it. The words follow the tray
// while the panel shows: their key is no row's, so they are counted again on every change of it.
function serverCounts(servers, outside) {
  const value = el("span");
  const count = () => {
    const leaving = servers.filter((s) => movesOutNow(s.name)).length;
    value.textContent = `${servers.length - leaving} in the gateway · ${outside.length + leaving} outside`;
  };
  followTray(value, "counts", count);
  return { label: "Servers", value, text: value.textContent };
}

// Whether the move out of the server `name` waits in the tray with its part, as the map draws it
// (gateway.js rowsOnMap): not once it is applied.
function movesOutNow(name) {
  const key = keyFor({ action: "gateway.move_out", params: { server: name } });
  return tray.phase !== "applied" && tray.rows.some((row) => row.key === key && row.part);
}

// The Kitden gateway, as the mockup's gateway panel (gateway-notes 3.6): the house, where it runs;
// its servers and the servers outside it, how many of their tools are on; one row per client with
// its own Connect or Disconnect (not without the setup read: the warning says so); the sentence of
// what it controls. Under More (D18): "Add a server…", which opens the Add a server panel, "Move
// all N…", every outside server a move can take, in one review, and "Add another gateway…", which
// shows the form in the panel (`adding`).
function kitdenCard(gateway, { view, setup, clientList, adding }) {
  const { known } = kitdenClients(setup);
  const servers = gateway.servers || [];
  const outside = Object.values(view.groups).flat();
  const facts = [];
  // Settings it cannot read are a problem, not an empty gateway: the callout says so.
  if (!gateway.problem) {
    facts.push(serverCounts(servers, outside), { label: "Tools", value: toolsWords(servers) });
  }
  // A name in two outside groups is set up differently in two clients: a move refuses it until
  // the person keeps one, so it moves on its own and "Move all" leaves it out.
  const twice = (row) => outside.filter((other) => other.name === row.name).length > 1;
  const rows = ["move", "local"].flatMap((key) => (view.groups[key] || []).filter((row) => !twice(row) && movesTo(view, key, row).some((g) => g.id === gateway.id)));
  const more = [{ label: ADD_SERVER, run: () => openAdd() }];
  if (rows.length) {
    const targets = rows.flatMap((row) => row.items).map((item) => ({ item }));
    more.push({ label: `Move all ${rows.length}…`, body: { action: "gateway.move", targets, params: { gateway: gateway.id } } });
  }
  // While the form is open its own heading stands in the place of its entry.
  if (!adding) more.push({ label: ADD_ANOTHER, run: () => showGateway(gateway.id, { adding: true }) });
  let warning = known ? null : "Kitden could not read which clients use it.";
  if (gateway.problem) warning = gateway.problem;
  let after = null;
  if (adding) {
    after = el("section", "add-gateway");
    after.append(el("h2", null, "Add another gateway"), addForm({ onCancel: () => stopAdding(gateway.id) }));
  }
  const why = "The gateway controls only the servers in it. Direct entries and terminal tools are outside it.";
  return { kind: KIND.gateway, title: gateway.name, id: gateway.where, tile: houseTile(), facts, list: known ? clientRows(setup, clientList) : null, why, actions: [], more, after, warning };
}

// A registered gateway Kitden could not read says only this on the map, in the List and as its
// Servers fact; its Details say why in a callout (heldProblem). The reason may name a variable or
// an address, which stay behind Details.
export const NOT_REACHED = "Not connected";

// What a registered gateway holds, as its Servers fact.
function heldWords(entry) {
  if (!entry || entry.loading) return "Reading what it holds…";
  if (!entry.servers) return NOT_REACHED;
  return plural(entry.servers.length, "server", "servers");
}

// Why Kitden could not read what a registered gateway holds, or null.
function heldProblem(entry) {
  if (!entry || entry.loading || entry.servers) return null;
  return entry.error || "Could not read what the gateway holds.";
}

// One sentence on where its servers and tools are set.
function heldWhy(gateway, entry) {
  if (!gateway.managed) {
    const need = gateway.kind === "obot" ? "the name of the variable that holds an Obot API key" : "its sign-in details";
    return `To see what it holds from here, save the gateway again with ${need}.`;
  }
  if (entry && entry.servers && !entry.servers.length) {
    return gateway.movable ? "Nothing yet. Move a server in from the outside group." : `Nothing yet. Add servers in ${gatewayName(gateway)} itself.`;
  }
  return `Tools and access are set in ${gatewayName(gateway)} itself.`;
}

// A registered gateway (Obot, MetaMCP): its clients, what it holds (`held`, the live read) and,
// with two of them, whether the clients use it. Its own page, "Use this gateway…", and the form to
// connect clients that use no registered gateway yet; its address waits under Technical details.
function registeredCard(gateway, { view, held: entry, clients }) {
  const name = gatewayName(gateway);
  const per = view.connections[gateway.id] || {};
  const facts = [clientsFact(WRITABLE.filter((c) => (per[c] || []).length))];
  if (gateway.managed) facts.push({ label: "Servers", value: heldWords(entry) });
  if (view.gateways.filter((g) => g.kind !== "kitden").length > 1) {
    facts.push({ label: "State", value: view.used.includes(gateway.id) ? "Used" : "Not used" });
  }
  const actions = [];
  const page = gatewayPage(gateway);
  // A side door: everything Kitden can do happens here, so it is never the primary action.
  if (page) actions.push({ label: `Open ${name} ↗`, run: () => window.open(page, "_blank", "noopener") });
  // Clients use another registered gateway: one review moves all of them here (the old entries go).
  if (offersSwitch(view, gateway)) {
    const entryName = name.toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
    actions.push({ label: "Use this gateway…", body: { action: "gateway.switch", targets: [], params: { gateway: gateway.id, name: entryName } }, primary: true });
  }
  const waiting = waitingClients(view, clients);
  let after = null;
  if (waiting.length) {
    const box = el("details", "connect");
    box.open = draft.connectOpen === null ? true : draft.connectOpen;
    box.addEventListener("toggle", () => { draft.connectOpen = box.open; });
    box.append(el("summary", null, "Connect clients"), connectForm(gateway, waiting));
    after = fold(box);
  }
  const rows = [{ title: "MCP address", summary: gateway.url }, ...(gateway.ui_url ? [{ title: "Interface link", summary: gateway.ui_url }] : [])];
  const warning = gateway.managed ? heldProblem(entry) : null;
  return { kind: KIND.gateway, title: name, id: null, tile: headTile(mark("gateway")), facts, why: heldWhy(gateway, entry), actions, after, technical: technical(rows), warning };
}

// Cancel, or Escape in the form: the card is drawn again without it, focus on its entry (or on More,
// which it waits under again).
const ADD_ANOTHER = "Add another gateway…";
function stopAdding(id) {
  showGateway(id);
  const drawer = $("#drawer");
  const back = withFocusKey(drawer, `action:${ADD_ANOTHER}`) || withFocusKey(drawer, "more");
  if (back) back.focus();
}

// Details of a gateway: the Kitden one, or a registered one. `clients` are the found clients Kitden
// writes; `clientList` the scan's clients, each with its status.
export function gatewayCard(gateway, { view, setup, held: entry = null, clients = foundClients(), clientList = data.clients, adding = false } = {}) {
  if (gateway.kind === "kitden") return kitdenCard(gateway, { view, setup, clientList, adding });
  return registeredCard(gateway, { view, held: entry, clients });
}

// Servers outside the gateway ----------------------------------------------------------------

// Details of a server outside the gateway, for its row of one group (one name in two groups is
// two rows), as the mockup's panel for it (gateway-notes 3.8): its icon, Remote, Local or From a
// plugin "· outside the gateway"; the clients that set it up, its direct route, and that Kitden's
// rules do not reach it; a sentence (outsideSay). "Move into the gateway…" when a move can take it
// (primary), else why not; under More (D18): "Remove direct entry…" when no gateway takes a remote
// one, "+ Add to <client>…" for each client Kitden writes that lacks it, while no client gets it
// through a gateway (as the Library's cells), and a Remove for each of its own entries.
// `definitions` come from /api/explain; [] until they are read. `linked`: the clients that use the
// Kitden gateway (null when not read).
export function outsideCard(row, group, definitions, { view, clients = foundClients(), linked = null } = {}) {
  const columns = row.columns || row.clients;
  const names = joinWords(columns.map((c) => CLIENT_NAMES[c] || c));
  const own = definitions.filter((d) => row.items.includes(d.id));
  const targets = moveTargets(view, group);
  const actions = [];
  const more = [];
  const moves = movesTo(view, group, row);
  // With one gateway the button is the move's own, so it says when the move waits in the tray.
  if (moves.length === 1) actions.push({ label: "Move into the gateway…", body: moveBody(moves[0], row.items), primary: true });
  else if (moves.length) actions.push({ label: "Move into the gateway…", run: () => moveInto(moves, row.items, row.name), primary: true });
  else if (group === "move" && row.items.length && !targets.length) {
    more.push({ label: "Remove direct entry…", body: { action: "mcp.remove_direct", targets: row.items.map((item) => ({ item })), params: {} } });
  }
  const source = own.find((d) => d.scope === "user" && d.actions.includes("mcp.remove_direct"));
  if (source && !definitions.some((d) => d.via_gateway)) {
    for (const client of WRITABLE.filter((c) => clients.includes(c) && !definitions.some((d) => d.client === c))) {
      const body = { action: "mcp.add", targets: [{ client }], params: { item: source.id } };
      // In a project an add still goes to the client's settings for all projects; its note says so.
      more.push({ label: `+ Add to ${CLIENT_NAMES[client]}…`, body, note: projectNote(state.project) });
    }
  }
  const offers = own.filter((d) => d.actions.includes("mcp.remove_direct")).map((def) => ({ def, action: "mcp.remove_direct" }));
  for (const offer of offers) {
    more.push({ label: offerLabel(offer, offers), body: { action: offer.action, targets: [{ item: offer.def.id }], params: {} } });
  }
  const note = row.stays || (group === "move" && row.items.length && !targets.length ? GATEWAY_NOTE : null);
  const evidence = techRows(own.length ? own : definitions.filter((d) => !d.via_gateway && columns.includes(d.client)));
  const route = el("span", "fact-mark");
  route.append(lamp("out"), el("span", null, "Direct, on its own"));
  return {
    kind: KIND.server,
    title: row.name,
    id: `${GROUP_KINDS[group]} · outside the gateway`,
    tile: iconTile(OUTSIDE_ICONS[group]),
    facts: [
      { label: "Set up in", value: tiles(columns, names), text: names },
      { label: "Route", value: route, text: "Direct, on its own" },
      { label: "Kitden's rules", value: "Don't reach it", warn: true },
    ],
    why: outsideSay(row, columns, names, moves, linked),
    actions,
    more,
    after: note ? el("p", "muted", note) : null,
    technical: evidence.length ? technical(evidence) : null,
  };
}

// What the outside panel says: who calls it on their own (who has it set up, when Kitden does not
// know that any client loads it), so Kitden's switches do not reach its tools; that a move brings
// them here, where one can take it; and that its clients keep it either way, only where the move
// goes into the Kitden gateway and every one of them uses it (a move takes their own entries).
function outsideSay(row, columns, names, moves, linked) {
  const many = columns.length > 1;
  const who = row.unknown ? `${names} ${many ? "have" : "has"} ${row.name} set up` : `${names} ${many ? "call" : "calls"} ${row.name}`;
  const own = many ? "their own" : "its own";
  const words = [`${who} on ${own}, so Kitden can't turn its tools on or off.`];
  if (moves.length) words.push("Move it into the gateway to manage them here.");
  const keeps = moves.length === 1 && moves[0].kind === "kitden" && Boolean(linked) && columns.every((c) => linked.includes(c));
  if (keeps) words.push(`${names} ${many ? "keep" : "keeps"} it either way.`);
  return words.join(" ");
}

// Servers in the Kitden gateway and their tools ----------------------------------------------

// A selected MCP server that the Kitden gateway holds, or null.
export function heldServer(model, selected) {
  if (!model || !selected || selected.kind !== "mcp_server") return null;
  const kitden = model.gateways.find((g) => g.kind === "kitden");
  return ((kitden && kitden.servers) || []).find((s) => s.name === selected.name) || null;
}

// The links in the Details of a server in the Kitden gateway: the same server in the Library,
// which has a row for it only while some client reaches it through the gateway here.
export function kitdenLinks(model, name) {
  const reached = model && Object.values(model.connections.kitden || {}).some((names) => names.includes(name));
  return reached ? contextLinks({ kind: "mcp_server", name }, [], "gateway") : [];
}

// The owner's words for the switches of a tool and of a server, by the state they turn to.
const FOR_ALL = { on: "Turn on for all projects…", off: "Turn off for all projects…" };
const IN_SOME = { on: "Turn on in some projects…", off: "Turn off in some projects…" };
const STRICT = { on: "Turn strict mode on…", off: "Turn strict mode off…" };
const MOVE_OUT = "Move out of the gateway…";
const other = (state) => (state === "on" ? "off" : "on");
// An action that steps to the next part of the panel (`open`). Its button is not handed the step
// to wait for: one that waits over 150 ms turns busy and disabled (busyWhile), and focus on it
// would fall to the page. An error after the step starts is still reported.
const stepAction = (label, open) => ({ label, run: () => { Promise.resolve(open()).catch(reportError); } });

// A tool's or a server's state in the picked project ("" for All projects), from `effective`: a
// tool of a server that is off is off, and says so. With All projects "On" or "Off"; in a project
// a rule of its own says so, else where the state comes from: all projects, or a parent folder.
export function toolState(rule, picked) {
  const on = (rule.effective ?? rule.state) === "on";
  if (rule.why === "server_off") return "Off · server off";
  if (!picked) return on ? STATE_WORDS.on : STATE_WORDS.off;
  if (rule.origin === "project") return on ? "On in this project" : "Off in this project";
  const from = rule.origin === "parent" ? rule.origin_from : "all projects";
  return `${on ? STATE_WORDS.on : STATE_WORDS.off} · from ${from}`;
}

// What a tool says it does: the server's hint, or a guess from its name (`hintFrom`). The
// Gateway's short tool list has only the hint, whose word says where it comes from.
const HINT_FROM = { reads: "server", writes: "server", "may write": "name" };
export function reported(hint, hintFrom = HINT_FROM[hint] || null) {
  if (hintFrom === "server") return hint === "reads" ? "Reads only" : "May write";
  if (hintFrom === "name") return "Not reported · its name suggests it writes";
  return "Not reported";
}

// Where a state holds, as a sentence ends: in the picked project, or with All projects by the
// shared rule (a project's own rule may decide otherwise; othersText counts those).
const placeWords = (picked, folder) => (picked ? `in ${folder}` : "by the shared rule");

// With All projects: how many known projects decide otherwise than the shared state, as a
// sentence after another; "" in a picked project, with none, or without each project's rules.
// `stateIn(p)` is the state in one entry of the answer's `projects`.
function othersText(picked, projectRules, shared, stateIn) {
  if (picked || !projectRules || !shared) return "";
  const k = projectRules.filter((p) => stateIn(p) && stateIn(p) !== shared).length;
  return k ? ` ${plural(k, "project decides", "projects decide")} otherwise.` : "";
}

// The known projects (as the menu lists them) where turning the rule to `target` changes
// something: its state there is another one. None without each project's rules.
function changedIn(projects, projectRules, target, stateIn) {
  if (!projectRules) return [];
  const differ = new Set(projectRules.filter((p) => stateIn(p) && stateIn(p) !== target).map((p) => p.id));
  return projects.filter((p) => differ.has(p.id));
}

// A tool's rule in one project of the server's answer, as the gateway decides it there; and
// whether it can be called there, which it cannot while that project has the server off.
const ruleIn = (name) => (p) => p.tools && p.tools[name];
const callableIn = (name) => (p) => (p.server === "off" ? "off" : ruleIn(name)(p));

// The known projects (`projects`, as the menu lists them, by folder name) that the server's answer
// (`rules`) has a state for, each with its entry (`entry`); null without the answer.
function knownIn(rules, projects) {
  if (!Array.isArray(rules.projects)) return null;
  const entries = new Map(rules.projects.map((p) => [p.id, p]));
  return menuItems(projects.filter((p) => entries.has(p.id)), "").filter((item) => item.id).map((item) => ({ ...item, entry: entries.get(item.id) }));
}

// The clients that reach the Kitden gateway, as a fact; null when Kitden could not read them.
const linkedFact = (linked) => (linked ? clientsFact(linked) : { label: "Clients", value: "Not known" });

// Who can call through the gateway, as a sentence starts; or the sentence when nobody can.
function nobody(linked) {
  if (!linked) return "Kitden could not read which clients use it.";
  return linked.length ? null : "No client uses the Kitden gateway yet.";
}

// The change that sets a rule on a server (`tool` null) or on one of its tools, for all projects
// (`project` null) or for one.
export function ruleBody(server, tool, state, project) {
  return { action: "gateway.rule", targets: [], params: { server, tool, state, project } };
}

// The state all projects get, when the server's answer did not come: a state no project decides
// is the shared one.
const sharedOf = (rule, detail) => detail.shared || (["project", "parent"].includes(rule.origin) ? null : rule.state);

// The Permission fact: the tool's mark, green while it is on, then its words.
function permissionFact(tool, picked) {
  const text = toolState(tool, picked);
  const mark = el("span", (tool.effective ?? tool.state) === "on" ? "mark on" : "mark");
  mark.setAttribute("aria-hidden", "true");
  const value = el("span", "fact-mark");
  value.append(mark, el("span", null, text));
  return { label: "Permission", value, text };
}

// The Reported fact: what the tool says it does; "May write" in amber.
function reportedFact(hint, hintFrom) {
  const value = reported(hint, hintFrom);
  return { label: "Reported", value, warn: value === "May write" };
}

// Details of a tool in the Kitden gateway, as the mockup's tool panel (gateway-notes 3.4), for the
// picked project (`picked`, its folder name `folder`): its server, its permission and where it
// comes from, what the server says it does, the clients that call it through the gateway, and its
// calls; with All projects the projects with a rule of their own for it; a sentence (toolSay) and
// its actions (toolActions). `rules` is the /api/gateway/tools answer for its server (the shared
// state, and the state and own rules in each known project) and `detail` the tool's entry in it
// (shared state, the folder a project rule falls back to, calls, description). "In some
// projects…" steps to the projects it would change (projectsStep), keeping `warning`. With its
// server off a tool rule would change nothing anyone can call: only a way to the server.
export function toolCard(tool, server, { linked, picked = "", folder = "", detail = {}, rules = {}, projects = [], warning = null } = {}) {
  const name = tool.name;
  const on = (tool.effective ?? tool.state) === "on";
  const calls = callsText(detail.calls);
  const facts = [
    { label: "Server", value: `${server.name} · ${server.kind === "remote" ? "Remote" : "Local"}` },
    permissionFact(tool, picked),
    { label: "Comes from", value: originText(tool, folder) || "Not known", accent: tool.origin === "project" },
    reportedFact(tool.hint, detail.hint_from),
    linkedFact(linked),
    ...(calls ? [{ label: "Calls", value: calls }] : []),
  ];
  // The name goes under a title the server gives; without one it is the title.
  const title = tool.title || name;
  const known = knownIn(rules, projects);
  const card = { kind: KIND.tool, title, id: tool.title ? name : null, facts, list: picked ? null : ownRules(server.name, name, known), warning };
  if (detail.description) card.technical = technical([{ title: "Description", summary: detail.description }]);
  if (tool.why === "server_off") {
    const place = placeWords(picked, folder);
    const others = othersText(picked, rules.projects, rules.shared, (p) => p.server);
    const why = `${server.name} is off ${place}, so none of its tools can be called.${others}`;
    return { ...card, why, actions: [{ label: `Open ${server.name}`, run: () => showHeld(server.name) }] };
  }
  const shared = sharedOf(tool, detail);
  const target = other(shared || (on ? "on" : "off"));
  const step = { server: server.name, tool: name, title, target, shared, rules, readIn: picked, warning };
  const some = changedIn(projects, rules.projects, target, ruleIn(name)).length ? stepAction(IN_SOME[target], () => projectsStep(step)) : null;
  const others = known && known.map((p) => ({ id: p.id, name: p.name, state: callableIn(name)(p.entry) })).filter((p) => p.state);
  const who = linked && linked.length ? joinWords(linked.map((c) => CLIENT_NAMES[c])) : null;
  const why = toolSay({ who, none: nobody(linked), on, picked, folder, tool, shared, serverShared: rules.shared, others });
  return { ...card, why, ...toolActions(server.name, tool, { picked, folder, detail, shared, some }) };
}

// "atlas, where it is on; web, where it is off": each project and its state.
const whereItIs = (list) => list.map((p) => `${p.name}, where it is ${p.state}`).join("; ");

// What the tool panel says. With All projects: whether the clients that reach the gateway (`who`)
// can call it in every project, then each known project that decides otherwise (`others`, null
// when Kitden did not read them: then only what the shared rule does). In a project with a rule of
// its own: whether they can call it there, then what every other project has: the tool's shared
// rule, or off while the server is off for all projects (`serverShared`). In a project without
// one: what it follows, which names no client. `none` says why nobody can call it.
function toolSay({ who, none, on, picked, folder, tool, shared, serverShared, others }) {
  const state = on ? "on" : "off";
  if (picked && tool.origin === "parent") return `${folder} follows ${tool.origin_from}'s rule: ${state}.`;
  if (picked && tool.origin !== "project") return `${folder} follows the shared rule: ${state}.`;
  if (none) return none;
  if (!picked) {
    if (!others) return `${who} ${on ? "can" : "can't"} call this tool through Kitden by the shared rule.`;
    const all = on ? `${who} can call this tool through Kitden, in every project.` : `${who} can't call this tool through Kitden, in any project.`;
    const differ = others.filter((p) => p.state !== state);
    return differ.length ? `${all} Except ${whereItIs(differ)}.` : all;
  }
  const here = `${who} ${on ? "can" : "can't"} call this tool in ${folder}.`;
  const base = serverShared === "off" ? "off" : shared;
  if (!others || !base) return here;
  const differ = others.filter((p) => p.id !== picked && p.state !== base);
  const every = base === "on" ? "Every other project has it on" : "Every other project still has it off";
  return `${here} ${every}${differ.length ? `, except ${whereItIs(differ)}` : ""}.`;
}

// The tool panel's actions. With All projects: the rule for all projects the other way (primary
// while the tool is off) and "in some projects…" (`some`). In a project without a rule of its own:
// the other way there (primary) and for all projects; with one: back to the rule it follows
// (primary) and for all projects. In a project "in some projects…" waits under More (D18).
function toolActions(server, tool, { picked, folder, detail, shared, some }) {
  const on = (tool.effective ?? tool.state) === "on";
  const all = shared ? { label: FOR_ALL[other(shared)], body: ruleBody(server, tool.name, other(shared), null) } : null;
  if (!picked) return { actions: [...(all ? [{ ...all, primary: !on }] : []), ...(some ? [some] : [])], more: [] };
  const flip = on ? "off" : "on";
  const here = tool.origin === "project"
    ? { label: detail.follows ? `Use ${detail.follows}'s rule…` : "Use the shared rule…", body: ruleBody(server, tool.name, null, picked) }
    : { label: `Turn ${flip} in ${folder}…`, body: ruleBody(server, tool.name, flip, picked) };
  return { actions: [{ ...here, primary: true }, ...(all ? [all] : [])], more: some ? [some] : [] };
}

// Under All projects, the known projects with a rule of their own for the tool (`own` in the
// server's answer, as the map counts them), each with that rule and "Show", which picks the
// project as the menu at the top does: the Gateway changes in place and this panel steps forward to
// the tool there (followProject). The press hands its button no wait, so focus stays inside the
// panel. Null without one, or without the answer.
function ownRules(server, name, known) {
  const own = (known || []).filter((p) => (p.entry.own || []).includes(name));
  if (!own.length) return null;
  const section = el("section", "own-rules");
  section.append(el("h2", "sw-head", "Projects with a rule of their own"));
  for (const p of own) {
    const on = ruleIn(name)(p.entry) === "on";
    const show = button("Show", () => { switchProject(p.id).catch(reportError); }, "btn small");
    show.setAttribute("aria-label", `Show ${p.name}`);
    show.dataset.focus = `show:${p.id}`;
    const row = el("div", "own-row");
    row.append(icon("folder", 13), el("span", "own-name", p.name), el("span", on ? "own-state on" : "own-state", on ? "On" : "Off"), show);
    section.append(row);
  }
  return section;
}

// Details of a server in the Kitden gateway, for the picked project, as the mockup's server panel
// (gateway-notes 3.3): Remote or Local under its name; how many of its tools are on, where its
// state comes from and the clients that reach it; then its switches (`list`). `detail` is the
// /api/gateway/tools answer (the tools, strict, the shared state, the folder a project rule falls
// back to, the state in each known project). "Move out of the gateway…" steps to the client choice
// (moveOutStep); every other server action waits under More (heldMore, then Remove, Put back and
// the Keychain), and the Library link under them. `warning` (the read failed, or the server's
// problem) shows first, also back from a step.
export function heldCard(server, { linked, picked = "", folder = "", view = null, detail = {}, clients = foundClients(), projects = [], warning = null } = {}) {
  const name = server.name;
  const list = server.tool_list || [];
  const facts = [
    { label: "Tools", value: list.length ? `${server.on_count} of ${list.length} on` : "Not known yet" },
    { label: "Comes from", value: (server.origin !== "default" && originText(server, folder)) || ALL_PROJECTS, accent: server.origin === "project" },
    linkedFact(linked),
  ];
  const shared = sharedOf(server, detail);
  const target = other(shared || server.state);
  const step = { server: name, tool: null, title: name, target, shared, rules: detail, readIn: picked, warning };
  const some = changedIn(projects, detail.projects, target, (p) => p.server).length ? stepAction(IN_SOME[target], () => projectsStep(step)) : null;
  const actions = clients.length ? [stepAction(MOVE_OUT, () => moveOutStep({ name, detail, readIn: picked, warning }))] : [];
  const more = [...heldMore(server, picked, detail, some), ...heldActions(name, clients, server.plain_secrets)];
  const links = view ? kitdenLinks(view, name) : [];
  const id = `${server.kind === "remote" ? "Remote" : "Local"} · in the Kitden gateway`;
  return { kind: KIND.server, title: name, id, facts, list: heldList(name, detail, picked, folder), actions, more, after: links.length ? linksRow(links) : null, warning };
}

// A held server's actions the mockup has no place for, under More (D18): back to the rule it
// follows, for a rule of the picked project's own; the rule for all projects, from a project (the
// Whole server switch is that project's) or when there is no Whole server switch (the server's
// answer did not come); in some projects (`some`, with only the projects it would change); strict
// mode, every writing tool off, and Refresh tools.
function heldMore(server, picked, detail, some) {
  const name = server.name;
  const more = [];
  if (picked && server.origin === "project") {
    more.push({ label: detail.follows ? `Use ${detail.follows}'s rule…` : "Use the shared rule…", body: ruleBody(name, null, null, picked) });
  }
  const shared = sharedOf(server, detail);
  if ((picked || !Array.isArray(detail.tools)) && shared) more.push({ label: FOR_ALL[other(shared)], body: ruleBody(name, null, other(shared), null) });
  if (some) more.push(some);
  // Strict mode is the server's own, for all projects; unknown without the server's answer.
  if (typeof detail.strict === "boolean") {
    const state = detail.strict ? "off" : "on";
    more.push({ label: STRICT[state], body: { action: "gateway.strict", targets: [], params: { server: name, state } } });
  }
  const writing = server.state === "on" ? writingToolsOn(server.tool_list || []) : [];
  if (writing.length) {
    more.push({ label: "Turn off every writing tool…", body: { action: "gateway.rules", targets: [], params: { server: name, tools: writing, state: "off", project: picked || null } } });
  }
  more.push({ label: "Refresh tools", run: () => refreshHeld(name) });
  return more;
}

// The server's switches, for the picked project (its folder) or all projects: "Tools · atlas", why
// its tools are not offered while it is off, the whole server and each tool (tools.js, as the
// Library lists them). As in the mockup, the server's own rule goes back under More, not on its
// row, and a tool's description waits in its own panel. None without the server's answer.
function heldList(name, detail, picked, folder) {
  if (!Array.isArray(detail.tools)) return null;
  const where = picked ? folder : null;
  const [whole, ...tools] = toolRows(detail, where);
  const section = el("section", "tools");
  section.append(el("h2", "sw-head", toolsHead(where)));
  const off = offNote(detail, where);
  if (off) section.append(off);
  section.append(switchList([{ ...whole, differs: false }, ...tools.map((t) => ({ ...t, description: null }))], { server: name, project: picked || null }));
  if (!detail.tools.length) section.append(el("p", "muted", NO_TOOLS));
  return section;
}

// Links on the map -------------------------------------------------------------------------------

// What a press on a link the tray draws does, and the panel's button while a link's change waits.
export const TAKE_OUT = "Take it out of the preview";
const IN_PREVIEW_SAY = "This link is a change in preview. Nothing is written until you Apply.";
// Under a link's title: what it is, by what it joins (linkKind).
const LINK_SUBS = { client: "Route through the gateway", held: "Held by the gateway", tool: "Tool on", direct: "Direct route", change: "Change in preview" };

// The tray row a link's × adds has the × for its icon, except a disconnect, which has the plug its
// Disconnect button gives it too.
export const removalIcon = (body) => (body.action === "client.disconnect" ? iconFor(body) : "x");

// What a link joins, by its two blocks: a client and a gateway, a gateway and a server it holds, a
// server and one of its tools, a client and a server it sets up on its own; else a change in
// preview (a server moving in).
function linkKind(from, to) {
  if (from.kind === "client") return to.kind === "outside" ? "direct" : "client";
  if (to.kind === "tool") return "tool";
  return to.kind === "held" ? "held" : "change";
}

// The Claude Desktop app's Code tab: the map draws its servers from Claude Code (gateway_view.py).
const DESKTOP_TAB = "claude_desktop_code_tab";

// Where a change to a link is written, in words, never a path: the client's settings, a plugin's
// files (for an entry or a server a plugin gives), or the Kitden gateway's own file, which holds its
// servers and its rules (gateway.json: there is no rules file of its own). Null where Kitden does
// not say: a registered gateway keeps its servers itself, and a Claude Code line may also, or only,
// come from the Desktop app's Code tab.
function writtenIn(kind, from, to) {
  if (kind === "change") return "Not written yet";
  // A plugin gives a client only its kitden entry; its route to a registered gateway is its own.
  if (kind === "client") return from.viaPlugin && to.gateway.kind === "kitden" ? "A plugin's files" : `${from.name}'s settings`;
  if (kind === "direct") {
    if (to.groupKey === "plugin") return "A plugin's files";
    const own = (to.row.clients || []).includes(from.client) && !(from.client === "claude_code" && to.row.clients.includes(DESKTOP_TAB));
    return own ? `${from.name}'s settings` : null;
  }
  return kind === "tool" || from.gateway.kind === "kitden" ? "Kitden's gateway file" : null;
}

// What a server in the Kitden gateway passes on, by the clients that use the gateway (`linked`,
// null when not read).
function heldSay(name, linked) {
  if (!linked) return `The gateway holds ${name} and passes its tools that are on to the clients that use it.`;
  if (!linked.length) return `The gateway holds ${name}. No client uses the Kitden gateway yet.`;
  return `The gateway holds ${name} and passes its tools that are on to ${plural(linked.length, "client", "clients")}.`;
}

// What a link means, while no change to it waits in the tray (gateway-notes 3.7), for the picked
// project (its folder): what a client gets through the Kitden gateway; who passes on what a server
// holds or a tool that is on; that a server a client sets up on its own skips Kitden's rules. A
// registered gateway's links say where its tools are set.
function linkSay(kind, from, to, { linked, view, picked, folder, unk }) {
  const place = placeWords(picked, folder);
  if (kind === "client" && to.gateway.kind !== "kitden") return `Tools and access are set in ${to.name} itself.`;
  if (kind === "client") {
    const plugin = from.viaPlugin ? ` ${from.name} gets Kitden from a plugin: turn the plugin off to disconnect it.` : "";
    return `${throughSay(from.name, throughKitden(view), place).say}${plugin}`;
  }
  if (kind === "held") return from.gateway.kind === "kitden" ? heldSay(to.name, linked) : `Tools and access are set in ${from.name} itself.`;
  if (kind === "tool") {
    const none = nobody(linked);
    return none ? `${to.name} is on ${place}. ${none}` : `${to.name} is on ${place}: ${joinWords(linked.map((c) => CLIENT_NAMES[c]))} can call it through Kitden.`;
  }
  if (kind === "direct") return `${from.name} ${unk ? `has its own entry for ${to.name}` : `calls ${to.name} on its own`}. Kitden's rules don't reach it.`;
  return IN_PREVIEW_SAY;
}

// The State fact: the lamp and "In place" (the grey ring for a server a client sets up on its
// own), or the dashed lamp and "In preview" while the link's change waits in the tray (`waits()`,
// its row `key`).
function stateFact(key, waits, direct) {
  const value = el("span", "fact-mark");
  const look = () => {
    const now = waits();
    value.replaceChildren(lamp(now ? "pv" : direct ? "out" : "on"), el("span", null, now ? "In preview" : "In place"));
  };
  if (key) followTray(value, key, look);
  else look();
  return { label: "State", value, text: waits() ? "In preview" : "In place" };
}

// The panel's button: the change the link's × adds (`removal`), or, while the link's change waits
// in the tray, "Take it out of the preview", which takes its row out. One press at a time.
function removeButton(label, key, waits, removal) {
  const words = el("span", "cut");
  const node = el("button", "btn");
  node.type = "button";
  node.dataset.focus = "remove-link";
  node.append(icon("x", 13), words);
  pressOnce(node, () => {
    if (waits()) return takeOut(key);
    return removal ? addToTray(removal.body, { icon: removalIcon(removal.body) }) : null;
  });
  followTray(node, key, () => {
    words.textContent = waits() ? TAKE_OUT : label;
    node.title = words.textContent;
  });
  return node;
}

// A link's Connection panel (gateway-notes 3.7), from its two blocks (`from`, `to`), whether Kitden
// knows its client loads it (`unk`), what its × does (`removal`, { tip, body }, null where the map
// does not act on it) and the tray row it draws (`row`): "<from> → <to>" and what it is; From, To,
// its state and where a change to it is written; a sentence; and one button, as its ×. While its
// change waits in the tray (its row, or its own removal as it is), the state, the sentence and the
// button say so; they follow the tray, with no motion.
export function linkCard({ from, to, unk = false, removal = null, row = null }, { linked = null, view = null, picked = "", folder = "" } = {}) {
  const kind = linkKind(from, to);
  const key = row || (removal ? keyFor(removal.body) : null);
  const waits = () => Boolean(key) && (row ? inTray(row) : ticked(removal.body));
  const written = writtenIn(kind, from, to);
  const facts = [{ label: "From", value: from.name }, { label: "To", value: to.name }, stateFact(key, waits, kind === "direct")];
  if (written) facts.push({ label: "Written in", value: written });
  const say = linkSay(kind, from, to, { linked, view, picked, folder, unk });
  const why = el("p", "why");
  const sayNow = () => {
    why.textContent = waits() ? IN_PREVIEW_SAY : say;
  };
  if (key) followTray(why, key, sayNow);
  else sayNow();
  const label = removal ? `${removal.tip}…` : TAKE_OUT;
  const actions = key ? [{ label, node: removeButton(label, key, waits, removal) }] : [];
  return { kind: KIND.connection, title: [from.name, el("span", "arrow", " → "), to.name], id: LINK_SUBS[kind], facts, why, actions };
}

// Steps in the panel -----------------------------------------------------------------------------

// A step's head: Back, where it came from (`crumb`) and Close, over its title.
export function stepHead(crumb, title, back) {
  const head = el("header");
  const top = el("div", "top");
  const backButton = button(null, back, "btn ghost small step-back");
  backButton.setAttribute("aria-label", "Back");
  backButton.append(icon("arrow-left", 14));
  top.append(backButton, el("span", "crumb", crumb), button("Close", () => closePanel(), "btn ghost small"));
  const heading = el("h1", null, title);
  heading.id = "panel-title";
  head.append(top, heading);
  return head;
}

// A step's quiet note at its foot, after an info icon; `words` can change.
export function stepFoot(words) {
  const foot = el("p", "step-foot");
  foot.append(icon("info", 13), words);
  return foot;
}

// Back from a step to its panel: drawn from the rules read for it (`draw`), or read again
// (`read`) when the project picked now is not the one they were read in (`readIn`: a project
// switch in place, also before the step was drawn again), so it never shows one project's rules
// under another's name.
function backTo(draw, read, readIn) {
  return () => (state.project === readIn ? draw() : read());
}

// After a step, focus that was in the panel goes to the first control named in `keys` that is there.
export function focusAfterStep(...keys) {
  const drawer = $("#drawer");
  if (!drawer.contains(document.activeElement)) return;
  const node = keys.map((key) => withFocusKey(drawer, key)).find(Boolean);
  if (node) node.focus();
}

// Move a server out of the gateway (gateway-notes 4.2), the next step in its panel: one row per
// client Kitden can write, saying whether it uses the gateway now. A press adds the move into that
// client to the tray at once (one row per server: another press replaces it); a press on the
// client picked takes it out. Focus goes to the client picked, else the first. Back steps to the
// server's panel with its `warning`. `detail` is the server's rules, read in the project `readIn`.
// Drawn again (`dir` null) in place.
function moveOutStep(read, dir = "fwd") {
  const { name, detail, readIn, warning } = read;
  panelState.current = { type: "moveout", name };
  const { linked } = heldContext();
  const back = backTo(() => drawHeld(name, detail, { step: "back", warning }), () => showHeld(name, { step: "back", focus: [`action:${MOVE_OUT}`] }), readIn);
  const nodes = moveOutNodes(name, foundClients(), linked, back);
  keepFrom(() => moveOutStep(read, null), nodes, () => showHeld(name));
  if (!dir) return swapContent(nodes);
  return stepTo(nodes, dir).then(() => focusAfterStep(`pick:${movingTo(name) || foundClients()[0]}`));
}

// The step's parts: Back, where it came from and Close; the question (on the map, that a drag does
// the same; the List has no drag); a row per client; and what the other clients lose.
function moveOutNodes(name, clients, linked, back) {
  const picks = el("div", "picks");
  picks.setAttribute("role", "group");
  picks.setAttribute("aria-label", "Client that keeps it");
  picks.append(...clients.map((client) => clientPick(name, client, linked)));
  const body = el("div", "body");
  const drag = gatewayShows.mode === "list" ? "" : ` You can also drag ${name} onto a client on the map.`;
  body.append(el("p", "why", `Pick the client that keeps it.${drag}`), picks);
  return [stepHead(`Server · ${name}`, `Move ${name} out of the gateway`, back), body, stepFoot(`The other clients lose ${name}'s tools.`)];
}

// The client a server moves out to while its row waits in the tray, or null.
function movingTo(name) {
  const row = tray.rows.find((r) => r.key === keyFor({ action: "gateway.move_out", params: { server: name } }));
  return row ? row.body.targets[0].client : null;
}

// One client to keep the server: its tile, its name over whether it uses the gateway now (when
// Kitden could read that), and a radio that fills while the move into it waits in the tray. Its
// name says the same, as a map block's does.
function clientPick(name, client, linked) {
  const body = { action: "gateway.move_out", targets: [{ client }], params: { server: name } };
  const node = el("button", "pick");
  node.type = "button";
  node.dataset.focus = `pick:${client}`;
  const uses = linked ? (linked.includes(client) ? "Uses the gateway now" : "Not connected to the gateway") : null;
  const words = el("span", "pk-tx");
  words.append(el("b", null, CLIENT_NAMES[client]));
  if (uses) words.append(el("small", null, uses));
  node.setAttribute("aria-label", [CLIENT_NAMES[client], uses].filter(Boolean).join(", "));
  node.append(mark(client), words, el("span", "radio"));
  const picked = () => movingTo(name) === client;
  pressOnce(node, () => (picked() ? takeOut(keyFor(body)) : review(body)));
  followTray(node, keyFor(body), () => {
    node.classList.toggle("on", picked());
    node.setAttribute("aria-pressed", String(picked()));
  });
  return node;
}

// A pick row's press, one at a time as a preview button's: a second one while the first is asked
// does nothing, and so does a press on a row that is off.
export function pressOnce(node, press) {
  node.addEventListener("click", () => {
    if (node.disabled || node.dataset.working) return;
    node.dataset.working = "1";
    Promise.resolve(press()).catch(reportError).finally(() => {
      delete node.dataset.working;
    });
  });
}

// Turn a tool, or a whole server (`tool` null), on or off (`target`) in the projects picked
// (gateway-notes 5), the next step in its panel: one checkbox row per known project, by folder
// name, saying what it has now; a project that has `target` already cannot be ticked. A tick adds
// that project's rule to the tray at once (one row per project, D13), an untick takes exactly that
// row out; the step names the known projects inside a ticked one that change with it. Find
// narrows the rows as you type. Back and Done step back to the panel (with its
// `warning`), focus on "in some projects…" or the More it waits under; focus comes to Find. Drawn
// again (`dir` null) in place.
function projectsStep(step, dir = "fwd") {
  const { server, tool } = step;
  panelState.current = { type: "projects", server, tool };
  const again = { warning: step.warning, step: "back", focus: [`action:${IN_SOME[step.target]}`, "more"] };
  const back = backTo(() => (tool ? drawTool(server, tool, step.rules, again) : drawHeld(server, step.rules, again)), () => (tool ? showTool(server, tool, again) : showHeld(server, again)), step.readIn);
  const nodes = projectsNodes(step, heldContext().projects, back);
  keepFrom(() => projectsStep(step, null), nodes, () => (tool ? showTool(server, tool) : showHeld(server)));
  if (!dir) return swapContent(nodes);
  return stepTo(nodes, dir).then(() => focusAfterStep("find"));
}

// The step's parts for a server or a tool: the shared rule that stays, and who changes with a
// ticked project, over the project checklist.
function projectsNodes({ server, tool, title, target, shared, rules }, projects, back) {
  const stateIn = tool ? ruleIn(tool) : (p) => p.server;
  const ownOf = tool ? (p) => (p.entry.own || []).includes(tool) : (p) => Boolean(p.entry.own_server);
  const rows = (knownIn(rules, projects) || []).map((p) => ({ ...p, now: stateIn(p.entry) })).filter((p) => p.now);
  const ticks = rows.map((p) => {
    const body = ruleBody(server, tool, target, p.id);
    const off = p.now === target;
    const line = [p.sub, p.count, off ? `already ${target}` : `${p.now} now`].filter(Boolean).join(" · ");
    return { id: p.id, name: p.name, line, off, body, ticked: () => ticked(body), project: p };
  });
  const follows = (picked) => picked.map((t) => followLine(t.project, rows, ownOf, picked.map((x) => x.project))).filter(Boolean);
  const crumb = tool ? `Tool · ${title}` : `Server · ${server}`;
  return projectChecklist({ crumb, title: `Turn ${target} ${title} in the projects you pick`, why: shared ? `The shared rule stays ${shared}.` : null, rows: ticks, back, follows });
}

// The project checklist (D13), a step in a panel: Back, where it came from (`crumb`) and Close; the
// question (`title`); a quiet line (`why`); what changes with the ticks (`follows(ticked)`, nodes);
// Find, a row per project (tickRow, with a folder) and the words when none matches; Done (`back`);
// and how many wait. A tick adds that project's change to the tray at once, one row per project; an
// untick takes exactly that row out. The Gateway's tools and servers and the Library's skills use it.
export function projectChecklist({ crumb, title, why = null, rows, back, follows = null }) {
  const words = el("span");
  const said = el("div", "follows");
  said.setAttribute("aria-live", "polite");
  const count = () => {
    const ticks = rows.filter((row) => row.ticked());
    words.textContent = ticks.length ? `${plural(ticks.length, "project", "projects")} in preview. Apply them from the tray.` : "Tick projects. Each one waits in preview until Apply.";
    said.replaceChildren(...(follows ? follows(ticks) : []));
  };
  const picks = el("div", "picks");
  picks.setAttribute("role", "group");
  picks.setAttribute("aria-label", "Projects");
  picks.append(...rows.map((row) => tickRow({ ...row, look: icon("folder", 14) }, count)));
  const none = el("p", "muted", "No project matches.");
  none.hidden = true;
  const body = el("div", "body");
  if (why) body.append(el("p", "why", why));
  body.append(said, findField(picks, none), picks, none);
  const done = el("footer", "stack");
  done.append(button("Done", back, "btn"));
  const foot = stepFoot(words);
  foot.setAttribute("aria-live", "polite");
  count();
  return [stepHead(crumb, title, back), body, done, foot];
}

// The known projects that follow the rule of a ticked project `p`, so they change with it: as the
// gateway decides, `p` is further along their chain (`up` in the server's answer, nearest first; the
// home folder and `/` claim nobody), they have no rule of their own (`ownOf`) and are not ticked
// (`ticks`), and no project between them decides. One sentence, or null when none does.
function followLine(p, rows, ownOf, ticks) {
  const byId = new Map(rows.map((q) => [q.id, q]));
  const decides = (q) => !q || ownOf(q) || ticks.includes(q);
  const follows = (q) => {
    const up = q.entry.up || [];
    const at = up.indexOf(p.id);
    return at >= 0 && !decides(q) && !up.slice(0, at).some((id) => decides(byId.get(id)));
  };
  const names = rows.filter(follows).map((q) => q.name);
  if (!names.length) return null;
  return el("p", null, names.length === 1 ? `${names[0]} follows ${p.name} and changes with it.` : `${names.join(", ")} follow ${p.name} and change with it.`);
}

// Whether the rule `body` waits in the tray as it is: a row for that project with another state
// (a "Use the shared rule…") is not this tick.
function ticked(body) {
  const row = tray.rows.find((r) => r.key === keyFor(body));
  return Boolean(row) && row.body.params.state === body.params.state;
}

// One row to tick: its icon or tile (`look`), its name over its quiet line ("1 own rule · on now",
// "already off"), and a check that fills, popping in, while its change (`body`) waits in the tray as
// it is (`ticked()`). A ticked row's line says "<line> · in preview", or `onLine` when given. A
// press adds the change, or takes it out again; a row that is `off` takes no press. `line` and
// `off` may be functions, read again after every change of the tray, which `changed()` hears too.
export function tickRow({ id, name, line, onLine = null, look, off = false, body, ticked: isTicked }, changed = () => {}) {
  const now = (value) => (typeof value === "function" ? value() : value);
  const node = el("button", "pick multi");
  node.type = "button";
  node.setAttribute("role", "checkbox");
  node.dataset.focus = `tick:${id}`;
  node.dataset.name = name;
  node.disabled = now(off);
  const words = el("span", "pk-tx");
  const small = el("small", null, now(line));
  words.append(el("b", null, name), small);
  const box = el("span", "chk");
  box.append(icon("check", 12));
  node.append(look, words, box);
  pressOnce(node, () => (isTicked() ? takeOut(keyFor(body)) : review(body)));
  let was = null;
  followTray(node, keyFor(body), () => {
    const on = isTicked();
    const text = now(line);
    node.disabled = now(off);
    node.classList.toggle("on", on);
    node.setAttribute("aria-checked", String(on));
    // The line says it too, as a client row does: " · in preview".
    const said = on ? onLine || (text ? `${text} · in preview` : "In preview") : text;
    small.textContent = said;
    node.setAttribute("aria-label", `${name}, ${said}`);
    if (on && was === false) animateTo(box, [{ transform: "scale(0.6)" }, { transform: "none" }], { dur: 160 });
    was = on;
    changed();
  });
  return node;
}

// Find narrows the rows by folder name as you type (Enter does nothing); when none is left it
// says so (`none`).
function findField(picks, none) {
  const field = el("label", "find-project");
  const input = el("input");
  input.type = "text";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.setAttribute("placeholder", FIND_PROJECT);
  input.setAttribute("aria-label", FIND_PROJECT);
  input.dataset.focus = "find";
  input.addEventListener("input", () => {
    const text = input.value.trim().toLowerCase();
    let shown = 0;
    for (const row of picks.children) {
      row.hidden = !row.dataset.name.toLowerCase().includes(text);
      if (!row.hidden) shown += 1;
    }
    none.hidden = shown > 0;
  });
  field.append(icon("search", 14), input);
  return field;
}

// Showing a card -----------------------------------------------------------------------------

// Whether the panel shows `shown` now (the same card, drawn again), field by field.
function showing(shown) {
  const now = panelState.current;
  const keys = Object.keys(shown);
  return Boolean(now) && Object.keys(now).length === keys.length && keys.every((key) => now[key] === shown[key]);
}

// Open a card beside the page, its warning first. A press in it comes back to it: `draw` draws it
// again from what it read, `read` reads first (after Apply all). Another card than the one shown
// comes through its skeleton (loadPanel); one drawn again, or one whose skeleton shows while its
// read ends, does not. A `step` ("back") slides it in as the next step in the panel (stepTo).
export function openCard(card, shown, draw, read = draw, step = null) {
  const loads = panelState.current && panelState.current.type === "loading" && panelState.current.kind === card.kind;
  if (!step && !showing(shown) && !loads) loadPanel(card.kind);
  panelState.current = shown;
  const nodes = detailsCard(card);
  if (card.warning) nodes[1].prepend(callout(card.warning));
  keepFrom(draw, nodes, read);
  return step ? stepTo(nodes, step) : openPanel(nodes);
}

export function showClient(id) {
  const { picked, folder } = heldContext();
  const card = clientCard(id, { setup: data.setupServer, clients: data.clients, view: current("gateway"), picked, folder });
  openCard(card, { type: "client", client: id }, () => showClient(id));
}

// A gateway that is gone since closes its Details.
export function showGateway(id, { adding = false } = {}) {
  const view = current("gateway");
  const gateway = view && view.gateways.find((g) => g.id === id);
  if (!gateway) {
    closePanel();
    return;
  }
  const card = gatewayCard(gateway, { view, setup: data.setupServer, held: held.get(id), adding });
  openCard(card, { type: "gateway", gateway: id }, () => showGateway(id));
  if (adding) {
    const first = $("#drawer .add-gateway input");
    if (first) first.focus();
  }
}

// Details of a server outside the gateway: drawn at once from its row, then again with its
// definitions from /api/explain (never the Library's /api/map). The address keeps the server.
// A row that is gone since closes them.
export async function showOutside(group, name) {
  const row = ((current("gateway") || { groups: {} }).groups[group] || []).find((r) => r.name === name);
  if (!row) {
    closePanel();
    return;
  }
  setState({ selected: { kind: "mcp_server", name: row.name } });
  const shown = { type: "outside", group, name };
  drawOutside(row, group, [], shown);
  let answer;
  try {
    answer = await getJson(`/api/explain${query({ name: row.name, kind: "mcp_server", project: state.project })}`);
  } catch {
    // Drawn again with the warning: the card may still wait behind its skeleton.
    if (panelState.current === shown) drawOutside(row, group, [], shown, "Could not load the details.");
    return;
  }
  // The person may have opened something else meanwhile.
  if (panelState.current === shown) drawOutside(row, group, answer.definitions || [], shown);
}

function drawOutside(row, group, definitions, shown, warning = null) {
  const card = { ...outsideCard(row, group, definitions, { view: current("gateway"), linked: heldContext().linked }), warning };
  openCard(card, shown, () => drawOutside(row, group, definitions, shown, warning), () => showOutside(group, row.name));
}

// A link's Connection panel. `find()` gives the link's parts from the map as the page has it now
// (gateway.js linkParts), or null once the link is gone: then the panel closes. Drawn again, and
// read again after Apply all, from what `find()` gives then.
export function showLink(key, find) {
  const parts = find();
  if (!parts) {
    closePanel();
    return;
  }
  const { linked, picked, folder } = heldContext();
  openCard(linkCard(parts, { linked, view: current("gateway"), picked, folder }), { type: "link", key }, () => showLink(key, find));
}

// A server in the Kitden gateway, or one of its tools: its card is drawn from the page's latest
// read of the Gateway and the server's rules for the picked project (/api/gateway/tools), read
// first. The address keeps what is shown.
let reads = 0;

async function readRules(server) {
  try {
    return await getJson(`/api/gateway/tools${query({ server, project: state.project })}`);
  } catch {
    return null;
  }
}

// Read the server's rules, then `draw(answer)` (null when the read failed), unless the person
// pressed something else, closed the panel or picked another project meanwhile. A card the panel
// does not show yet (`shown`) shows its skeleton (`kind`) while it reads.
async function readThen(server, draw, { shown, kind }) {
  const asked = ++reads;
  if (!showing(shown)) loadPanel(kind);
  const { current: before } = panelState;
  const project = state.project;
  const answer = await readRules(server);
  if (asked !== reads || panelState.current !== before || state.project !== project) return;
  await draw(answer);
}

// What every card of the Kitden gateway is drawn for: the clients it reaches (null when not
// read), the picked project and its folder, and the projects a step offers.
function heldContext() {
  const { linked, known } = kitdenClients(data.setupServer);
  return { linked: known ? linked : null, picked: state.project, folder: folderName(projectPath()), projects: data.projects || [] };
}

// What a server in the Kitden gateway shows as, and the kind its skeleton names.
const heldShown = (name) => ({ shown: { type: "held", name }, kind: KIND.server });

// `step` ("fwd" or "back"): it slides in as a step in the panel, focus on the first control of
// `focus` there (none: it stays where it is).
export async function showHeld(name, { step = null, focus = [] } = {}) {
  setState({ selected: { kind: "mcp_server", name } });
  await readThen(name, (answer) => drawHeld(name, answer || {}, { warning: answer ? answer.problem : "Could not load the details.", step, focus }), heldShown(name));
}

// A server that is gone from the gateway since closes its Details. Back from a step it slides in
// (`step`), focus on the first control of `focus` there (Move out, or More).
function drawHeld(name, detail, { warning = null, step = null, focus = [`action:${MOVE_OUT}`] } = {}) {
  const view = current("gateway");
  const server = heldServer(view, { kind: "mcp_server", name });
  if (!server) {
    closePanel();
    return;
  }
  const card = heldCard(server, { ...heldContext(), view, detail, warning });
  const shown = openCard(card, { type: "held", name }, () => drawHeld(name, detail, { warning }), () => showHeld(name), step);
  if (step) return shown.then(() => focusAfterStep(...focus));
}

export async function showTool(server, name, { step = null, focus = [] } = {}) {
  setState({ selected: { kind: "tool", name: `${server}/${name}` } });
  await readThen(server, (answer) => drawTool(server, name, answer || {}, { warning: answer ? null : "Could not load the details.", step, focus }), { shown: { type: "tool", server, tool: name }, kind: KIND.tool });
}

// A project switch on the Gateway changes the page in place (gateway.js), and Details follow: a
// tool's or a server's step forward to the new project (130 + 220), read for it first; a client's,
// a gateway's, an outside server's or a link's are drawn again at once for it, so no button in
// them acts on the old project; a client's keeps its place in the address. A step inside a panel
// (the project picker, a move out) and a row's review stay as they are: Back from a step reads
// again (backTo). A panel still loading for the old project closes. The panel takes no press, key
// or Tab until a step has landed or a panel drawn again has read (holdPanel).
const REDRAWN = ["client", "gateway", "outside", "link"];
export function followProject() {
  const shown = panelState.current;
  if (!isPanelOpen() || !shown) return Promise.resolve();
  if (shown.type === "tool") return holdPanel(showTool(shown.server, shown.tool, { step: "fwd" }));
  if (shown.type === "held") return holdPanel(showHeld(shown.name, { step: "fwd" }));
  if (shown.type === "client") setState({ selected: { kind: "client", name: shown.client } });
  if (shown.type === "loading") closePanel({ focus: false });
  else if (REDRAWN.includes(shown.type) && panelState.from) return holdPanel(drawQuietly(panelState.from.read));
  return Promise.resolve();
}

// `rules` is the server's /api/gateway/tools answer. A tool that is gone since (its server left
// the gateway, or no longer lists it) closes its Details. Back from a step it slides in (`step`),
// focus on the first control of `focus` there.
function drawTool(serverName, name, rules, { warning = null, step = null, focus = [] } = {}) {
  const server = heldServer(current("gateway"), { kind: "mcp_server", name: serverName });
  const tool = server && (server.tool_list || []).find((t) => t.name === name);
  if (!tool) {
    closePanel();
    return;
  }
  const detail = (rules.tools || []).find((t) => t.name === name) || {};
  const card = toolCard(tool, server, { ...heldContext(), detail, rules, warning });
  const shown = openCard(card, { type: "tool", server: serverName, tool: name }, () => drawTool(serverName, name, rules, { warning }), () => showTool(serverName, name), step);
  if (step) return shown.then(() => focusAfterStep(...focus));
}

// Refresh tools asks every held server for its tools; when it is done the page reads the
// Gateway again, and these Details too while they are still shown. Focus stays on the button.
async function refreshHeld(name) {
  const error = await refreshTools();
  await reload().catch(() => {});
  render();
  const shown = panelState.current;
  if (!shown || shown.type !== "held" || shown.name !== name) return;
  await readThen(name, (answer) => {
    drawHeld(name, answer || {}, { warning: error || (answer ? answer.problem : "Could not load the details.") });
    // Refresh tools waits under More again: focus goes back to More.
    const again = withFocusKey($("#drawer"), "action:Refresh tools") || withFocusKey($("#drawer"), "more");
    if (again && $("#drawer").contains(document.activeElement)) again.focus();
  }, heldShown(name));
}

// Forms --------------------------------------------------------------------------------------

// What the person typed survives a redraw (a rescan can redraw the page at any time).
const EMPTY_ADD = { url: "", ui_url: "", auth: "none", key_env_var: "", login_email: "", login_password_env_var: "" };
const draft = { add: { ...EMPTY_ADD }, connect: null, connectOpen: null };
// Every client gets the same entry name; the review shows the exact entry before Apply.
const ENTRY_NAME = "gateway";
const PREVIEW = "Preview";

function field(label, control) {
  const box = el("label", "field");
  box.append(el("span", null, label), control);
  return box;
}

function input(attrs, value, onInput) {
  const node = el("input");
  Object.assign(node, attrs);
  node.value = value;
  node.addEventListener("input", () => onInput(node.value));
  return node;
}

// Connect clients to the gateway of this card, and only to it. The button says "In preview" while
// the row for the clients ticked now waits in the tray.
function connectForm(gateway, waiting) {
  if (!draft.connect || draft.connect.gateway !== gateway.id) {
    draft.connect = { gateway: gateway.id, clients: new Set(waiting) };
  }
  const chosen = draft.connect;
  const body = () => ({ action: "gateway.connect", targets: waiting.filter((c) => chosen.clients.has(c)).map((client) => ({ client })), params: { gateway: chosen.gateway, name: ENTRY_NAME } });
  const form = el("form", "form");
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  const submit = el("button", "btn primary");
  const words = el("span", "cut", PREVIEW);
  submit.type = "submit";
  submit.append(words);
  const follow = () => showInPreview(submit, words, PREVIEW, keyFor(body()));
  for (const client of waiting) {
    checks.append(clientCheck(client, chosen.clients.has(client), null, (checked) => {
      if (checked) chosen.clients.add(client); else chosen.clients.delete(client);
      follow();
    }));
  }
  form.append(checks);
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  follow();
  form.append(submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const { targets } = body();
    if (!targets.length) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    message.textContent = "";
    if (inTray(keyFor(body())) || submit.dataset.working) return;
    busyWhile(submit, review(body())).catch(reportError);
  });
  return form;
}

// Add a registered gateway. Saved, its Details open, where clients connect to it.
// The form to add a gateway. `onCancel`: it ends with a quiet Cancel too, which Escape in the form
// presses (the panel stays open).
export function addForm({ onCancel = null } = {}) {
  const typed = draft.add;
  const form = el("form", "form");
  const url = input({ type: "url", required: true, placeholder: "http://127.0.0.1:12008/metamcp/local/mcp or http://127.0.0.1:8080/mcp-connect/<id>", autocomplete: "off" }, typed.url, (v) => { typed.url = v; showFields(); });
  const ui = input({ type: "url", placeholder: "http://127.0.0.1:12008", autocomplete: "off" }, typed.ui_url, (v) => { typed.ui_url = v; });
  const login = el("select");
  for (const [value, text] of [["none", "None"], ["env_key", "Key in an environment variable"], ["oauth", "OAuth login"]]) {
    const option = el("option", null, text);
    option.value = value;
    login.append(option);
  }
  login.value = typed.auth;
  const key = input({ pattern: "[A-Z_][A-Z0-9_]*", placeholder: "GATEWAY_KEY", autocomplete: "off", spellcheck: false }, typed.key_env_var, (v) => { typed.key_env_var = v; });
  const keyLabel = el("span", null, "Variable name (not the key)");
  const keyField = el("label", "field");
  keyField.append(keyLabel, key);
  // The fields follow the address: an Obot gateway needs the variable that holds an API key
  // (Kitden reads what it holds with it, even when the clients sign in with OAuth); a MetaMCP
  // gateway needs a sign-in. The key or password itself is never typed into Kitden.
  const showFields = () => {
    const kind = kindOf(typed.url);
    const needsKey = login.value === "env_key" || kind === "obot";
    keyField.hidden = !needsKey;
    key.required = needsKey;
    keyLabel.textContent = kind === "obot" && login.value !== "env_key" ? "Obot API key variable name (not the key)" : "Variable name (not the key)";
    emailField.hidden = passwordField.hidden = kind === "obot";
  };
  login.addEventListener("change", () => { typed.auth = login.value; showFields(); });
  const urlField = field("MCP address", url);
  urlField.classList.add("grow");
  const uiField = field("Interface link (optional)", ui);
  uiField.classList.add("grow");
  // Sign-in for managing the gateway from here (feature 006). The password itself is never
  // typed into Kitden: only the name of the variable that holds it.
  const email = input({ type: "email", placeholder: "you@example.com", autocomplete: "off" }, typed.login_email, (v) => { typed.login_email = v; });
  const password = input({ pattern: "[A-Z_][A-Z0-9_]*", placeholder: "METAMCP_PASSWORD", autocomplete: "off", spellcheck: false }, typed.login_password_env_var, (v) => { typed.login_password_env_var = v; });
  const emailField = field("Sign-in email (to manage it from here)", email);
  emailField.classList.add("grow");
  const passwordField = field("Password variable name (not the password)", password);
  showFields();
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Save gateway");
  submit.type = "submit";
  form.append(urlField, uiField, field("Login", login), keyField, emailField, passwordField, submit);
  if (onCancel) {
    const cancel = button("Cancel", () => onCancel(), "btn");
    cancel.dataset.focus = "add-cancel";
    form.append(cancel);
    form.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      onCancel();
    });
  }
  form.append(message);
  async function save() {
    // The person's own action wins over an arrival still waiting (store.js).
    arrival.pending = false;
    {
      const result = await postJson("/api/gateways", {
        url: typed.url.trim(),
        ui_url: typed.ui_url.trim() || null,
        auth: typed.auth,
        key_env_var: typed.auth === "env_key" || kindOf(typed.url) === "obot" ? typed.key_env_var.trim() : null,
        login_email: typed.login_email.trim() || null,
        login_password_env_var: typed.login_password_env_var.trim() || null,
      });
      if (!result.ok) {
        message.className = "form-message error";
        message.textContent = (result.data && result.data.detail) || `Not saved (${result.status}).`;
        return;
      }
      draft.add = { ...EMPTY_ADD };
      await reload();
      render();
      toast("Gateway saved. Now connect your clients to it.");
      showGateway(result.data && result.data.id);
    }
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submit.dataset.working) return;
    busyWhile(submit, save()).catch(reportError);
  });
  return form;
}
