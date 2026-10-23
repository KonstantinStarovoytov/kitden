// Item details: what an item is, where each client loads it from, and the actions on it.
import { getJson, query } from "./api.js";
import { $, button, el, joinWords, plural, reportError, shortPath } from "./dom.js";
import { loadLibraryFor, raceSlow, rowSel, rowTitle, shownRow } from "./library.js";
import { fold } from "./motion.js";
import { about, addButton, addOptions, addReach, mcpRows, whyNoAction } from "./offer.js";
import { closePanel, header, openInfo, openPanel, panelState, swapContent } from "./panel.js";
import { ALL_PROJECTS, callout, CLIENT_NAMES, CLIENT_ORDER, GATEWAY_NOTE, gatewayName, mark, ROUTE_WORDS, socket, STATE_WORDS, toolsNode } from "./parts.js";
import { review } from "./review.js";
import { current as currentModel, currentError, data, goTo, libraryChoice, projectPath, state } from "./store.js";
import { toolsSection } from "./tools.js";

export const KIND_WORDS = {
  mcp_server: "MCP server", plugin: "Plugin", skill: "Skill", hook: "Hook", marketplace: "Marketplace",
};
const CATEGORY_WORDS = { instructions: "Instruction file", command: "Command", agent: "Agent" };

// The Details kicker: the kind, or for an instruction file its category.
export function kindWord(row) {
  if (row.kind === "instructions") return CATEGORY_WORDS[row.category] || "Instruction file";
  return KIND_WORDS[row.kind] || row.kind;
}
const WRITABLE = ["claude_code", "codex", "cursor"];
// A switch names its own client; a Remove names every client it reaches (offerLabel).
const ACTION_BUTTONS = {
  "plugin.disable": (client) => `Turn off in ${client}…`,
  "plugin.enable": (client) => `Turn on in ${client}…`,
  "mcp.remove_direct": (clients) => `Remove from ${clients}…`,
  "plugin.remove": (clients) => `Remove from ${clients}…`,
  "skill.remove": (clients) => `Remove from ${clients}…`,
};
const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove"];
// Whether Cursor loads Claude Code's plugins and the skills in its folder, before the server says.
const NO_INHERITS = { plugin: false, skill: false };

export const clientName = (id) => CLIENT_NAMES[id] || id;

// `tools` goes to the tool list of a server in the Kitden gateway (see toolsSection).
export async function openItem(row, { instant = false, tools: toolsNext = {} } = {}) {
  panelState.current = { type: "item", row };
  const body = el("div", "body");
  body.append(el("div", "skeleton card"));
  openPanel([itemHeader(row), body, el("footer")], { instant });
  // The marketplace's entry says what the item is; read beside the definitions. Without it the
  // rest still shows.
  const entry = row.offer ? getJson(`/api/offer${query({ kind: row.kind, id: row.offer })}`).catch(() => null) : null;
  let answer;
  try {
    const params = { name: row.lookup || row.name, kind: row.kind, project: state.project };
    // A command and an agent may share a name: ask for this row's one.
    if (row.category && row.kind === "instructions") params.category = row.category;
    answer = await getJson(`/api/explain${query(params)}`);
  } catch {
    if (panelState.current && panelState.current.row === row) {
      body.replaceChildren(callout("Could not load the details.", "error"));
      const footer = el("footer");
      footer.append(button("Retry", () => openItem(row), "btn"));
      $("#drawer footer").replaceWith(footer);
      if (!$("#drawer").contains(document.activeElement)) $("#drawer").focus();
    }
    return;
  }
  const offer = await entry;
  if (!panelState.current || panelState.current.row !== row) return;
  const { definitions } = answer;
  const inherits = answer.inherits || NO_INHERITS;
  Object.assign(panelState.current, { definitions, offer, inherits });
  showDetails(row, definitions, offer, toolsNext, inherits);
}

// The line under the Details title: the clients that have the item, those whose item of that
// name comes from another source, then those where the page cannot tell whether it is on. The
// same words for every kind, instruction files included.
export function loadsLede(row, columns) {
  const names = (states) => columns
    .filter((c) => states.includes(row.cells[c.id] && row.cells[c.id].state))
    .map((c) => c.name);
  const available = names(["on", "gw"]);
  const review = names(["review"]);
  const unknown = names(["unk"]);
  const lines = [];
  if (available.length) lines.push(`Available in ${joinWords(available)}.`);
  if (review.length) lines.push(`Needs review in ${joinWords(review)}: same name, another source.`);
  if (unknown.length) lines.push(`Unknown in ${joinWords(unknown)}.`);
  return lines.join(" ") || "Not available here.";
}

// The title names the source too when two rows share the name ("superpowers · cursor-public").
function itemHeader(row) {
  const map = currentModel("map");
  return header(kindWord(row), rowTitle(row), loadsLede(row, map ? map.columns : []), "Close", true);
}

// The warning names the fix; the server sends both (load_map.py).
function warningText(flag) {
  return flag.fix ? `${flag.text}. ${flag.fix}` : flag.text;
}

