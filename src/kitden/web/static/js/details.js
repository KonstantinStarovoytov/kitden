// Item details: what an item is, where each client loads it from, and the actions on it.
import { getJson, query } from "./api.js";
import { $, button, el, joinWords, reportError, shortPath } from "./dom.js";
import { rowTitle, shownRow } from "./library.js";
import { about, addButton, addOptions, whyNoAction } from "./offer.js";
import { header, openInfo, openPanel, panelState, swapContent } from "./panel.js";
import { ALL_PROJECTS, callout, CLIENT_NAMES, CLIENT_ORDER, GATEWAY_NOTE, gatewayName, mark, socket, STATE_WORDS, toolsNode } from "./parts.js";
import { review } from "./review.js";
import { current as currentModel, currentError, data, projectPath, state } from "./store.js";
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
const ACTION_BUTTONS = {
  "plugin.disable": (client) => `Turn off in ${client}…`,
  "plugin.enable": (client) => `Turn on in ${client}…`,
  "mcp.remove_direct": (client) => `Remove from ${client}…`,
  "plugin.remove": (client) => `Remove from ${client}…`,
  "skill.remove": (client) => `Remove from ${client}…`,
};

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
  let definitions;
  try {
    const params = { name: row.lookup || row.name, kind: row.kind, project: state.project };
    // A command and an agent may share a name: ask for this row's one.
    if (row.category && row.kind === "instructions") params.category = row.category;
    definitions = (await getJson(`/api/explain${query(params)}`)).definitions;
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
  panelState.current.definitions = definitions;
  panelState.current.offer = offer;
  showDetails(row, definitions, offer, toolsNext);
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
// the warning's fix leads, then Move, then a lone action, then the first add. With a warning no
// button fixes, or a server to add in the gateway by hand first, nothing leads.
export function footerActions(offers, warnings, move, adds = []) {
  const fix = offers.find((o) => warnings.some((f) => f.fix_action === o.action && f.client === o.def.client));
  const canMove = Boolean(move && move.gateways.length);
  const options = [...(canMove ? ["move"] : []), ...offers, ...adds];
  let lead = fix || null;
  if (!lead && !warnings.length && canMove) lead = "move";
  if (!lead && !warnings.length && !move && offers.length === 1) lead = offers[0];
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

// A Details footer from footerActions: the lead is the primary button and the rest, then
// `commands`, wait under More. Without a lead every action is plain, after the commands.
// `draw(option, look)` gives an option's nodes.
// A button's words. When one client has more than one definition that can change, the label
// names the scope too, or the folder when the scopes are the same (one skill in two folders).
export function offerLabel({ def, action }, offers) {
  const twins = offers.filter((o) => o.def.client === def.client && o.def.id !== def.id);
  let where = "";
  if (twins.length) {
    const same = twins.some((o) => scopeWords(o.def) === scopeWords(def));
    where = ` (${same ? placeWords(def) : scopeWords(def).toLowerCase()})`;
  }
  return ACTION_BUTTONS[action](`${clientName(def.client)}${where}`);
}

// The folder a definition sits in, by its last two parts so the label stays short: a skill's
// skills folder (".agents/skills"), or the file of any other entry (".cursor/mcp.json").
function placeWords(def) {
  const parts = String(def.source || "").split("/").filter(Boolean);
  const place = parts[parts.length - 1] === "SKILL.md" ? parts.slice(0, -2) : parts;
  return place.slice(-2).join("/");
}

export function footerButtons({ lead, rest }, draw, commands = []) {
  if (lead) {
    const others = [...rest.flatMap((o) => draw(o, "btn")), ...commands];
    return [...(others.length ? [moreButton(others)] : []), ...draw(lead, "btn primary")];
  }
  const note = commands.length ? [el("span", "note", "Install, update or move to another client:"), ...commands] : [];
  return [...note, ...rest.flatMap((o) => draw(o, "btn"))];
}

// Where a definition applies, in the words the cells use: the picked project is "This project".
export function scopeWords(def, picked = projectPath()) {
  const project = def.project ? def.project.split("/").filter(Boolean).pop() : "";
  const words = {
    user: ALL_PROJECTS,
    project: def.project && def.project === picked ? "This project" : `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const via = def.owner_client && def.owner_client !== def.client ? ` · through ${clientName(def.owner_client)}'s folder` : "";
  return `${words}${via}`;
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
export function layerState(def) {
  let look = "off";
  let badge = "Not loaded";
  // The server's why starts with "Loads." for agents; the badge already says Available.
  let why = (def.why || "").replace(/^Loads\.\s*/, "");
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

function layer(def) {
  const { look, badge, why, unknown, stale } = layerState(def);
  const wins = def.loads && !unknown;
  const row = el("div", wins ? "layer wins" : "layer");
  const dot = socket({ state: look });
  dot.replaceChildren(dot.querySelector(".dot"));
  dot.setAttribute("aria-hidden", "true");
  const middle = el("div");
  middle.append(el("div", "name", scopeWords(def)));
  const where = el("div", "why mono", shortPath(def.source));
  where.title = def.source || "";
  middle.append(where);
  if (def.summary) middle.append(el("div", "why mono", def.summary));
  if (why) middle.append(el("div", "why", why));
  if (stale) middle.append(el("div", "why", stale));
  // An instruction file's first lines, secrets hidden by the server.
  if (def.preview && def.preview.length) middle.append(el("pre", "preview", def.preview.join("\n")));
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

// Details of a row on this computer: why nothing can be done (when so), what it is (`offer`, the
// marketplace's entry, when read), warnings, what each client loads, then every action.
// The definition whose tool count Details shows once: one in the Kitden gateway with a known
// count. Every client reaches the same held server, so the first one says it.
export function countedDefinition(definitions) {
  return definitions.find((d) => d.via_gateway === "kitden" && d.tools) || null;
}

function showDetails(row, definitions, offer = null, toolsNext = {}) {
  const warnings = row.flags.filter((x) => x.level === "warning");
  const move = moveFor(row, currentModel("gateway"), Boolean(currentError("gateway")));
  const offers = definitions.flatMap((def) => def.actions.filter((a) => ACTION_BUTTONS[a]).map((action) => ({ def, action })));
  const actions = footerActions(offers, warnings, move, addOptions(row, offer));
  const why = actions.lead || actions.rest.length ? "" : whyNoAction(row, definitions);
  const body = el("div", "body");
  if (why) body.append(el("p", "muted", why));
  if (offer) body.append(...about(offer));
  for (const f of warnings) body.append(callout(warningText(f)));
  // A warning that already says where to change it (a copy loaded from another client)
  // replaces the hints under that client, so the fact appears once.
  const covered = new Set(warnings.filter((f) => f.via).map((f) => f.client));
  const byClient = new Map();
  for (const def of definitions) {
    if (!byClient.has(def.client)) byClient.set(def.client, []);
    byClient.get(def.client).push(def);
  }
  const clients = [...byClient.keys()].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  for (const client of clients) {
    const section = el("section", "client-layers");
    const title = el("div", "chip");
    title.append(mark(client), el("h2", null, clientName(client)));
    const stack = el("div", "stack");
    for (const def of byClient.get(client)) stack.append(layer(def));
    section.append(title, stack);
    const hints = covered.has(client) ? [] : new Set(byClient.get(client).filter((d) => d.change_hint && !d.actions.length && d.change_hint !== why).map((d) => d.change_hint));
    for (const hint of hints) section.append(el("p", "muted", hint));
    body.append(section);
  }
  if (!definitions.length) body.append(el("p", "muted", "No definitions found for this item here."));
  // A server in the Kitden gateway: its tools, a switch each.
  if (definitions.some((d) => d.via_gateway === "kitden")) {
    const counted = countedDefinition(definitions);
    if (counted) body.append(toolsNode(counted));
    // Drawn again after a change with the row as the Library reads it now, so the line under
    // the title stays true.
    body.append(toolsSection(row.name, (next) => openItem(shownRow(row.key) || row, { tools: next }), toolsNext));
  }
  if (definitions.some((d) => d.secret_present)) {
    body.append(el("p", "muted", "This entry holds a secret. It is hidden here and never logged."));
  }
  if (move && move.unread) body.append(el("p", "muted", "Could not read the gateway, so Move is not offered."));
  else if (move && !move.gateways.length) body.append(el("p", "muted", GATEWAY_NOTE));

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
  footer.append(button("Back", () => showDetails(row, panelState.current.definitions, panelState.current.offer), "btn"));
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
