// Gateway: which clients reach it, and which servers are not connected to it.
import { postJson } from "./api.js";
import { button, el, plural, webLink } from "./dom.js";
import { entrance } from "./motion.js";
import { openItem, review, toast } from "./panel.js";
import { banner, CLIENT_ICONS, CLIENT_NAMES, DARK_ICONS, flag, mark, skeleton } from "./parts.js";
import { data, loadGateway, loadMap, reload, render } from "./store.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
const GROUPS = [
  ["move", "Can move into the gateway", "Add the server in the gateway first, then remove its direct entry here."],
  ["local", "Must run on this Mac", "Local servers start a program here; a gateway cannot reach them. Nothing to do."],
  ["plugin", "Come with a plugin", "Turn the plugin off if you do not want them."],
];

// What the person typed survives a redraw (a rescan can redraw the page at any time).
const draft = { add: { url: "", ui_url: "", auth: "none", key_env_var: "" }, connect: null, addOpen: false, connectOpen: null };
// Every client gets the same entry name; the review shows the exact entry before Apply.
const ENTRY_NAME = "gateway";

export function gatewayName(gateway) {
  if (/metamcp/i.test(gateway.url)) return "MetaMCP";
  if (/obot/i.test(gateway.url)) return "Obot";
  try { return new URL(gateway.url).host || "Gateway"; } catch { return "Gateway"; }
}

function foundClients() {
  return (data.clients || []).filter((c) => WRITABLE.includes(c.id) && c.status === "found").map((c) => c.id);
}

export function renderGateway(main) {
  main.append(el("h1", null, "Gateway"));
  main.append(el("p", "lede", "Turn MCP tools on and off in the gateway, not in each client. Here you see which clients reach it and which servers are not connected to it."));
  const model = data.gateway;
  if (!model) {
    if (data.errors.gateway) main.append(banner("the gateway", async () => { await loadGateway(); render(); }));
    else main.append(skeleton("card", 2));
    return;
  }

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

  const [first, ...others] = model.gateways;
  const card = gatewayCard(first, model);
  main.append(card);
  blocks.push(card);
  for (const gateway of others) {
    const more = el("section", "card");
    more.append(gatewayHead(gateway, model));
    main.append(more);
    blocks.push(more);
  }

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
    section.append(el("h3", "group-title", `${title} · ${count}`), el("p", "group-note", note));
    const list = el("div", "list");
    for (const row of rows) list.append(groupRow(row, key));
    section.append(list);
    main.append(section);
    blocks.push(section);
  }

  const more = el("details", "add-more");
  more.open = draft.addOpen;
  more.addEventListener("toggle", () => { draft.addOpen = more.open; });
  more.append(el("summary", null, "Add another gateway"), addForm());
  main.append(more);
  entrance("gateway", blocks);
}

function gatewayHead(gateway, model) {
  const head = el("div", "gw-head");
  const left = el("div");
  // With two gateways, say which one the clients use.
  const used = model.gateways.length > 1 ? ` · ${model.used.includes(gateway.id) ? "Used" : "Not used"}` : "";
  left.append(el("div", "kicker", `${gatewayName(gateway)}${used}`), el("div", "gw-url", gateway.url));
  const right = el("div");
  if (gateway.ui_url) right.append(webLink(gateway.ui_url, `Open ${gatewayName(gateway)} ↗`));
  head.append(left, right);
  return head;
}

function gatewayCard(gateway, model) {
  const card = el("section", "card");
  card.append(gatewayHead(gateway, model), routes(gateway, model.connections));
  // Only clients without a gateway entry are offered; the others are connected already.
  const waiting = foundClients().filter((c) => !(model.connections[c] || []).length);
  if (waiting.length) {
    const box = el("details", "connect");
    box.open = draft.connectOpen === null ? true : draft.connectOpen;
    box.addEventListener("toggle", () => { draft.connectOpen = box.open; });
    box.append(el("summary", null, "Connect clients"), connectForm(model.gateways, waiting));
    card.append(box);
  }
  return card;
}