// Seen from the client with the warning, a change to the copy it loads from another client
// also changes that other client itself; say so next to the button.
const SIDE_EFFECTS = {
  "plugin.disable": "also turns it off for", "plugin.enable": "also turns it on for", "mcp.remove_direct": "also removes it from",
};
function sideEffect({ def, action }, warnings) {
  const reaches = warnings.some((f) => f.via === def.client && f.client !== def.client);
  if (!reaches || !SIDE_EFFECTS[action]) return [];
  return [el("span", "note side", `${SIDE_EFFECTS[action]} ${clientName(def.client)} itself`)];
}

// The gateways that can take the direct servers of one group of the Gateway page, in the order
// offered: the Kitden gateway first (it runs on this Mac, so it also takes local servers), then
// each registered gateway that takes servers (remote ones only).
export function moveTargets(model, group) {
  if (!model) return [];
  const kitden = model.gateways.filter((g) => g.kind === "kitden");
  if (group === "local") return kitden;
  if (group !== "move") return [];
  return [...kitden, ...model.gateways.filter((g) => g.kind !== "kitden" && g.movable)];
}

// A server the Gateway page lists as one that can move, with the entries a move takes and the
// gateways that can take them (none when it must be added in the gateway by hand). Without a
// gateway there is nothing to move into, so Details stays as it was. When the gateway could
// not be read (`unread`), Move cannot be judged: it is marked `unread`.
export function moveFor(row, model, unread = false) {
  if (row.kind !== "mcp_server") return null;
  if (!model) return unread ? { items: [], gateways: [], unread: true } : null;
  if (!model.gateways.length) return null;
  for (const group of ["move", "local"]) {
    const direct = (model.groups[group] || []).find((r) => r.name === row.name);
    if (!direct || !direct.items.length) continue;
    const gateways = moveTargets(model, group);
    // A local server no gateway here can take stays as it was: nothing to say about it.
    if (group === "move" || gateways.length) return { items: direct.items, gateways };
  }
  return null;
}

// The footer's lead action and the rest, in order; "move" stands for Move into the gateway, and
// `adds` are the ways to add the item (offer.js addOptions). A problem comes before an option:
// the warning's fix leads, then "Manage tools" (`tools`, the link to a server the Kitden gateway
// already holds: its tools come before moving the rest in), then Move, then a lone action, then
// the first add. A lone Remove gives way to an add, so the add the cell offers stays in sight; a
// lone switch still leads. With a warning no button fixes, or a server to add in the gateway by
// hand first, nothing leads. The link is never in `rest`: when it does not lead, it is a link.
export function footerActions(offers, warnings, move, adds = [], tools = null) {
  const fix = offers.find((o) => warnings.some((f) => f.fix_action === o.action && f.client === o.def.client));
  const canMove = Boolean(move && move.gateways.length);
  const options = [...(canMove ? ["move"] : []), ...offers, ...adds];
  const lone = offers.length === 1 && !(REMOVES.includes(offers[0].action) && adds.length);
  let lead = fix || null;
  if (!lead && !warnings.length && tools) lead = tools;
  if (!lead && !warnings.length && canMove) lead = "move";
  if (!lead && !warnings.length && !move && lone) lead = offers[0];
  if (!lead && !warnings.length && adds.length) lead = adds[0];
  return { lead, rest: options.filter((o) => o !== lead) };
}

// Move entries into a gateway. With one gateway that can take them the review opens at once;
// with two the panel asks which, the Kitden gateway first. A move into the Kitden gateway may
// ask the server for its tools first, so the button that started it stays busy until then.
export function moveInto(gateways, items, title) {
  const targets = items.map((item) => ({ item }));
  const preview = (gateway) => review({ action: "gateway.move", targets, params: { gateway: gateway.id } });
  if (gateways.length === 1) return preview(gateways[0]);
  const body = el("div", "body");
  body.append(el("p", "muted", "More than one gateway can take it. The Kitden gateway runs on this Mac and turns tools on or off per project."));
  const into = (gateway) => (gateway.kind === "kitden" ? "the Kitden gateway" : gatewayName(gateway));
  // The primary button sits last, so the Kitden gateway is drawn last.
  const choices = gateways.map((gateway, i) => button(`Move into ${into(gateway)}…`, () => preview(gateway), i === 0 ? "btn primary" : "btn"));
  openInfo("Move into the gateway", title, body, choices.reverse());
  return null;
}

function moveButton({ items, gateways }, look, name) {
  return button("Move into the gateway…", () => moveInto(gateways, items, name), look);
}

// A server in the Kitden gateway can leave it, or be written back into a client as its own
// entry. `clients` are the found clients Kitden can write. With `plain` (its entry still holds
// a secret) its secrets can move to the Keychain.
export function heldActions(server, clients, plain = false) {
  return [
    { label: "Remove from the Kitden gateway…", body: { action: "gateway.remove", targets: [], params: { server } } },
    ...clients.map((client) => ({
      label: `Put back in ${CLIENT_NAMES[client]}…`,
      body: { action: "gateway.put_back", targets: [{ client }], params: { server } },
    })),
    ...(plain ? [{ label: "Move secrets to the Keychain…", body: { action: "gateway.keychain", targets: [], params: { server } } }] : []),
  ];
}

