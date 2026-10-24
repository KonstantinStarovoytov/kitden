// Details on the Gateway page for a client, a gateway and a server outside the gateway: a card
// builder each (a plain object that detailsCard draws, so a test reads it without a page), and a
// show… that opens it beside the page. The forms to add a gateway and to connect clients live
// here too, with what each registered gateway holds.
import { getJson, postJson, query } from "./api.js";
import { $, busyWhile, el, joinWords, plural, reportError } from "./dom.js";
import { fold } from "./motion.js";
import { projectNote } from "./offer.js";
import { closePanel, detailsCard, keepFrom, moveInto, moveTargets, offerLabel, openPanel, panelState, review, techRows, technical, toast } from "./panel.js";
import { callout, CLIENT_NAMES, clientCheck, GATEWAY_NOTE, gatewayName, kindOf, kitdenClients, mark, STATE_WORDS, versionWords } from "./parts.js";
import { arrival, current, data, freshness, reload, render, setState, state } from "./store.js";

const WRITABLE = ["claude_code", "codex", "cursor"];
// The kitden entry is the same one that lets agents read this setup.
export const SETUP_NOTE = "The kitden entry shows your setup to agents and offers the tools in the Kitden gateway.";
// What a server outside the gateway is, by the Gateway's group for it.
const GROUP_KINDS = { move: "Remote", local: "Local", plugin: "From a plugin" };
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
function tiles(clients, text) {
  const node = el("span", "fact-tiles");
  node.append(...clients.map((client) => mark(client)), el("span", null, text));
  return node;
}

function clientsFact(clients) {
  const text = clients.length ? plural(clients.length, "client", "clients") : "No clients yet";
  return { label: "Clients", value: tiles(clients, text), text };
}

// Clients ------------------------------------------------------------------------------------

// A client's version, or why there is none.
function versionText(found, progress) {
  if (!found || found.status === "not_found") return STATE_WORDS.missing;
  if (found.status === "unreadable") return STATE_WORDS.unread;
  return versionWords(found.version, progress, true);
}

// The client's kitden entry in one word.
function entryWord(entry, known) {
  if (!known) return STATE_WORDS.unk;
  if (!entry) return "Not set up";
  if (entry.state === "added" || entry.state === "plugin") return entry.enabled === false ? "Off" : "On";
  return entry.state === "old" ? "Old" : "Not set up";
}

// Details of a client: its version, its kitden entry and whether that entry reaches the gateway.
// "Set up in <client>…" comes from kitdenClients, as on Overview; the client's app opens from
// here when Kitden found its link scheme.
export function clientCard(client, { setup, clients, progress = data.progress } = {}) {
  const name = CLIENT_NAMES[client];
  const found = (clients || []).find((c) => c.id === client);
  const { linked, off, setup: offers, known } = kitdenClients(setup);
  const on = linked.includes(client);
  const entry = (setup || []).find((e) => e.client === client);
  const facts = [
    { label: "Version", value: versionText(found, progress) },
    { label: "Kitden entry", value: entryWord(entry, known) },
    { label: "Gateway", value: on ? "Connected" : "Not connected" },
  ];
  let why = `${name} does not use the Kitden gateway yet.`;
  if (!known) why = "Kitden could not read which clients use it.";
  else if (on) why = `${name} reaches the Kitden gateway through its kitden entry.`;
  else if (off.includes(client)) why = `${name} has the kitden entry turned off, so it does not reach the gateway.`;
  const actions = offers.filter((s) => s.client === client)
    .map((s) => ({ label: s.label, body: s.body, run: () => review(s.body, { note: SETUP_NOTE }), primary: true }));
  if (found && found.app_url) {
    const url = found.app_url;
    // The browser asks once before it opens the app.
    actions.push({ label: `Open ${CLIENT_APPS[client]}`, run: () => { window.location.href = url; } });
  }
  return { kind: "Client", title: name, id: null, facts, why, actions };
}

// Gateways -----------------------------------------------------------------------------------

// What each registered gateway holds, read from the gateway itself when the page draws and again
// after every reload. An answer that fails never blocks the rest of the page.
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

