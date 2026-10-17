// Gateway: which clients reach it, and what still goes around it.
import { postJson } from "./api.js";
import { button, el, plural, shortPath, webLink } from "./dom.js";
import { entrance } from "./motion.js";
import { review, toast } from "./panel.js";
import { banner, CLIENT_NAMES, mark, skeleton } from "./parts.js";
import { data, loadGateway, reload, render } from "./store.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
const GROUPS = [
  ["move", "Can move into the gateway", "Direct entries for remote servers. Add them in the gateway, then remove them here."],
  ["local", "Must run on this Mac", "Local servers start a program here; a gateway cannot reach them. Nothing to do."],
  ["plugin", "Come with a plugin", "Turn the plugin off if you do not want them."],
];

// What the person typed survives a redraw (a rescan can redraw the page at any time).
const draft = { add: { url: "", ui_url: "", auth: "none", key_env_var: "" }, connect: null, addOpen: false };

export function gatewayName(gateway) {
  if (/metamcp/i.test(gateway.url)) return "MetaMCP";
  if (/obot/i.test(gateway.url)) return "Obot";
  try { return new URL(gateway.url).host || "Gateway"; } catch { return "Gateway"; }
}

function loginWords(gateway) {
  if (gateway.auth === "env_key") return `key in $${gateway.key_env_var}`;
  if (gateway.auth === "oauth") return "OAuth login";
  return "no login";
}

function foundClients() {
  return (data.clients || []).filter((c) => WRITABLE.includes(c.id) && c.status === "found").map((c) => c.id);
}

export function renderGateway(main) {
  main.append(el("h1", null, "Gateway"));
  main.append(el("p", "lede", "Turn MCP tools on and off in the gateway, not in each client. Here you see which clients reach it and what still goes around it."));
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
  const card = gatewayCard(first, model.connections);
  main.append(card);
  blocks.push(card);
  for (const gateway of others) {
    const more = el("section", "card");
    more.append(gatewayHead(gateway));
    main.append(more);
    blocks.push(more);
  }

  for (const [key, title, note] of GROUPS) {
    const rows = model.groups[key];
    if (!rows.length) continue;
    const section = el("section");
    section.append(el("h2", "group-title", `${title} · ${rows.length}`), el("p", "group-note", note));
    const list = el("div", "list");
    for (const entry of rows) list.append(groupRow(entry, key));
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

function gatewayHead(gateway) {
  const head = el("div", "gw-head");
  const left = el("div");
  left.append(el("div", "kicker", `${gatewayName(gateway)} · ${loginWords(gateway)}`), el("div", "gw-url", gateway.url));
  const right = el("div");
  if (gateway.ui_url) right.append(webLink(gateway.ui_url, `Open ${gatewayName(gateway)} ↗`));
  head.append(left, right);
  return head;
}

function gatewayCard(gateway, connections) {
  const card = el("section", "card");
  card.append(gatewayHead(gateway), routes(gateway, connections));
  const found = foundClients();
  const waiting = found.filter((c) => !(connections[c] || []).length);
  const box = el("details", "connect");
  box.open = waiting.length > 0;
  box.append(el("summary", null, waiting.length ? "Connect clients" : "Connect again with another entry name"));
  box.append(connectForm(gateway, found, waiting));
  card.append(box);
  return card;
}

// Three clients, one hub: dashes flow along the wire of each client that has a gateway entry.
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
    add("path", { d, class: linked.includes(client) ? "wire" : "wire idle" });
    if (linked.includes(client)) add("path", { d, class: `flow ${speeds[i]}` });
    add("rect", { x: 8, y: y - 15, width: 142, height: 30, rx: 7, class: "node" });
    add("text", { x: 22, y: y + 4 }, { claude_code: "CC", codex: "CX", cursor: "CU" }[client]);
    add("text", { x: 50, y: y + 4, class: "sub" }, CLIENT_NAMES[client]);
  });
  add("rect", { x: hub.x, y: hub.y - 22, width: 160, height: 44, rx: 9, class: "hub" });
  add("text", { x: hub.x + 14, y: hub.y - 2 }, name);
  add("text", { x: hub.x + 14, y: hub.y + 14, class: "sub" }, linked.length ? plural(linked.length, "client", "clients") : "No clients yet");
  return svg;
}

function groupRow(entry, group) {
  const row = el("div", "list-row");
  const name = el("span", "mono", entry.name);
  name.title = entry.name;
  const path = el("span", "path mono", shortPath(entry.path));
  path.title = entry.path || "";
  const action = el("span");
  if (group === "move" && entry.actions.includes("mcp.remove_direct")) {
    action.append(button("Remove…", () => review({ action: "mcp.remove_direct", targets: [{ item: entry.item }], params: {} })));
  }
  row.append(mark(entry.client), name, path, action);
  return row;
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

function connectForm(gateway, found, waiting) {
  if (!draft.connect || draft.connect.gateway !== gateway.id) {
    draft.connect = { gateway: gateway.id, name: "gateway", clients: new Set(waiting.length ? waiting : found) };
  }
  const state = draft.connect;
  const form = el("form", "form");
  const name = input({ required: true, pattern: "[A-Za-z0-9][A-Za-z0-9_\\-]*", autocomplete: "off" }, state.name, (v) => { state.name = v; });
  form.append(field("Entry name", name));
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of found) {
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.value = client;
    box.checked = state.clients.has(client);
    box.addEventListener("change", () => { if (box.checked) state.clients.add(client); else state.clients.delete(client); });
    label.append(box, el("span", null, CLIENT_NAMES[client]));
    checks.append(label);
  }
  if (!found.length) checks.append(el("span", "muted", "No client found to connect."));
  form.append(checks);
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const targets = [...state.clients].filter((c) => found.includes(c)).map((client) => ({ client }));
    if (!targets.length) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    message.textContent = "";
    review({ action: "gateway.connect", targets, params: { gateway: gateway.id, name: state.name.trim() } });
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