// Whether the Kitden gateway's entry for `server` still holds a plain secret, as the Gateway
// page read it.
export function plainSecrets(model, server) {
  const kitden = model && (model.gateways || []).find((g) => g.kind === "kitden");
  return Boolean(kitden && (kitden.servers || []).some((s) => s.name === server && s.plain_secrets));
}

// heldActions as plain buttons, for both Details of a held server.
export function heldButtons(actions) {
  const draw = (a, look) => [button(a.label, () => review(a.body), look)];
  return footerButtons({ lead: null, rest: actions }, draw);
}

// The found clients Kitden can write, as the Gateway page reads them.
function writableClients() {
  return (data.clients || []).filter((c) => WRITABLE.includes(c.id) && c.status === "found").map((c) => c.id);
}

// The other actions wait behind one button, so the primary one stands alone.
function moreButton(buttons) {
  const more = button("More", () => {
    more.replaceWith(...buttons);
    buttons[0].focus();
  }, "btn");
  return more;
}

// A button's words. A Remove names every client it reaches (def.affects.clients): "Remove from
// Codex and Cursor…". When one client has more than one definition that can change, the label
// names the scope too, or the folder when the scopes are the same (one skill in two folders).
export function offerLabel({ def, action }, offers) {
  const twins = offers.filter((o) => o.def.client === def.client && o.def.id !== def.id);
  let where = "";
  if (twins.length) {
    const same = twins.some((o) => scopeWords(o.def) === scopeWords(def));
    where = ` (${same ? placeWords(def) : scopeWords(def).toLowerCase()})`;
  }
  const clients = REMOVES.includes(action) && def.affects ? def.affects.clients : [def.client];
  return ACTION_BUTTONS[action](`${joinWords(clients.map(clientName))}${where}`);
}

// The Affects line ---------------------------------------------------------------------------

const inOrder = (clients) => [...new Set(clients)].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));

// What the lead action changes, before any action: the clients, why other clients are reached
// (`note`), and where (`scope`): "all" projects, one "project" (`project`), or "others", all
// projects but the picked one, whose own definition of that one client wins over this one.
// `asks`: an add that asks "this project or all projects" next; it names only what both choices
// reach. `project` in the context is the picked project's path, "" for All projects; `found`, the
// clients on this computer; `connections`, the Gateway page's servers per gateway and client.
// Null when nothing leads, for the Add form, and when the server sent no reach for the
// definition.
export function affectsFor(lead, { definitions = [], move = null, connections = {}, inherits = NO_INHERITS, found = [], project = "" } = {}) {
  if (!lead || lead.form) return null;
  if (lead === "move") return moveAffects(definitions, move, connections);
  if (lead.def) return offerAffects(lead.def, definitions, project);
  if (lead.add) {
    const only = Boolean(lead.add.project_only);
    const asks = Boolean(project && lead.add.project_place);
    return { ...addReach(lead.client, lead.add.action, inherits, found, asks), scope: only ? "project" : "all", project: only ? project : null, asks };
  }
  // "Manage tools": a tool switch is one for every client that loads it through the Kitden
  // gateway, set for the picked project or for all projects. Held servers carry no actions, so
  // this reach is the page's own.
  if (lead.view === "gateway") {
    const clients = inOrder(definitions.filter((d) => d.via_gateway === "kitden").map((d) => d.client));
    return { clients, note: null, scope: project ? "project" : "all", project: project || null, asks: false };
  }
  return null;
}

function offerAffects(def, definitions, here) {
  if (!def.affects) return null;
  const affects = { ...def.affects, project: def.project || null, asks: false };
  const winner = def.overridden && here ? winnerOf(definitions, def) : null;
  const one = affects.clients.length === 1;
  if (affects.scope === "all" && one && winner && winner.project === here) affects.scope = "others";
  return affects;
}

// Move into the gateway: every entry it takes, and every client that reaches the gateway already,
// which then offers the server too (the review's "Via gateway" chips). With two gateways to
// choose from, only the clients every choice reaches. One project only when all the entries are
// in that project's files.
function moveAffects(definitions, move, connections = {}) {
  const defs = definitions.filter((d) => move && move.items.includes(d.id) && d.affects);
  if (!defs.length) return null;
  const reach = (gateway) => Object.entries((connections || {})[gateway.id] || {}).filter(([, names]) => names.length).map(([client]) => client);
  const [first = [], ...others] = move.gateways.map(reach);
  const every = first.filter((client) => others.every((list) => list.includes(client)));
  const notes = [...new Set(defs.map((d) => d.affects.note).filter(Boolean))];
  const places = new Set(defs.map((d) => (d.affects.scope === "project" ? d.project : null)));
  const [place] = places;
  const one = places.size === 1 && place ? place : null;
  const clients = inOrder([...defs.flatMap((d) => d.affects.clients), ...every]);
  return { clients, note: notes.join("; ") || null, scope: one ? "project" : "all", project: one, asks: false };
}

// The Affects line: "Changes Codex and Cursor (Cursor reads Codex's folder). All projects."
// `here`: the picked project's path, "" for All projects. "" without an affects.
export function affectsText(affects, here) {
  if (!affects) return "";
  const note = affects.note ? ` (${affects.note})` : "";
  return `Changes ${joinWords(affects.clients.map(clientName))}${note}. ${placeText(affects, here)}`;
}

