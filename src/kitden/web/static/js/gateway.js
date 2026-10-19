// Gateway: which clients reach it, and which servers are not connected to it.
import { getJson, postJson } from "./api.js";
import { button, el, plural, webLink } from "./dom.js";
import { entrance, fold, reducedMotion } from "./motion.js";
import { openInfo, openItem, review, toast } from "./panel.js";
import { banner, CLIENT_ICONS, CLIENT_NAMES, DARK_ICONS, flag, mark, skeleton, staleNote } from "./parts.js";
import { current, currentError, data, freshness, loadGateway, loadMap, reload, render, state } from "./store.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
const GROUPS = [
  ["move", "Can move into the gateway", "Moving adds the server to the gateway, then removes its direct entry here."],
  ["local", "Must run on this Mac", "Local servers start a program here; a gateway cannot reach them. Nothing to do."],
  ["plugin", "Come with a plugin", "Turn the plugin off if you do not want them."],
];

// What the person typed survives a redraw (a rescan can redraw the page at any time).
const EMPTY_ADD = { url: "", ui_url: "", auth: "none", key_env_var: "", login_email: "", login_password_env_var: "" };
const draft = { add: { ...EMPTY_ADD }, connect: null, addOpen: false, connectOpen: null };
// Every client gets the same entry name; the review shows the exact entry before Apply.
const ENTRY_NAME = "gateway";

// Which gateway an address belongs to, told from its path (the server does the same).
export function kindOf(url) {
  try {
    const path = new URL(url).pathname;
    if (path.startsWith("/metamcp/")) return "metamcp";
    if (path.startsWith("/mcp-connect/")) return "obot";
  } catch { /* not an address yet */ }
  return "other";
}

const KIND_NAMES = { metamcp: "MetaMCP", obot: "Obot" };

export function gatewayName(gateway) {
  const kind = gateway.kind || kindOf(gateway.url);
  if (KIND_NAMES[kind]) return KIND_NAMES[kind];
  try { return new URL(gateway.url).host || "Gateway"; } catch { return "Gateway"; }
}

function foundClients() {
  return (data.clients || []).filter((c) => WRITABLE.includes(c.id) && c.status === "found").map((c) => c.id);
}

export function renderGateway(main) {
  main.append(el("h1", null, "Gateway"));
  main.append(el("p", "lede", "Turn MCP tools on and off in the gateway, not in each client. Here you see which clients reach it and which servers are not connected to it."));
  const model = current("gateway");
  if (!model) {
    if (currentError("gateway")) main.append(banner("the gateway", async () => { await loadGateway(); render(); }));
    else main.append(skeleton("card", 2));
    return;
  }
  if (currentError("gateway")) main.append(staleNote(data.readAt.gateway));

  const blocks = [];
  if (!model.gateways.length) {
    const card = el("section", "card");
    card.append(el("h2", null, "No gateway yet"));
    card.append(el("p", "muted", "A gateway keeps your MCP servers in one place: each client needs one entry, and you turn tools on or off once."));
    card.append(addForm());
    main.append(card);
    entrance("gateway", [card]);
    return;
  }

  // The gateway the clients use gets the big card with the routes; the others follow.
  const ordered = [...model.gateways].sort((a, b) => Number(model.used.includes(b.id)) - Number(model.used.includes(a.id)));
  const [first, ...others] = ordered;
  const card = gatewayCard(first, model);
  main.append(card);
  blocks.push(card);
  for (const gateway of others) {
    const more = el("section", "card");
    more.append(gatewayHead(gateway, model), heldSection(gateway));
    main.append(more);
    blocks.push(more);
  }

  // The gateway Kitden can manage from here takes the servers that move.
  const target = model.gateways.find((g) => g.movable) || null;
  // One heading says what the lists below are: MCP servers that reach a client directly.
  if (GROUPS.some(([key]) => model.groups[key].length)) {
    const title = el("h2", "section-title", "MCP servers not in the gateway");
    main.append(title);
    blocks.push(title);
  }
  for (const [key, title, note] of GROUPS) {
    const rows = model.groups[key];
    if (!rows.length) continue;
    // The heading counts entries, as the Overview does; a server in two clients is one row.
    const entries = rows.reduce((n, row) => n + row.clients.length, 0);
    const count = entries === rows.length ? String(entries) : `${entries} entries in ${plural(rows.length, "server", "servers")}`;
    const section = el("section");
    const head = el("div", "group-head");
    head.append(el("h3", "group-title", `${title} · ${count}`));
    const movable = key === "move" && target ? rows.flatMap((row) => row.items) : [];
    if (movable.length) {
      const targets = movable.map((item) => ({ item }));
      head.append(button(`Move all ${movable.length}…`, () => review({ action: "gateway.move", targets, params: { gateway: target.id } })));
    }
    section.append(head, el("p", "group-note", key === "move" && !target ? "Add the server in the gateway first, then remove its direct entry here." : note));
    const list = el("div", "list");
    for (const row of rows) list.append(groupRow(row, key, target));
    section.append(list);
    main.append(section);
    blocks.push(section);
  }

  const more = el("details", "add-more");
  more.open = draft.addOpen;
  more.addEventListener("toggle", () => { draft.addOpen = more.open; });
  more.append(el("summary", null, "Add another gateway"), addForm());
  main.append(fold(more));
  entrance("gateway", blocks);
}