// The Kitden gateway: its clients, servers and the projects with rules of their own. "Move all N…"
// takes every outside server a move can take into it, in one review; "Add another gateway…" shows
// the form in the column (`adding`).
function kitdenCard(gateway, { view, setup, projects, adding }) {
  const { linked, known } = kitdenClients(setup);
  const servers = gateway.servers || [];
  const facts = known ? [clientsFact(linked)] : [];
  // Settings it cannot read are a problem, not an empty gateway: the callout says so.
  if (!gateway.problem) {
    facts.push({ label: "Servers", value: servers.length ? plural(servers.length, "server", "servers") : "Nothing yet. Move a server in from the outside group." });
  }
  const ruled = (projects || []).filter((p) => p.own_rules > 0).length;
  facts.push({ label: "Rules", value: ruled ? `${plural(ruled, "project has", "projects have")} its own rules` : "No project has its own rules" });
  const rows = ["move", "local"].flatMap((key) => (view.groups[key] || []).filter((row) => movesTo(view, key, row).some((g) => g.id === gateway.id)));
  const actions = [];
  if (rows.length) {
    const targets = rows.flatMap((row) => row.items).map((item) => ({ item }));
    actions.push({ label: `Move all ${rows.length}…`, body: { action: "gateway.move", targets, params: { gateway: gateway.id } }, primary: true });
  }
  actions.push({ label: "Add another gateway…", run: () => showGateway(gateway.id, { adding: true }) });
  let warning = known ? null : "Kitden could not read which clients use it.";
  if (gateway.problem) warning = gateway.problem;
  let after = null;
  if (adding) {
    after = el("section", "add-gateway");
    after.append(el("h2", null, "Add another gateway"), addForm());
  }
  const why = "The gateway controls only the servers in it. Direct entries and terminal tools are outside it.";
  return { kind: "Gateway", title: gateway.name, id: gateway.where, facts, why, actions, after, warning };
}

// What a registered gateway holds, as its Servers fact.
function heldWords(entry) {
  if (!entry || entry.loading) return "Reading what it holds…";
  if (!entry.servers) return entry.error || "Could not read what the gateway holds.";
  return plural(entry.servers.length, "server", "servers");
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
  return { kind: "Gateway", title: name, id: null, facts, why: heldWhy(gateway, entry), actions, after, technical: technical(rows) };
}

// Details of a gateway: the Kitden one, or a registered one.
export function gatewayCard(gateway, { view, setup, projects = [], held: entry = null, clients = foundClients(), adding = false } = {}) {
  if (gateway.kind === "kitden") return kitdenCard(gateway, { view, setup, projects, adding });
  return registeredCard(gateway, { view, held: entry, clients });
}

// Servers outside the gateway ----------------------------------------------------------------

// Details of a server outside the gateway, for its row of one group (one name in two groups is
// two rows). Its facts say who has it and that calls skip Kitden's rules. Actions: "Move into the
// gateway…" when a move can take it, else why not; "Remove direct entry…" when no gateway takes a
// remote one; "+ Add to <client>…" for each client Kitden writes that lacks it, while no client
// gets it through a gateway (as the Library's cells); and a Remove for each of its own entries.
// `definitions` come from /api/explain; [] until they are read.
export function outsideCard(row, group, definitions, { view, clients = foundClients() } = {}) {
  const columns = row.columns || row.clients;
  const names = joinWords(columns.map((c) => CLIENT_NAMES[c] || c));
  const own = definitions.filter((d) => row.items.includes(d.id));
  const targets = moveTargets(view, group);
  const actions = [];
  const moves = movesTo(view, group, row);
  if (moves.length) actions.push({ label: "Move into the gateway…", run: () => moveInto(moves, row.items, row.name), primary: true });
  else if (group === "move" && row.items.length && !targets.length) {
    actions.push({ label: "Remove direct entry…", body: { action: "mcp.remove_direct", targets: row.items.map((item) => ({ item })), params: {} } });
  }
  const source = own.find((d) => d.scope === "user" && d.actions.includes("mcp.remove_direct"));
  if (source && !definitions.some((d) => d.via_gateway)) {
    for (const client of WRITABLE.filter((c) => clients.includes(c) && !definitions.some((d) => d.client === c))) {
      const body = { action: "mcp.add", targets: [{ client }], params: { item: source.id } };
      // In a project an add still goes to the client's settings for all projects; the review says so.
      actions.push({ label: `+ Add to ${CLIENT_NAMES[client]}…`, body, run: () => review(body, { note: projectNote(state.project) }) });
    }
  }
  const offers = own.filter((d) => d.actions.includes("mcp.remove_direct")).map((def) => ({ def, action: "mcp.remove_direct" }));
  for (const offer of offers) {
    actions.push({ label: offerLabel(offer, offers), body: { action: offer.action, targets: [{ item: offer.def.id }], params: {} } });
  }
  const note = row.stays || (group === "move" && row.items.length && !targets.length ? GATEWAY_NOTE : null);
  const verb = columns.length > 1 ? "call" : "calls";
  const evidence = techRows(own.length ? own : definitions.filter((d) => !d.via_gateway && columns.includes(d.client)));
  return {
    kind: "MCP server",
    title: row.name,
    id: null,
    facts: [
      { label: "In", value: tiles(columns, names), text: names },
      { label: "Kind", value: GROUP_KINDS[group] },
      { label: "Gateway", value: "Outside · calls skip Kitden's rules" },
    ],
    why: `${names} ${verb} it directly, so Kitden's tool rules do not reach it.`,
    actions,
    after: note ? el("p", "muted", note) : null,
    technical: evidence.length ? technical(evidence) : null,
  };
}