function placeText({ scope, project, asks }, here) {
  if (asks) return "You choose this project or all projects next.";
  if (scope === "others") return "All projects except this one.";
  if (scope === "project") return project && project === here ? "In this project." : `In ${folderName(project)}.`;
  return "All projects.";
}

// Links that keep context -------------------------------------------------------------------

// The same item on another page; never the page shown. "Manage tools" only for a server in the
// Kitden gateway: the only servers with tool switches (the Gateway opens a server by its name).
// "Show on the map" joins them once the map exists (Part 6).
export function contextLinks(row, definitions, view) {
  const links = [];
  if (view !== "library") links.push({ label: "Compare across clients", view: "library", selected: rowSel(row) });
  if (view !== "gateway" && definitions.some((d) => d.via_gateway === "kitden")) {
    links.push({ label: "Manage tools", view: "gateway", selected: { kind: "mcp_server", name: row.name } });
  }
  return links;
}

// Go to the item on the link's page, which opens it there. The panel closes first, so the
// arrival opens; the Library's rows are read first, as the rail reads them. Project and
// selection stay.
export async function followLink(link) {
  closePanel({ keepSelection: true, focus: false });
  if (link.view === "library") await raceSlow(loadLibraryFor(libraryChoice(link.selected)), 300);
  goTo(link.view, link.selected);
}

function linkButton(link, look) {
  const node = button(link.label, () => followLink(link), look);
  node.dataset.focus = `link:${link.view}`;
  return node;
}

// The links in Details: one quiet row of buttons.
export function linksRow(links) {
  const row = el("div", "links");
  row.append(...links.map((link) => linkButton(link, "btn small ghost")));
  return row;
}

// The folder a definition sits in, by its last two parts so the label stays short: a skill's
// skills folder (".agents/skills"), or the file of any other entry (".cursor/mcp.json").
function placeWords(def) {
  const parts = String(def.source || "").split("/").filter(Boolean);
  const place = parts[parts.length - 1] === "SKILL.md" ? parts.slice(0, -2) : parts;
  return place.slice(-2).join("/");
}

// A Details footer from footerActions: the lead is the primary button and the rest, then
// `commands`, wait under More. Without a lead every action is plain, after the commands.
// `draw(option, look)` gives an option's nodes.
export function footerButtons({ lead, rest }, draw, commands = []) {
  if (lead) {
    const others = [...rest.flatMap((o) => draw(o, "btn")), ...commands];
    return [...(others.length ? [moreButton(others)] : []), ...draw(lead, "btn primary")];
  }
  const note = commands.length ? [el("span", "note", "Install, update or move to another client:"), ...commands] : [];
  return [...note, ...rest.flatMap((o) => draw(o, "btn"))];
}

const folderName = (path) => (path ? path.split("/").filter(Boolean).pop() : "");

// The client whose folder or file this definition is read from, when it is another of the
// three clients (WRITABLE). "shared" (~/.agents/skills) and the Kitden gateway are not
// clients: the Why says a shared folder in words, and a held server's route.
function ownerName(def) {
  const owner = def.owner_client;
  return owner && owner !== def.client && WRITABLE.includes(owner) ? clientName(owner) : null;
}