function gatewayHead(gateway, model) {
  const head = el("div", "gw-head");
  const left = el("div");
  // With two gateways, say which one the clients use.
  const used = model.gateways.length > 1 ? ` · ${model.used.includes(gateway.id) ? "Used" : "Not used"}` : "";
  left.append(el("div", "kicker", `${gatewayName(gateway)}${used}`), el("div", "gw-url", gateway.url));
  const right = el("div");
  if (gateway.ui_url) {
    // A small side door: everything the page can do happens here.
    const link = webLink(gateway.ui_url, `Open ${gatewayName(gateway)} ↗`);
    link.classList.add("small", "ghost");
    right.append(link);
  }
  // Clients use another gateway: one review moves all of them here (the old entries go).
  if (model.used.length && !model.used.includes(gateway.id)) {
    const name = gatewayName(gateway).toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
    right.append(button("Use this gateway…", () => review({ action: "gateway.switch", targets: [], params: { gateway: gateway.id, name } }), "btn small primary"));
  }
  head.append(left, right);
  return head;
}

// What each managed gateway holds, read from the gateway itself when the card draws and
// again after every reload. An answer that fails never blocks the rest of the page.
const held = new Map(); // gateway id -> { servers, error, at, loading }

async function loadHeld(gateway) {
  const at = performance.now();
  held.set(gateway.id, { loading: true, at });
  let answer;
  try {
    answer = await getJson(`/api/gateways/${encodeURIComponent(gateway.id)}/servers`);
  } catch {
    answer = { servers: null, error: "Could not read what the gateway holds." };
  }
  held.set(gateway.id, { ...answer, at });
  if (state.view === "gateway") render();
}

function heldSection(gateway) {
  const box = el("section", "held");
  const title = (count) => el("h3", "group-title", count === undefined ? "In the gateway" : `In the gateway · ${count}`);
  if (!gateway.managed) {
    const need = gateway.kind === "obot" ? "the name of the variable that holds an Obot API key" : "its sign-in details";
    box.append(title(), el("p", "group-note", `To see what it holds from here, save the gateway again with ${need}.`));
    return box;
  }
  let entry = held.get(gateway.id);
  if (!entry || entry.at < freshness.reloadStartedAt) {
    loadHeld(gateway);
    entry = held.get(gateway.id);
  }
  if (entry.loading) {
    box.append(title(), skeleton("line", 2));
    return box;
  }
  if (!entry.servers) {
    box.append(title(), el("p", "group-note", entry.error || "Could not read what the gateway holds."));
    return box;
  }
  box.append(title(entry.servers.length));
  if (!entry.servers.length) {
    box.append(el("p", "group-note", gateway.movable ? "Nothing yet. Move a server from the lists below." : `Nothing yet. Add servers in ${gatewayName(gateway)} itself.`));
    return box;
  }
  const list = el("div", "list");
  for (const server of entry.servers) list.append(heldRow(server, gateway));
  box.append(list);
  return box;
}