// Showing a card -----------------------------------------------------------------------------

// Open a card beside the page, its warning first. A review opened from it comes back to it:
// `draw` draws it again from what it read, `read` reads first (the settings changed since the
// preview). False when a review being written kept its place.
function openCard(card, shown, draw, read = draw) {
  panelState.current = shown;
  const nodes = detailsCard(card);
  if (card.warning) nodes[1].prepend(callout(card.warning));
  if (!openPanel(nodes)) return false;
  keepFrom(draw, nodes, read);
  return true;
}

export function showClient(id) {
  const card = clientCard(id, { setup: data.setupServer, clients: data.clients });
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
  const card = gatewayCard(gateway, { view, setup: data.setupServer, projects: data.projects, held: held.get(id), adding });
  if (!openCard(card, { type: "gateway", gateway: id }, () => showGateway(id))) return;
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
  if (!drawOutside(row, group, [], shown)) return;
  let answer;
  try {
    answer = await getJson(`/api/explain${query({ name: row.name, kind: "mcp_server", project: state.project })}`);
  } catch {
    if (panelState.current === shown) $("#drawer .body").prepend(callout("Could not load the details.", "error"));
    return;
  }
  // The person may have opened something else meanwhile.
  if (panelState.current === shown) drawOutside(row, group, answer.definitions || [], shown);
}

function drawOutside(row, group, definitions, shown) {
  const card = outsideCard(row, group, definitions, { view: current("gateway") });
  return openCard(card, shown, () => drawOutside(row, group, definitions, shown), () => showOutside(group, row.name));
}

// Forms --------------------------------------------------------------------------------------

// What the person typed survives a redraw (a rescan can redraw the page at any time).
const EMPTY_ADD = { url: "", ui_url: "", auth: "none", key_env_var: "", login_email: "", login_password_env_var: "" };
const draft = { add: { ...EMPTY_ADD }, connect: null, connectOpen: null };
// Every client gets the same entry name; the review shows the exact entry before Apply.
const ENTRY_NAME = "gateway";

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
  const chosen = draft.connect;
  const form = el("form", "form");
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of waiting) {
    checks.append(clientCheck(client, chosen.clients.has(client), null, (checked) => {
      if (checked) chosen.clients.add(client); else chosen.clients.delete(client);
    }));
  }
  form.append(checks);
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const targets = [...chosen.clients].filter((c) => waiting.includes(c)).map((client) => ({ client }));
    if (!targets.length) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    message.textContent = "";
    busyWhile(submit, review({ action: "gateway.connect", targets, params: { gateway: chosen.gateway, name: ENTRY_NAME } })).catch(reportError);
  });
  return form;
}

// Add a registered gateway. Saved, its Details open, where clients connect to it.
export function addForm() {
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
  form.append(urlField, uiField, field("Login", login), keyField, emailField, passwordField, submit, message);
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
