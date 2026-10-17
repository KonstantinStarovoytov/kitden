// Agent setup page. All text from client files is untrusted (FR-041):
// it is only ever set with textContent, never as HTML.
"use strict";

const state = {
  clients: [], items: [], problems: [], projects: [], gateways: [], changeLog: [], change: null,
};
const WRITABLE_CLIENTS = ["claude_code", "codex", "cursor"];
const $ = (id) => document.getElementById(id);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function button(text, onClick) {
  const node = el("button", text);
  node.type = "button";
  node.addEventListener("click", () => onClick().catch(showError));
  return node;
}

function shortPath(path) {
  if (!path) return "";
  return path.replace(/^\/Users\/[^/]+/, "~");
}

async function getJson(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Tool-Request": "1", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  return { ok: response.ok, status: response.status, data };
}

async function load() {
  $("status").textContent = "Loading…";
  const [clients, items, problems, projects, gateways, changeLog] = await Promise.all([
    getJson("/api/clients"), getJson("/api/items"), getJson("/api/problems"),
    getJson("/api/projects"), getJson("/api/gateways"), getJson("/api/changes"),
  ]);
  Object.assign(state, { clients, items, problems, projects, gateways, changeLog });
  renderClients();
  renderProblems();
  fillFilters();
  renderItems();
  fillProjects();
  renderGateways();
  fillClientChecks($("setup-clients"));
  renderChangeLog();
  await renderProject();
  $("status").textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function renderClients() {
  const list = $("clients");
  list.replaceChildren();
  for (const client of state.clients) {
    const count = state.items.filter((i) => i.client === client.id).length;
    const li = el("li", null, `client ${client.status}`);
    li.append(el("strong", client.display_name));
    li.append(el("span", client.version ? `version ${client.version}` : "version unknown"));
    if (client.version && !client.version_supported) li.append(el("span", "not tested", "warn"));
    li.append(el("span", client.status === "found" ? `${count} items` : client.status.replace("_", " ")));
    list.append(li);
  }
}

function renderProblems() {
  const list = $("problems");
  list.replaceChildren();
  for (const problem of state.problems) {
    const where = shortPath(problem.path) || problem.owner_client;
    list.append(el("li", `${where}: ${String(problem.unknown_reason).replaceAll("_", " ")}`));
  }
  $("problems-section").hidden = state.problems.length === 0;
}

function fillFilters() {
  const fill = (select, values) => {
    const current = select.value;
    select.replaceChildren(el("option", "All"));
    select.firstChild.value = "";
    for (const value of values) {
      const option = el("option", value);
      option.value = value;
      select.append(option);
    }
    select.value = values.includes(current) ? current : "";
  };
  fill($("filter-client"), [...new Set(state.items.map((i) => i.client))].sort());
  fill($("filter-kind"), [...new Set(state.items.map((i) => i.kind))].sort());
}

function sourceCell(item) {
  const td = el("td");
  const source = item.source;
  const path = shortPath(source.path);
  td.append(el("span", path || source.kind.replaceAll("_", " "), "path"));
  if (source.owner_client && source.owner_client !== item.client) {
    td.append(el("span", `from ${source.owner_client}`, "tag"));
  }
  if (source.link_path) td.append(el("span", `link: ${shortPath(source.link_path)}`, "tag"));
  if (source.unknown_reason) td.append(el("span", source.unknown_reason.replaceAll("_", " "), "tag warn"));
  if (item.secret_present) td.append(el("span", "secret hidden", "tag"));
  if (item.via_gateway) td.append(el("span", "via gateway", "tag on"));
  return td;
}

const ACTION_LABELS = {
  "mcp.remove_direct": "Remove…",
  "plugin.disable": "Turn off…",
  "plugin.enable": "Turn on…",
};

function actionCell(item) {
  const td = el("td");
  for (const action of item.actions) {
    if (!ACTION_LABELS[action]) continue;
    td.append(button(ACTION_LABELS[action], () => preview({
      action, targets: [{ item: item.id }], params: {},
    })));
  }
  if (item.kind === "plugin" || item.kind === "marketplace") {
    td.append(button("Commands…", () => showCommands(item)));
  }
  if (item.change_hint && item.actions.length === 0) td.append(el("p", item.change_hint, "hint"));
  return td;
}

async function showCommands(item) {
  const data = await getJson(`/api/commands?item=${encodeURIComponent(item.id)}`);
  const list = $("commands");
  list.replaceChildren();
  $("commands-title").textContent = `Commands for ${item.name}`;
  for (const command of data.commands) {
    const li = el("li");
    li.append(el("strong", command.label));
    if (command.command) li.append(el("pre", command.command, "diff"));
    if (command.note) li.append(el("p", command.note, "hint"));
    list.append(li);
  }
  if (data.commands.length === 0) list.append(el("li", "No commands for this item.", "hint"));
  $("commands-section").hidden = false;
  $("commands-section").scrollIntoView({ behavior: "smooth" });
}

function renderItems() {
  const client = $("filter-client").value;
  const kind = $("filter-kind").value;
  const text = $("filter-text").value.trim().toLowerCase();
  const rows = state.items.filter((i) =>
    (!client || i.client === client) &&
    (!kind || i.kind === kind) &&
    (!text || `${i.name} ${i.source.path || ""} ${i.project || ""}`.toLowerCase().includes(text)));

  const body = $("items");
  body.replaceChildren();
  for (const item of rows) {
    const tr = el("tr");
    tr.append(el("td", item.client));
    tr.append(el("td", item.kind.replace("_", " ")));
    tr.append(el("td", item.name, "name"));
    tr.append(el("td", item.scope));
    tr.append(el("td", shortPath(item.project), "path"));
    tr.append(el("td", item.enabled, `state ${item.enabled}`));
    tr.append(sourceCell(item));
    tr.append(actionCell(item));
    body.append(tr);
  }
  $("count").textContent = `${rows.length} of ${state.items.length}`;
}

function fillProjects() {
  const select = $("project");
  const current = select.value;
  select.replaceChildren(el("option", "Outside any project"));
  select.firstChild.value = "";
  for (const project of state.projects) {
    const label = `${shortPath(project.path)}${project.exists ? "" : " (folder missing)"}`;
    const option = el("option", label);
    option.value = project.id;
    select.append(option);
  }
  select.value = state.projects.some((p) => p.id === current) ? current : "";
}

async function renderProject() {
  const id = $("project").value;
  const project = state.projects.find((p) => p.id === id);
  const views = $("project-views");
  views.replaceChildren();
  $("project-note").textContent = project
    ? `Known by ${project.known_by.join(", ")}`
    : "Choose a project to see what each client loads there.";
  const query = project ? `?project=${encodeURIComponent(project.path)}` : "";
  const [effective, findings] = await Promise.all([
    project ? getJson(`/api/projects/${id}/effective`) : Promise.resolve(null),
    getJson(`/api/findings${query}`),
  ]);
  for (const view of effective ? effective.views : []) {
    const box = el("div", null, "view");
    box.append(el("h3", `${view.client}: ${view.items.length} loaded`));
    const shadowed = new Set(view.shadowed.map((s) => s.name));
    const list = el("ul");
    for (const item of view.items) {
      const li = el("li");
      li.append(el("span", item.kind.replace("_", " "), "tag"));
      li.append(el("span", ` ${item.name}`, "name"));
      li.append(el("span", item.scope, "tag"));
      if (item.enabled === "unknown") li.append(el("span", "state unknown", "tag warn"));
      if (shadowed.has(item.name)) li.append(el("span", "overrides another definition", "tag"));
      if (item.via_gateway) li.append(el("span", "via gateway", "tag on"));
      if (item.source.kind === "other_client_folder") {
        li.append(el("span", `from ${item.source.owner_client}`, "tag"));
      }
      list.append(li);
    }
    box.append(list);
    views.append(box);
  }
  renderFindings(findings.filter((f) => f.type !== "bypasses_gateway"), $("findings"));
  renderFindings(findings.filter((f) => f.type === "bypasses_gateway"), $("bypasses"));
}

function renderFindings(findings, list) {
  list.replaceChildren();
  const order = { warning: 0, info: 1 };
  findings.sort((a, b) => order[a.severity] - order[b.severity] || a.type.localeCompare(b.type));
  for (const finding of findings) {
    const li = el("li", null, finding.severity);
    li.append(el("span", finding.severity, `tag ${finding.severity === "warning" ? "warn" : ""}`));
    li.append(el("span", ` ${finding.type.replaceAll("_", " ")}: `, "name"));
    li.append(el("span", finding.explanation));
    list.append(li);
  }
  if (findings.length === 0) list.append(el("li", "Nothing to report.", "hint"));
}

// Gateway (US3) --------------------------------------------------------------------------

function webLink(url, text) {
  // Only http(s) links; the server also refuses anything else (FR-040).
  if (!/^https?:\/\//i.test(url)) return el("span", url);
  const link = el("a", text);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function renderGateways() {
  const list = $("gateways");
  list.replaceChildren();
  for (const gateway of state.gateways) {
    const li = el("li");
    li.append(el("span", gateway.url, "path"));
    const login = { none: "no login", env_key: `key in $${gateway.key_env_var}`, oauth: "OAuth login" };
    li.append(el("span", login[gateway.auth] || gateway.auth, "tag"));
    if (gateway.ui_url) {
      li.append(el("span", " "));
      li.append(webLink(gateway.ui_url, "Open the gateway to turn tools on or off"));
    }
    list.append(li);
  }
  if (state.gateways.length === 0) list.append(el("li", "No gateway yet.", "hint"));

  const form = $("connect-form");
  form.hidden = state.gateways.length === 0;
  const select = $("connect-gateway");
  const current = select.value;
  select.replaceChildren();
  for (const gateway of state.gateways) {
    const option = el("option", gateway.url);
    option.value = gateway.id;
    select.append(option);
  }
  if (state.gateways.some((g) => g.id === current)) select.value = current;

  fillClientChecks($("connect-clients"));
}

function fillClientChecks(boxes) {
  const checked = new Set([...boxes.querySelectorAll("input:checked")].map((i) => i.value));
  boxes.querySelectorAll("label").forEach((label) => label.remove());
  for (const client of state.clients) {
    if (!WRITABLE_CLIENTS.includes(client.id) || client.status !== "found") continue;
    const label = el("label");
    const input = el("input");
    input.type = "checkbox";
    input.value = client.id;
    input.checked = checked.size === 0 || checked.has(client.id);
    label.append(input, el("span", ` ${client.display_name}`));
    boxes.append(label);
  }
}

function checkedClients(boxes) {
  return [...boxes.querySelectorAll("input:checked")].map((i) => ({ client: i.value }));
}

async function addSetupServer(event) {
  event.preventDefault();
  await preview({ action: "setup_server.register", targets: checkedClients($("setup-clients")), params: {} });
}

async function saveGateway(event) {
  event.preventDefault();
  const auth = $("gw-auth").value;
  const result = await postJson("/api/gateways", {
    url: $("gw-url").value.trim(),
    ui_url: $("gw-ui").value.trim() || null,
    auth,
    key_env_var: auth === "env_key" ? $("gw-key").value.trim() : null,
  });
  $("gw-message").textContent = result.ok ? "Saved." : (result.data && result.data.detail) || "Not saved.";
  if (result.ok) {
    $("gateway-add").open = false;
    await load();
  }
}

async function connectGateway(event) {
  event.preventDefault();
  await preview({
    action: "gateway.connect",
    targets: checkedClients($("connect-clients")),
    params: { gateway: $("connect-gateway").value, name: $("connect-name").value.trim() },
  });
}

// Changes --------------------------------------------------------------------------------

const STATE_TEXT = {
  previewed: "Preview. Nothing has been written yet.",
  verified: "Applied and checked.",
  stale: "Stopped: a file changed since the preview. Preview again.",
  restored: "Failed. The original settings were put back.",
  cancelled: "Cancelled. Nothing was written.",
  undone: "Undone. The previous settings are back.",
  undo_blocked: "Undo stopped: the file changed after the change was applied.",
};

async function preview(body) {
  const result = await postJson("/api/changes/preview", body);
  if (!result.ok) {
    showChangeError((result.data && result.data.detail) || `Preview failed (${result.status}).`);
    return;
  }
  showChange(result.data);
}

function showChangeError(text) {
  state.change = null;
  $("change-section").hidden = false;
  $("change-state").textContent = text;
  $("change-warning").hidden = true;
  $("change-steps").replaceChildren();
  for (const id of ["change-apply", "change-cancel", "change-undo"]) $(id).hidden = true;
  $("change-section").scrollIntoView({ behavior: "smooth" });
}

function showChange(change) {
  state.change = change;
  $("change-section").hidden = false;
  const titles = {
    "gateway.connect": "Add the gateway",
    "mcp.remove_direct": "Remove a direct MCP entry",
    "plugin.disable": "Turn a plugin off",
    "plugin.enable": "Turn a plugin on",
    "setup_server.register": "Add the \"show my setup\" server",
  };
  $("change-title").textContent = titles[change.action] || change.action;
  $("change-state").textContent = STATE_TEXT[change.state] + (change.error ? ` ${change.error}` : "");
  $("change-warning").hidden = !change.shared_file_warning;
  const steps = $("change-steps");
  steps.replaceChildren();
  for (const step of change.steps) {
    const box = el("div", null, "view");
    box.append(el("h3", `${step.client} · ${step.scope} · ${step.name}`));
    box.append(el("p", shortPath(step.path), "path"));
    box.append(el("pre", step.diff, "diff"));
    if (step.command) box.append(el("p", `Runs the client's own command: ${step.command}`, "hint"));
    if (step.restart_note) box.append(el("p", step.restart_note, "hint"));
    if (step.login_note) box.append(el("p", `Login: ${step.login_note}`));
    steps.append(box);
  }
  $("change-apply").hidden = change.state !== "previewed";
  $("change-cancel").hidden = change.state !== "previewed";
  $("change-undo").hidden = change.state !== "verified";
  $("change-section").scrollIntoView({ behavior: "smooth" });
}

async function changeVerb(verb, id) {
  const changeId = id || (state.change && state.change.id);
  if (!changeId) return;
  const result = await postJson(`/api/changes/${encodeURIComponent(changeId)}/${verb}`);
  if (result.data && result.data.id) showChange(result.data);
  else showChangeError((result.data && result.data.detail) || `Failed (${result.status}).`);
  await load();
}

function renderChangeLog() {
  const list = $("change-log");
  list.replaceChildren();
  const latest = new Map();
  for (const entry of state.changeLog) if (!latest.has(entry.id)) latest.set(entry.id, entry);
  for (const entry of latest.values()) {
    const li = el("li");
    li.append(el("span", new Date(entry.time).toLocaleString(), "tag"));
    const names = entry.steps.map((s) => `${s.client}: ${s.name}`).join(", ");
    li.append(el("span", ` ${entry.action} · ${entry.state.replace("_", " ")} · ${names}`));
    if (entry.error) li.append(el("span", ` ${entry.error}`, "hint"));
    if (entry.state === "verified") li.append(button("Undo", () => changeVerb("undo", entry.id)));
    list.append(li);
  }
  if (latest.size === 0) list.append(el("li", "No changes yet.", "hint"));
}

// Events ---------------------------------------------------------------------------------

async function rescan() {
  $("rescan").disabled = true;
  try {
    await postJson("/api/rescan");
    await load();
  } finally {
    $("rescan").disabled = false;
  }
}

function listen() {
  const events = new EventSource("/api/events");
  events.addEventListener("rescan_finished", () => load().catch(showError));
  events.addEventListener("rescan_started", () => { $("status").textContent = "Rescanning…"; });
}

function showError(error) {
  $("status").textContent = `Error: ${error.message}`;
}

document.addEventListener("DOMContentLoaded", () => {
  $("rescan").addEventListener("click", () => rescan().catch(showError));
  for (const id of ["filter-client", "filter-kind", "filter-text"]) {
    $(id).addEventListener("input", renderItems);
  }
  $("project").addEventListener("change", () => renderProject().catch(showError));
  $("gw-auth").addEventListener("change", () => { $("gw-key-label").hidden = $("gw-auth").value !== "env_key"; });
  $("gateway-form").addEventListener("submit", (e) => saveGateway(e).catch(showError));
  $("connect-form").addEventListener("submit", (e) => connectGateway(e).catch(showError));
  $("setup-form").addEventListener("submit", (e) => addSetupServer(e).catch(showError));
  $("change-apply").addEventListener("click", () => changeVerb("apply").catch(showError));
  $("change-cancel").addEventListener("click", () => changeVerb("cancel").catch(showError));
  $("change-undo").addEventListener("click", () => changeVerb("undo").catch(showError));
  $("commands-close").addEventListener("click", () => { $("commands-section").hidden = true; });
  load().catch(showError);
  listen();
});