// What a held server is, in one word. MetaMCP says SSE or STREAMABLE_HTTP; Obot says how it
// runs the server: a remote address, or a program Obot hosts (uvx, npx, containerized).
function heldKind(server) {
  if (server.type === "SSE") return "SSE";
  if (!server.type || server.type === "STREAMABLE_HTTP" || server.type === "remote") return "Remote";
  return "Hosted";
}

// One row per server the gateway holds: its name and what it is. The address stays behind
// Details, as on the other lists.
function heldRow(server, gateway) {
  const node = el("div", "list-row");
  const marks = el("span", "chip");
  marks.setAttribute("aria-label", gatewayName(gateway));
  marks.append(mark("gateway"));
  const what = el("span", "what");
  const name = el("span", "mono", server.name);
  name.title = server.name;
  what.append(name, flag({ text: heldKind(server), level: "info" }));
  const actions = el("span", "row-actions");
  actions.append(button("Details", () => showHeld(server, gateway), "btn small ghost"));
  node.append(marks, what, actions);
  return node;
}

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

function gatewayCard(gateway, model) {
  const card = el("section", "card");
  const connections = model.connections[gateway.id] || {};
  card.append(gatewayHead(gateway, model), routes(gateway, connections, model.groups.move), heldSection(gateway));
  // Only clients without an entry in any gateway are offered. One that uses another gateway
  // moves with "Use this gateway…"; connecting it here too would load its servers twice.
  const waiting = foundClients().filter((c) => !Object.values(model.connections).some((per) => (per[c] || []).length));
  if (waiting.length) {
    const box = el("details", "connect");
    box.open = draft.connectOpen === null ? true : draft.connectOpen;
    box.addEventListener("toggle", () => { draft.connectOpen = box.open; });
    box.append(el("summary", null, "Connect clients"), connectForm(gateway, waiting));
    card.append(fold(box));
  }
  return card;
}

// Wires already drawn on this page. A wire draws itself once, when its connection first
// appears; it never moves after that, because Kitden cannot see real traffic.
const drawn = new Set();

// Hovering a client or its wire lights that route, dims the rest and lights the rows below
// that hold a direct entry of that client. Hovering a server row lights only the clients
// that load it: its own entry does not go through the gateway.
export function focusRoutes(clients, { wires = true, rows = true } = {}) {
  for (const svg of document.querySelectorAll(".routes")) {
    svg.classList.toggle("focusing", clients.length > 0);
    svg.classList.toggle("nodes-only", !wires);
    for (const group of svg.querySelectorAll(".route")) group.classList.toggle("focus", clients.includes(group.dataset.client));
  }
  for (const row of document.querySelectorAll(".list-row[data-clients]")) {
    const own = row.dataset.clients.split(" ");
    row.classList.toggle("lit", rows && clients.some((c) => own.includes(c)));
  }
}

// From a client in the diagram to its first direct entry in the lists below.
function showDirect(client) {
  focusRoutes([client]);
  const row = document.querySelector(".list-row.lit");
  if (row) row.scrollIntoView({ block: "center", behavior: reducedMotion.matches ? "auto" : "smooth" });
}