// Where a definition applies, in the words the cells use: the picked project is "This project".
export function scopeWords(def, picked = projectPath()) {
  const project = folderName(def.project);
  const words = {
    user: ALL_PROJECTS,
    project: def.project && def.project === picked ? "This project" : `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const owner = ownerName(def);
  return owner ? `${words} · ${ROUTE_WORDS.folder.replace("{}", owner)}` : words;
}

// Where a definition's file sits, in file words. Only the technical details say these: spec
// 2.1 keeps "global settings" there.
export function fileScopeWords(def) {
  const project = folderName(def.project);
  const words = {
    user: "Global settings",
    project: `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const owner = ownerName(def);
  return owner ? `${words} · via ${owner}` : words;
}

// How a client gets a definition, in Part 2's route words (as load_map.py `_route` picks
// them), or null for the client's own plain entry.
function routeWords(def) {
  if (def.client === "claude_desktop_code_tab") return ROUTE_WORDS.desktop;
  if (def.via_gateway === "kitden") return ROUTE_WORDS.kitden;
  const owner = ownerName(def);
  if (owner) return ROUTE_WORDS.folder.replace("{}", owner);
  return def.scope === "plugin" ? ROUTE_WORDS.plugin : null;
}

// Where an entry of each other scope loads from, in the Why.
const FROM_WORDS = {
  user: "from all projects", plugin: ROUTE_WORDS.plugin, managed: "from your organization", account: "from your Claude account",
};

// Where a definition applies, as the Why says it: "from this project", "from all projects".
function scopeOrigin(def, here) {
  if (def.scope === "project" || def.scope === "local") {
    return def.project && def.project === here ? "from this project" : `from ${folderName(def.project)}`;
  }
  return FROM_WORDS[def.scope] || `from ${def.scope}`;
}

// Where a client loads a definition from, for the Why: the route first, then the scope.
// `here` is the picked project's path, or null for All projects.
export function originWords(def, here) {
  return routeWords(def) || scopeOrigin(def, here);
}

const inClientOrder = (definitions) => [...definitions].sort((a, b) => CLIENT_ORDER.indexOf(a.client) - CLIENT_ORDER.indexOf(b.client));
const clientsOf = (definitions) => [...new Set(definitions.map((d) => clientName(d.client)))];

// A definition no rule ties to another one, that does not load: the Why may say why instead
// of its own line (turned off, or only in another project).
const standsAlone = (def) => def.kind !== "instructions" && !def.loads && !def.overridden && !def.merged;
const elsewhere = (def, here) => Boolean(def.project) && def.project !== here;

// The Why: one or two quiet lines (whyLines), and `said`, the definitions whose own line it
// replaces, so a fact shows once (layerState). First where each client loads it from, grouped
// by where ("Codex and Cursor load it from all projects."). Then what decides, in one line: one
// folder several clients read, or one definition over another of the same client; the projects
// it is in when it does not load here; what is turned off, by client, or by project for another
// project's copy. None for instruction files: their own lines say when each client reads them.
// An unknown state's reason stays on its layer.
export function whyParts(definitions, here) {
  const said = new Set();
  if (!definitions.length || definitions.some((d) => d.kind === "instructions")) return { lines: [], said };
  const defs = inClientOrder(definitions);
  const groups = new Map(); // where it loads from -> the clients
  for (const def of defs.filter((d) => d.loads && d.enabled !== "unknown")) {
    const origin = originWords(def, here);
    const names = groups.get(origin) || [];
    if (!names.includes(clientName(def.client))) names.push(clientName(def.client));
    groups.set(origin, names);
  }
  const parts = [...groups].map(([origin, names], i) => {
    const verb = i ? "" : names.length > 1 ? " load it" : " loads it";
    return `${joinWords(names)}${verb} ${origin}`;
  });
  const rules = [sharedFolder(defs) || heldRule(defs, here, said) || overRule(defs, here)].filter(Boolean);
  const away = defs.filter((d) => standsAlone(d) && elsewhere(d, here) && (d.enabled === "on" || d.enabled === "off"));
  if (away.some((d) => d.enabled === "on")) {
    const count = plural(new Set(away.map((d) => d.project)).size, "project", "projects");
    rules.push(parts.length ? `It is also in ${count}.` : `It is in ${count}; it loads only there.`);
    for (const d of away.filter((x) => x.enabled === "on")) said.add(d);
  }
  // Turned off: a copy in another project, or a client that loads no other copy.
  const loading = new Set(defs.filter((d) => d.loads).map((d) => d.client));
  const off = defs.filter((d) => standsAlone(d) && d.enabled === "off" && !said.has(d) && (elsewhere(d, here) || !loading.has(d.client)));
  if (off.length) {
    const where = off.map((d) => (elsewhere(d, here) ? folderName(d.project) : clientName(d.client)));
    rules.push(`Turned off in ${joinWords([...new Set(where)])}.`);
    for (const d of off) said.add(d);
  }
  const lines = [...(parts.length ? [`${parts.join("; ")}.`] : []), ...(rules.length ? [rules.join(" ")] : [])];
  return { lines, said };
}

export function whyLines(definitions, here) {
  return whyParts(definitions, here).lines;
}

// One skill folder that several clients read.
function sharedFolder(defs) {
  const folders = new Map(); // a skill's folder -> the definitions read from it
  for (const def of defs.filter((d) => d.kind === "skill" && String(d.source || "").includes("/"))) {
    folders.set(def.source, [...(folders.get(def.source) || []), def]);
  }
  const shared = [...folders.values()].find((list) => clientsOf(list).length > 1);
  return shared ? `One folder, read by ${joinWords(clientsOf(shared))}.` : null;
}

// The definition of the same client that `beaten` gives way to: one that loads, else the first
// that is not beaten itself.
function winnerOf(defs, beaten) {
  const others = defs.filter((d) => d.client === beaten.client && d !== beaten && !d.overridden && !d.merged);
  return others.find((d) => d.loads) || others[0];
}

// A server in the Kitden gateway with a switch of its own in the project: said plainly, since
// both definitions come through the gateway. The switch is one for every client: when it is off
// for all of them, the line says so once and stands for each client's "turned off" (`said`).
function heldRule(defs, here, said) {
  const held = defs.filter((d) => {
    const winner = (d.overridden || d.merged) && d.via_gateway === "kitden" && winnerOf(defs, d);
    return winner && winner.via_gateway === "kitden" && winner.project;
  });
  if (!held.length) return null;
  const winners = held.map((d) => winnerOf(defs, d));
  const whose = winners[0].project === here ? "this project's" : `${folderName(winners[0].project)}'s`;
  if (winners.every((w) => w.enabled === "off")) {
    for (const w of winners) said.add(w);
    return `In the Kitden gateway, ${whose} switch for ${winners[0].name} is off.`;
  }
  const names = clientsOf(held.filter((d, i) => winners[i].enabled !== "off"));
  return `${joinWords(names)} ${names.length > 1 ? "use" : "uses"} ${whose} switch for ${winners[0].name} in the Kitden gateway.`;
}

// One definition over another of the same client. When both come the same way, their scopes
// tell them apart; when those match too, it says so.
function overRule(defs, here) {
  const beaten = defs.find((d) => d.overridden && winnerOf(defs, d)) || defs.find((d) => d.merged && winnerOf(defs, d));
  if (!beaten) return null;
  const winner = winnerOf(defs, beaten);
  const client = clientName(beaten.client);
  let [a, b] = [originWords(winner, here), originWords(beaten, here)];
  if (a === b) [a, b] = [scopeOrigin(winner, here), scopeOrigin(beaten, here)];
  if (a === b) return `In ${client}, two of them come ${a}; ${beaten.merged ? "they are merged" : "only one loads"}.`;
  return beaten.merged ? `In ${client}, the ones ${a} and ${b} are merged.` : `In ${client}, the one ${a} overrides the one ${b}.`;
}

// The evidence under "Technical details", in client order: one row per file, file key,
// command and first lines, titled with every client that reads it and the file words
// ("Codex and Cursor · Global settings"). A held server's entry is the Kitden gateway's own.
export function techRows(definitions) {
  const rows = new Map(); // the same evidence -> one row and its definitions
  for (const def of inClientOrder(definitions)) {
    const row = {
      client: def.client,
      path: String(def.source || "").includes("/") ? def.source : null,
      key: def.key || null,
      summary: def.summary || null,
      preview: def.preview && def.preview.length ? def.preview : null,
    };
    if (!row.path && !row.key && !row.summary && !row.preview) continue;
    const id = JSON.stringify([row.path, row.key, row.summary, row.preview]);
    if (!rows.has(id)) rows.set(id, { row, defs: [] });
    rows.get(id).defs.push(def);
  }
  return [...rows.values()].map(({ row, defs }) => {
    const who = defs[0].via_gateway === "kitden" ? CLIENT_NAMES.kitden : joinWords(clientsOf(defs));
    return { ...row, title: `${who} · ${fileScopeWords(defs[0])}` };
  });
}

// The evidence, folded: per definition its file (the whole path in the hover text), file key,
// command and first lines. It opens like "Show file change" in a review.
export function technical(rows) {
  const box = el("details", "tech");
  box.append(el("summary", null, "Technical details"));
  for (const r of rows) {
    const part = el("div", "tech-row");
    part.append(el("div", "name", r.title));
    if (r.path) {
      const where = el("div", "mono", shortPath(r.path));
      where.title = r.path;
      part.append(where);
    }
    if (r.key) part.append(el("div", "mono", r.key));
    if (r.summary) part.append(el("div", "mono", r.summary));
    // An instruction file's first lines, secrets hidden by the server.
    if (r.preview) part.append(el("pre", "preview", r.preview.join("\n")));
    box.append(part);
  }
  return fold(box);
}

// The five questions Details answers, in order: what it is and its state (the header), why,
// what the lead action changes and what else to do (the footer), then the evidence. Each id is
// a block of the body; a block with nothing to say is left out.
export const DETAILS_ORDER = ["warnings", "about", "why", "clients", "tools", "secret", "next", "links", "technical"];

export function detailsOrder(present) {
  return DETAILS_ORDER.filter((id) => present.has(id));
}

const UNKNOWN_WORDS = {
  stored_in_account: "Its on/off state is kept in your Claude account, not on this Mac.",
  no_access: "This page could not read where its state is kept.",
  unrecognized_format: "Its state is kept in a format this page does not know.",
  parse_error: "The file that holds its state could not be read.",
  may_be_stale: "The saved state may be out of date.",
  not_documented: "The client does not document where its state is kept.",
};

// When a definition kept from the last good read was read, on this Mac's clock (the twin of
// views/words.py STALE): "From the last good read at 14:02".
function staleWords(at) {
  const time = new Date(at);
  const two = (n) => String(n).padStart(2, "0");
  return `From the last good read at ${two(time.getHours())}:${two(time.getMinutes())}`;
}

// A definition's dot, badge and line of why. An instruction file says it is available, or
// that it is in a project, never "Not loaded": its why says when it is read. A definition kept
// from the last good read also says when (`stale`).
export function layerState(def, said = new Set()) {
  let look = "off";
  let badge = "Not loaded";
  // The server's why is written for agents ("Loads. It overrides the user definition."). The
  // badge says Available, and the Why lines say in page words which definition overrides or
  // merges with which; such a definition has no line of its own. Nor has one whose line the
  // Why says instead (`said`, from whyParts): turned off, or only in another project.
  const ruled = def.kind !== "instructions" && (def.loads || def.overridden || def.merged);
  let why = ruled || said.has(def) ? "" : def.why || "";
  const unknown = def.enabled === "unknown";
  if (unknown) {
    look = "unk";
    badge = "Unknown";
    why = UNKNOWN_WORDS[def.unknown_reason] || "This page cannot tell whether it is on.";
  } else if (def.kind === "instructions") {
    if (def.loads) look = "on";
    badge = def.loads ? STATE_WORDS.on : def.project ? "In a project" : "";
  } else if (def.loads) { look = def.via_gateway ? "gw" : "on"; badge = STATE_WORDS.on; }
  else if (def.merged) badge = "Merged";
  else if (def.overridden) { look = "over"; badge = "Overridden"; }
  else if (def.enabled === "off") badge = "Off";
  const stale = def.stale_at ? staleWords(def.stale_at) : null;
  return { look, badge, why, unknown, stale };
}

function layer(def, said) {
  const { look, badge, why, unknown, stale } = layerState(def, said);
  const wins = def.loads && !unknown;
  const row = el("div", wins ? "layer wins" : "layer");
  const dot = socket({ state: look });
  dot.replaceChildren(dot.querySelector(".dot"));
  dot.setAttribute("aria-hidden", "true");
  // The file, the command and the first lines wait under Technical details.
  const middle = el("div");
  middle.append(el("div", "name", scopeWords(def)));
  if (why) middle.append(el("div", "why", why));
  if (stale) middle.append(el("div", "why", stale));
  // Every plugin with a known state gets the same switch; one the page cannot change from
  // here (its on/off lives in the client's account) is shown locked, with the reason.
  const toggle = !unknown && def.kind === "plugin" && def.actions.find((a) => a === "plugin.disable" || a === "plugin.enable");
  const known = !unknown && def.kind === "plugin" && (def.enabled === "on" || def.enabled === "off");
  const control = toggle ? pluginSwitch(def, toggle) : known ? pluginSwitch(def, null) : badge ? el("span", wins ? "badge win" : "badge", badge) : el("span");
  row.append(dot, middle, control);
  return row;
}

// A switch that shows a real state. Pressing it runs `press`, which opens the review; it flips
// only when the change is written and checked, never before. Without `press` it only shows.
export function switchNode(on, press) {
  const node = el("button", "switch");
  node.type = "button";
  node.setAttribute("role", "switch");
  node.setAttribute("aria-checked", String(on));
  node.append(el("span", "thumb"));
  if (!press) return node;
  node.title = on ? "On. Press to review turning it off." : "Off. Press to review turning it on.";
  // While the preview is fetched the thumb rests half-way: pending, not flipped.
  node.addEventListener("click", async () => {
    if (node.classList.contains("pending")) return;
    node.classList.add("pending");
    node.setAttribute("aria-busy", "true");
    try {
      await press();
    } catch (error) {
      reportError(error);
    } finally {
      node.classList.remove("pending");
      node.removeAttribute("aria-busy");
    }
  });
  return node;
}

// The plugin's real state; the Library shows the new state after a change. Without an action
// the switch is locked: it shows the state and says where to change it.
function pluginSwitch(def, action) {
  const on = action ? action === "plugin.disable" : def.enabled === "on";
  const node = switchNode(on, action ? () => review({ action, targets: [{ item: def.id }], params: {} }) : null);
  if (!action) {
    node.disabled = true;
    node.setAttribute("aria-label", `${on ? "On" : "Off"} in ${clientName(def.client)}; not changed from here`);
    node.title = def.change_hint || "Not changed from here.";
    return node;
  }
  node.setAttribute("aria-label", `${on ? "Turn off" : "Turn on"} in ${clientName(def.client)}…`);
  return node;
}

// The definition whose tool count Details shows once: one in the Kitden gateway with a known
// count. Every client reaches the same held server, so the first one says it.
export function countedDefinition(definitions) {
  return definitions.find((d) => d.via_gateway === "kitden" && d.tools) || null;
}

// Details of a row on this computer, in DETAILS_ORDER: warnings, what it is (`offer`, the
// marketplace's entry, when read), why, what each client loads, the tools, then what to do next
// (what the lead action changes, or why nothing can be done), links to the item on other pages,
// and the evidence, folded. Every action is in the footer.
function showDetails(row, definitions, offer = null, toolsNext = {}, inherits = NO_INHERITS) {
  const warnings = row.flags.filter((x) => x.level === "warning");
  const move = moveFor(row, currentModel("gateway"), Boolean(currentError("gateway")));
  const offers = definitions.flatMap((def) => def.actions.filter((a) => ACTION_BUTTONS[a]).map((action) => ({ def, action })));
  const links = contextLinks(row, definitions, state.view);
  const manage = links.find((link) => link.view === "gateway") || null;
  const actions = footerActions(offers, warnings, move, addOptions(row, offer), manage);
  const why = actions.lead || actions.rest.length ? "" : whyNoAction(row, definitions);
  const blocks = new Map(); // a DETAILS_ORDER id -> its nodes
  if (warnings.length) blocks.set("warnings", warnings.map((f) => callout(warningText(f))));
  if (offer) blocks.set("about", about(offer));
  const { lines, said } = whyParts(definitions, projectPath());
  if (lines.length) {
    const box = el("div", "why-lines");
    box.append(...lines.map((line) => el("p", null, line)));
    blocks.set("why", [box]);
  }
  // A warning that already says where to change it (a copy loaded from another client)
  // replaces the hints under that client, so the fact appears once.
  const covered = new Set(warnings.filter((f) => f.via).map((f) => f.client));
  const byClient = new Map();
  for (const def of definitions) {
    if (!byClient.has(def.client)) byClient.set(def.client, []);
    byClient.get(def.client).push(def);
  }
  const clients = [...byClient.keys()].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const sections = [];
  for (const client of clients) {
    const section = el("section", "client-layers");
    const title = el("div", "chip");
    title.append(mark(client), el("h2", null, clientName(client)));
    const stack = el("div", "stack");
    for (const def of byClient.get(client)) stack.append(layer(def, said));
    section.append(title, stack);
    const hints = covered.has(client) ? [] : new Set(byClient.get(client).filter((d) => d.change_hint && !d.actions.length && d.change_hint !== why).map((d) => d.change_hint));
    for (const hint of hints) section.append(el("p", "muted", hint));
    sections.push(section);
  }
  if (!definitions.length) sections.push(el("p", "muted", "No definitions found for this item here."));
  blocks.set("clients", sections);
  // A server in the Kitden gateway: its tools, a switch each.
  if (definitions.some((d) => d.via_gateway === "kitden")) {
    const counted = countedDefinition(definitions);
    // Drawn again after a change with the row as the Library reads it now, so the line under
    // the title stays true.
    const list = toolsSection(row.name, (next) => openItem(shownRow(row.key) || row, { tools: next }), toolsNext);
    blocks.set("tools", [...(counted ? [toolsNode(counted)] : []), list]);
  }
  if (definitions.some((d) => d.secret_present)) {
    blocks.set("secret", [el("p", "muted", "This entry holds a secret. It is hidden here and never logged.")]);
  }
  const next = [];
  // What the lead action changes, before any action.
  const here = projectPath();
  const gateway = currentModel("gateway");
  const reach = { definitions, move, connections: gateway ? gateway.connections : {}, inherits, found: writableClients(), project: here };
  const affects = affectsText(affectsFor(actions.lead, reach), here);
  if (affects) next.push(el("p", "affects", affects));
  // With nothing to do, say why, quietly.
  if (why) next.push(el("p", "muted", why));
  if (move && move.unread) next.push(el("p", "muted", "Could not read the gateway, so Move is not offered."));
  else if (move && !move.gateways.length) next.push(el("p", "muted", GATEWAY_NOTE));
  if (next.length) blocks.set("next", next);
  // A link that leads is in the footer, not here too.
  const shown = links.filter((link) => link !== actions.lead);
  if (shown.length) blocks.set("links", [linksRow(shown)]);
  // What the marketplace's entry runs joins the evidence.
  const rows = [...techRows(definitions), ...(offer ? mcpRows(offer) : [])];
  if (rows.length) blocks.set("technical", [technical(rows)]);
  const body = el("div", "body");
  for (const id of detailsOrder(new Set(blocks.keys()))) body.append(...blocks.get(id));

  const withCommands = definitions.filter((d) => d.kind === "plugin" || d.kind === "marketplace");
  const commands = withCommands.length ? [button("Commands…", () => showCommands(row, withCommands), "btn")] : [];
  const buttonFor = ({ def, action }, look) => {
    const label = offerLabel({ def, action }, offers);
    const node = button(null, () => review({ action, targets: [{ item: def.id }], params: {} }), look);
    // A narrow panel cuts the words with "…"; the whole label stays in the hover text.
    node.title = label;
    node.append(el("span", "cut", label));
    return node;
  };
  // A plain action names what else it changes; the primary one stands alone.
  const draw = (o, look) => {
    if (o === "move") return [moveButton(move, look, row.name)];
    if (o.view) return [linkButton(o, look)];
    if (o.def) return [...(look === "btn" ? sideEffect(o, warnings) : []), buttonFor(o, look)];
    return [addButton(o, row, offer, look)];
  };
  const footer = el("footer");
  const held = definitions.some((d) => d.via_gateway === "kitden") ? heldButtons(heldActions(row.name, writableClients(), plainSecrets(currentModel("gateway"), row.name))) : [];
  footer.append(...held, ...footerButtons(actions, draw, commands));
  swapContent([itemHeader(row), body, footer]);
}

async function showCommands(row, definitions) {
  const body = el("div", "body");
  body.append(el("p", "muted", "You run these yourself. This page never runs them."));
  const footer = el("footer");
  const { definitions: all, offer, inherits } = panelState.current;
  footer.append(button("Back", () => showDetails(row, all, offer, {}, inherits), "btn"));
  swapContent([header("Commands", row.name, null, "Close", true), body, footer]);
  const seen = new Set();
  for (const def of definitions) {
    if (seen.has(def.id)) continue;
    seen.add(def.id);
    const twins = definitions.filter((d) => d.client === def.client).length > 1;
    const section = el("section");
    const title = el("div", "chip");
    title.append(mark(def.client), el("h2", null, twins ? `${clientName(def.client)} · ${scopeWords(def)}` : clientName(def.client)));
    const list = el("ul", "commands");
    list.append(el("li", "muted", "Loading…"));
    section.append(title, list);
    body.append(section);
    try {
      const result = await getJson(`/api/commands${query({ item: def.id })}`);
      list.replaceChildren();
      for (const command of result.commands) {
        const li = el("li");
        li.append(el("strong", null, command.label));
        if (command.command) li.append(el("pre", null, command.command));
        if (command.note) li.append(el("p", "muted", command.note));
        list.append(li);
      }
      if (!result.commands.length) list.append(el("li", "muted", "No commands for this item."));
    } catch {
      list.replaceChildren(el("li", null, "Could not load the commands."));
    }
  }
}
