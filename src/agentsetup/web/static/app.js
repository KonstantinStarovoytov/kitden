// Agent setup page. All text from client files is untrusted (FR-041):
// it is only ever set with textContent, never as HTML.
"use strict";

const state = { clients: [], items: [], problems: [], projects: [] };
const $ = (id) => document.getElementById(id);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
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

async function load() {
  $("status").textContent = "Loading…";
  const [clients, items, problems, projects] = await Promise.all([
    getJson("/api/clients"), getJson("/api/items"), getJson("/api/problems"),
    getJson("/api/projects"),
  ]);
  Object.assign(state, { clients, items, problems, projects });
  renderClients();
  renderProblems();
  fillFilters();
  renderItems();
  fillProjects();
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
  return td;
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
      if (item.source.kind === "other_client_folder") {
        li.append(el("span", `from ${item.source.owner_client}`, "tag"));
      }
      list.append(li);
    }
    box.append(list);
    views.append(box);
  }
  renderFindings(findings);
}

function renderFindings(findings) {
  const list = $("findings");
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

async function rescan() {
  $("rescan").disabled = true;
  try {
    await fetch("/api/rescan", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Tool-Request": "1" },
    });
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
  load().catch(showError);
  listen();
});