// Three clients, one hub: a wire only for a client that has a gateway entry. A client
// without one stands apart.
// Each client opens its own Mac app through the link scheme the app registers: Claude,
// Cursor, and ChatGPT for Codex. The server reads the scheme from the installed app's
// Info.plist at scan time (`app_url`); without the app the node stays a plain node.
const CLIENT_APPS = { claude_code: "Claude", codex: "ChatGPT", cursor: "Cursor" };

function appUrl(client) {
  const found = (data.clients || []).find((c) => c.id === client);
  return found && found.app_url ? found.app_url : null;
}

// The gateway's own page: the saved link, or the address it serves.
function gatewayPage(gateway) {
  if (gateway.ui_url) return gateway.ui_url;
  try { return new URL(gateway.url).origin; } catch { return null; }
}

// A diagram node that acts like a link: click, Enter or Space.
function opens(node, label, open) {
  node.classList.add("clickable");
  node.setAttribute("role", "link");
  node.setAttribute("tabindex", "0");
  node.setAttribute("aria-label", label);
  const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
  title.textContent = label;
  node.prepend(title);
  node.addEventListener("click", open);
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
  });
}

function routes(gateway, connections, direct = []) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  const add = (tag, attrs, text, parent = svg) => {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text) node.textContent = text;
    parent.append(node);
    return node;
  };
  const name = gatewayName(gateway);
  const linked = WRITABLE.filter((c) => (connections[c] || []).length);
  const apart = WRITABLE.filter((c) => !linked.includes(c)).map((c) => CLIENT_NAMES[c]);
  svg.setAttribute("viewBox", "0 0 640 150");
  svg.setAttribute("class", "routes");
  svg.setAttribute("role", "group");
  const said = linked.length ? `${linked.map((c) => CLIENT_NAMES[c]).join(", ")} connect to ${name}` : `No client connects to ${name} yet`;
  svg.setAttribute("aria-label", apart.length && linked.length ? `${said}; ${apart.join(", ")} not yet.` : `${said}.`);
  const hub = { x: 470, y: 75 };
  let order = 0;
  WRITABLE.forEach((client, i) => {
    const y = 25 + i * 50;
    const d = `M 200 ${y} C 330 ${y}, 350 ${hub.y}, ${hub.x - 2} ${hub.y}`;
    const around = direct.filter((row) => row.clients.includes(client)).length;
    const group = add("g", { class: linked.includes(client) ? "route linked" : "route", "data-client": client });
    const state = linked.includes(client) ? `connected to ${name}` : `not connected to ${name}`;
    const url = appUrl(client);
    // With the app installed, the node opens it; the browser asks once before it does.
    if (url) opens(group, `Open ${CLIENT_APPS[client]} · ${CLIENT_NAMES[client]}: ${state}`, () => { window.location.href = url; });
    else group.setAttribute("aria-label", `${CLIENT_NAMES[client]}: ${state}`);
    group.addEventListener("pointerenter", () => focusRoutes([client]));
    group.addEventListener("pointerleave", () => focusRoutes([]));
    group.addEventListener("focus", () => focusRoutes([client]));
    group.addEventListener("blur", () => focusRoutes([]));
    if (linked.includes(client)) {
      const wire = add("path", { d, class: "wire", pathLength: "1" }, null, group);
      const key = `${gateway.id}:${client}`;
      if (!drawn.has(key)) {
        drawn.add(key);
        wire.classList.add("draw");
        wire.style.animationDelay = `${order++ * 90}ms`;
      }
    }
    add("rect", { x: 8, y: y - 15, width: 192, height: 30, rx: 7, class: "node" }, null, group);
    // The same tile as mark(): the Claude glyph sits inside it, the other icons fill it.
    const icon = CLIENT_ICONS[client];
    const pad = icon === "claude" ? 4 : 0;
    add("rect", { x: 16, y: y - 12, width: 24, height: 24, rx: 6, class: "node-tile" }, null, group);
    const box = { x: 16 + pad, y: y - 12 + pad, width: 24 - 2 * pad, height: 24 - 2 * pad, "aria-hidden": "true" };
    const tile = add("g", { class: DARK_ICONS.has(icon) ? "has-dark" : "" }, null, group);
    add("image", { ...box, href: `/static/brand/clients/${icon}.png`, class: "node-icon icon-light" }, null, tile);
    if (DARK_ICONS.has(icon)) add("image", { ...box, href: `/static/brand/clients/${icon}-dark.png`, class: "node-icon icon-dark" }, null, tile);
    add("text", { x: 50, y: y + 4, class: "sub" }, CLIENT_NAMES[client], group);
    // Servers this client reaches directly, around the gateway: the count leads to them below.
    if (around) {
      const count = add("text", { x: 190, y: y + 4, class: "bypass", "text-anchor": "end" }, `${around} direct`, group);
      count.addEventListener("click", (event) => { event.stopPropagation(); showDirect(client); });
    }
  });
  const node = add("g", { class: "hub-node" });
  add("rect", { x: hub.x, y: hub.y - 22, width: 160, height: 44, rx: 9, class: "hub" }, null, node);
  add("text", { x: hub.x + 14, y: hub.y - 2 }, name, node);
  add("text", { x: hub.x + 14, y: hub.y + 14, class: "sub" }, linked.length ? plural(linked.length, "client", "clients") : "No clients yet", node);
  const page = gatewayPage(gateway);
  if (page) opens(node, `Open ${name}`, () => window.open(page, "_blank", "noopener"));
  return svg;
}