// Three clients, one hub: a wire, with flowing dashes, only for a client that has a gateway
// entry. A client without one stands apart.
function routes(gateway, connections) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  const add = (tag, attrs, text) => {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text) node.textContent = text;
    svg.append(node);
    return node;
  };
  const name = gatewayName(gateway);
  const linked = WRITABLE.filter((c) => (connections[c] || []).length);
  const apart = WRITABLE.filter((c) => !linked.includes(c)).map((c) => CLIENT_NAMES[c]);
  svg.setAttribute("viewBox", "0 0 640 150");
  svg.setAttribute("class", "routes");
  svg.setAttribute("role", "img");
  const said = linked.length ? `${linked.map((c) => CLIENT_NAMES[c]).join(", ")} connect to ${name}` : `No client connects to ${name} yet`;
  svg.setAttribute("aria-label", apart.length && linked.length ? `${said}; ${apart.join(", ")} not yet.` : `${said}.`);
  const hub = { x: 470, y: 75 };
  const speeds = ["", "mid", "slow"];
  WRITABLE.forEach((client, i) => {
    const y = 25 + i * 50;
    const d = `M 150 ${y} C 300 ${y}, 330 ${hub.y}, ${hub.x - 2} ${hub.y}`;
    if (linked.includes(client)) {
      add("path", { d, class: "wire" });
      add("path", { d, class: `flow ${speeds[i]}` });
    }
    add("rect", { x: 8, y: y - 15, width: 142, height: 30, rx: 7, class: "node" });
    // The same tile as mark(): the Claude glyph sits inside it, the other icons fill it.
    const icon = CLIENT_ICONS[client];
    const pad = icon === "claude" ? 4 : 0;
    add("rect", { x: 16, y: y - 12, width: 24, height: 24, rx: 6, class: "node-tile" });
    const box = { x: 16 + pad, y: y - 12 + pad, width: 24 - 2 * pad, height: 24 - 2 * pad, "aria-hidden": "true" };
    const tile = add("g", { class: DARK_ICONS.has(icon) ? "has-dark" : "" });
    tile.append(add("image", { ...box, href: `/static/brand/clients/${icon}.png`, class: "node-icon icon-light" }));
    if (DARK_ICONS.has(icon)) tile.append(add("image", { ...box, href: `/static/brand/clients/${icon}-dark.png`, class: "node-icon icon-dark" }));
    add("text", { x: 50, y: y + 4, class: "sub" }, CLIENT_NAMES[client]);
  });
  add("rect", { x: hub.x, y: hub.y - 22, width: 160, height: 44, rx: 9, class: "hub" });
  add("text", { x: hub.x + 14, y: hub.y - 2 }, name);
  add("text", { x: hub.x + 14, y: hub.y + 14, class: "sub" }, linked.length ? plural(linked.length, "client", "clients") : "No clients yet");
  return svg;
}

const GROUP_WORDS = { move: "Remote", local: "Local", plugin: "Plugin" };

// One row per server: the clients that have it, its name and what it is. Addresses and
// commands stay behind Details (the same panel as on the Load map).
function groupRow(row, group) {
  const node = el("div", "list-row");
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
    actions.append(button("Remove direct entry…", () => review({ action: "mcp.remove_direct", targets, params: {} })));
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

// Connect any registered gateway; the first one is chosen until the person picks another.
function connectForm(gateways, waiting) {
  if (!draft.connect || !gateways.some((g) => g.id === draft.connect.gateway)) {
    draft.connect = { gateway: gateways[0].id, clients: new Set(waiting) };
  }
  const state = draft.connect;
  const form = el("form", "form");
  if (gateways.length > 1) {
    const pick = el("select");
    for (const g of gateways) pick.append(new Option(`${gatewayName(g)} · ${g.url}`, g.id));
    pick.value = state.gateway;
    pick.addEventListener("change", () => { state.gateway = pick.value; });
    form.append(field("Gateway", pick));
  }
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
  const url = input({ type: "url", required: true, placeholder: "http://127.0.0.1:12008/metamcp/local/mcp", autocomplete: "off" }, state.url, (v) => { state.url = v; });
  const ui = input({ type: "url", placeholder: "http://127.0.0.1:12008", autocomplete: "off" }, state.ui_url, (v) => { state.ui_url = v; });
  const login = el("select");
  for (const [value, text] of [["none", "None"], ["env_key", "Key in an environment variable"], ["oauth", "OAuth login"]]) login.append(new Option(text, value));
  login.value = state.auth;
  const key = input({ pattern: "[A-Z_][A-Z0-9_]*", placeholder: "GATEWAY_KEY", autocomplete: "off", spellcheck: false }, state.key_env_var, (v) => { state.key_env_var = v; });
  const keyField = field("Variable name (not the key)", key);
  const showKey = () => { keyField.hidden = login.value !== "env_key"; key.required = login.value === "env_key"; };
  login.addEventListener("change", () => { state.auth = login.value; showKey(); });
  showKey();
  const urlField = field("MCP address", url);
  urlField.classList.add("grow");
  const uiField = field("Interface link (optional)", ui);
  uiField.classList.add("grow");
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Save gateway");
  submit.type = "submit";
  form.append(urlField, uiField, field("Login", login), keyField, submit, message);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const result = await postJson("/api/gateways", {
        url: state.url.trim(),
        ui_url: state.ui_url.trim() || null,
        auth: state.auth,
        key_env_var: state.auth === "env_key" ? state.key_env_var.trim() : null,
      });
      if (!result.ok) {
        message.className = "form-message error";
        message.textContent = (result.data && result.data.detail) || `Not saved (${result.status}).`;
        return;
      }
      draft.add = { url: "", ui_url: "", auth: "none", key_env_var: "" };
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