const GROUP_WORDS = { move: "Remote", local: "Local", plugin: "Plugin" };

// One row per server: the clients that have it, its name and what it is. Addresses and
// commands stay behind Details (the same panel as on the Load map).
function groupRow(row, group, target) {
  const node = el("div", "list-row");
  node.dataset.clients = row.clients.join(" ");
  node.addEventListener("pointerenter", () => focusRoutes(row.clients, { wires: false, rows: false }));
  node.addEventListener("pointerleave", () => focusRoutes([]));
  const marks = el("span", "chip");
  marks.setAttribute("aria-label", row.clients.map((c) => CLIENT_NAMES[c] || c).join(", "));
  for (const client of row.clients) marks.append(mark(client));
  const what = el("span", "what");
  const name = el("span", "mono", row.name);
  name.title = row.name;
  what.append(name, flag({ text: GROUP_WORDS[group], level: "info" }));
  const actions = el("span", "row-actions");
  actions.append(button("Details", () => showServer(row.name), "btn small ghost"));
  if (group === "move" && row.items.length) {
    const targets = row.items.map((item) => ({ item }));
    // With a managed gateway the move does both steps; without one, only the removal is here.
    if (target) actions.append(button("Move into the gateway…", () => review({ action: "gateway.move", targets, params: { gateway: target.id } })));
    else actions.append(button("Remove direct entry…", () => review({ action: "mcp.remove_direct", targets, params: {} })));
  }
  node.append(marks, what, actions);
  return node;
}

async function showServer(name) {
  if (!data.map) await loadMap();
  const row = ((data.map && data.map.rows) || []).find((r) => r.kind === "mcp_server" && r.name === name);
  if (row) await openItem(row);
  else toast("Could not find this server on the Load map.");
}

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

// Connect clients to the gateway of this card, and only to it.
function connectForm(gateway, waiting) {
  if (!draft.connect || draft.connect.gateway !== gateway.id) {
    draft.connect = { gateway: gateway.id, clients: new Set(waiting) };
  }
  const state = draft.connect;
  const form = el("form", "form");
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of waiting) {
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.value = client;
    box.checked = state.clients.has(client);
    box.addEventListener("change", () => { if (box.checked) state.clients.add(client); else state.clients.delete(client); });
    label.append(box, el("span", null, CLIENT_NAMES[client]));
    checks.append(label);
  }
  form.append(checks);
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const targets = [...state.clients].filter((c) => waiting.includes(c)).map((client) => ({ client }));
    if (!targets.length) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    message.textContent = "";
    review({ action: "gateway.connect", targets, params: { gateway: state.gateway, name: ENTRY_NAME } });
  });
  return form;
}

function addForm() {
  const state = draft.add;
  const form = el("form", "form");
  const url = input({ type: "url", required: true, placeholder: "http://127.0.0.1:12008/metamcp/local/mcp or http://127.0.0.1:8080/mcp-connect/<id>", autocomplete: "off" }, state.url, (v) => { state.url = v; showFields(); });
  const ui = input({ type: "url", placeholder: "http://127.0.0.1:12008", autocomplete: "off" }, state.ui_url, (v) => { state.ui_url = v; });
  const login = el("select");
  for (const [value, text] of [["none", "None"], ["env_key", "Key in an environment variable"], ["oauth", "OAuth login"]]) login.append(new Option(text, value));
  login.value = state.auth;
  const key = input({ pattern: "[A-Z_][A-Z0-9_]*", placeholder: "GATEWAY_KEY", autocomplete: "off", spellcheck: false }, state.key_env_var, (v) => { state.key_env_var = v; });
  const keyLabel = el("span", null, "Variable name (not the key)");
  const keyField = el("label", "field");
  keyField.append(keyLabel, key);
  // The fields follow the address: an Obot gateway needs the variable that holds an API key
  // (Kitden reads what it holds with it, even when the clients sign in with OAuth); a MetaMCP
  // gateway needs a sign-in. The key or password itself is never typed into Kitden.
  const showFields = () => {
    const kind = kindOf(state.url);
    const needsKey = login.value === "env_key" || kind === "obot";
    keyField.hidden = !needsKey;
    key.required = needsKey;
    keyLabel.textContent = kind === "obot" && login.value !== "env_key" ? "Obot API key variable name (not the key)" : "Variable name (not the key)";
    emailField.hidden = passwordField.hidden = kind === "obot";
  };
  login.addEventListener("change", () => { state.auth = login.value; showFields(); });
  const urlField = field("MCP address", url);
  urlField.classList.add("grow");
  const uiField = field("Interface link (optional)", ui);
  uiField.classList.add("grow");
  // Sign-in for managing the gateway from here (feature 006). The password itself is never
  // typed into Kitden: only the name of the variable that holds it.
  const email = input({ type: "email", placeholder: "you@example.com", autocomplete: "off" }, state.login_email, (v) => { state.login_email = v; });
  const password = input({ pattern: "[A-Z_][A-Z0-9_]*", placeholder: "METAMCP_PASSWORD", autocomplete: "off", spellcheck: false }, state.login_password_env_var, (v) => { state.login_password_env_var = v; });
  const emailField = field("Sign-in email (to manage it from here)", email);
  emailField.classList.add("grow");
  const passwordField = field("Password variable name (not the password)", password);
  showFields();
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Save gateway");
  submit.type = "submit";
  form.append(urlField, uiField, field("Login", login), keyField, emailField, passwordField, submit, message);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const result = await postJson("/api/gateways", {
        url: state.url.trim(),
        ui_url: state.ui_url.trim() || null,
        auth: state.auth,
        key_env_var: state.auth === "env_key" || kindOf(state.url) === "obot" ? state.key_env_var.trim() : null,
        login_email: state.login_email.trim() || null,
        login_password_env_var: state.login_password_env_var.trim() || null,
      });
      if (!result.ok) {
        message.className = "form-message error";
        message.textContent = (result.data && result.data.detail) || `Not saved (${result.status}).`;
        return;
      }
      draft.add = { ...EMPTY_ADD };
      draft.addOpen = false;
      await reload();
      render();
      toast("Gateway saved. Now connect your clients to it.");
    } finally {
      submit.disabled = false;
    }
  });
  return form;
}
