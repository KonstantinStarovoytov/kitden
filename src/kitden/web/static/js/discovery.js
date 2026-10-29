// Online discovery is explicit. Results only enter the normal preview tray.
import { getJson, postJson } from "./api.js";
import { button, el, icon } from "./dom.js";
import { header, openPanel, panelState, review } from "./panel.js";
import { addFormBody, clientChecks } from "./offer.js";
import { state } from "./store.js";

const LABELS = { skill: "Skill", plugin: "Plugin", mcp: "MCP server" };

export function installBody(row, clients, project = null) {
  const params = { discovery: row.id };
  const action = row.kind === "mcp" ? "gateway.add" : `${row.kind}.install`;
  params[row.kind === "mcp" ? "server" : row.kind] = row.kind === "mcp" ? `online@registry/${row.name.split("/").pop()}` : row.name;
  if (project && row.kind !== "mcp") params.project = project;
  return { action, targets: [...clients].map((client) => ({ client })), params };
}

function fail(body, message) {
  const note = el("p", "muted", message);
  note.setAttribute("role", "alert");
  body.replaceChildren(note);
}

const sessions = new Map();

// Visible mode buttons are shared by the online and local Add panels.
export function addModes(active, online, local) {
  const group = el("div", "discovery-modes");
  group.setAttribute("role", "group"); group.setAttribute("aria-label", "Find items");
  for (const [id, label, action] of [["online", "Catalogs", online], ["local", "On this Mac", local]]) {
    const choice = button(label, action, "btn");
    choice.setAttribute("aria-pressed", String(active === id)); group.append(choice);
  }
  return group;
}

export async function openDiscovery(kind = "all", options = {}) {
  const title = kind === "mcp" ? "Add an MCP server" : "Add a plugin or skill";
  const head = header(kind === "mcp" ? "Gateway" : "Library", title, null);
  const body = el("div", "body discovery");
  const modes = options.local ? addModes("online", () => {}, options.local) : null;
  if (modes) body.append(modes);
  const loading = el("p", "muted", "Reading catalogs…"); body.append(loading);
  panelState.current = { type: "discovery" };
  openPanel([head, body]);
  let data;
  try { data = await getJson("/api/discovery/sources"); }
  catch { loading.textContent = "Could not read catalogs. Close and try again."; return; }
  if (!body.isConnected) return;
  loading.remove();
  if (data.offline) {
    body.append(el("p", "muted", "This sample stays offline. Choose On this Mac to browse its items."));
    return;
  }
  const saved = sessions.get(kind);
  const model = { source: saved?.source || (kind === "mcp" ? "mcp-registry" : "skills.sh"), kind: saved?.kind || kind };
  let sources = data.sources.filter((source) => kind === "mcp" ? ["mcp", "github"].includes(source.kind) : source.kind !== "mcp");
  const sourceButtons = el("div", "discovery-choices");
  sourceButtons.setAttribute("role", "group"); sourceButtons.setAttribute("aria-label", "Source");
  const sourceLabel = el("p", "discovery-label", "Search in");
  const input = el("input"); input.type = "search"; input.value = saved?.query || "";
  input.placeholder = kind === "mcp" ? "Search MCP servers…" : "Search plugins and skills…";
  input.setAttribute("aria-label", "Search catalogs");
  const field = el("label", "discovery-search"); field.append(icon("search", 15), input);
  const form = el("form", "discovery-search-form");
  const search = button("Search", () => {}, "btn primary"); search.type = "submit";
  form.append(field, search);
  const filters = el("div", "discovery-choices discovery-filters");
  filters.setAttribute("role", "group"); filters.setAttribute("aria-label", "Show");
  const status = el("p", "muted discovery-status"); status.setAttribute("role", "status");
  const results = el("div", "add-list");
  let sequence = 0;
  const invalidate = () => {
    sequence++; search.disabled = false; status.textContent = ""; results.replaceChildren();
    sessions.delete(kind);
  };
  const remember = (answer) => sessions.set(kind, { ...model, query: input.value, answer });
  const draw = (answer) => {
    results.replaceChildren();
    status.textContent = answer.results.length ? `${answer.results.length} results` : "No matches. Try another search or catalog.";
    for (const row of answer.results) {
      const line = button("", () => itemDetails(row, answer.clients, kind, options), "res");
      const tile = el("span", "itile");
      tile.append(icon(row.kind === "skill" ? "sparkles" : row.kind === "plugin" ? "puzzle" : "server", 14));
      const text = el("span", "tx");
      text.append(el("b", null, row.name), el("small", null, `${LABELS[row.kind]} · ${row.repo || row.source}`));
      line.append(tile, text, el("span", "st", row.held ? "In gateway" : row.installed.length ? "Installed" : "Review"));
      results.append(line);
    }
  };
  const paintSources = () => {
    const available = sources.filter((source) => model.kind !== "plugin" || source.kind === "github");
    if (!available.some((source) => source.id === model.source)) model.source = available[0]?.id;
    sourceButtons.replaceChildren();
    for (const source of available) {
      const choice = button(source.name, () => { model.source = source.id; invalidate(); paintSources(); }, "btn small");
      choice.setAttribute("aria-pressed", String(source.id === model.source)); sourceButtons.append(choice);
    }
  };
  const paintFilters = () => {
    filters.replaceChildren();
    if (kind === "mcp") return;
    for (const [id, label] of [["all", "All"], ["plugin", "Plugins"], ["skill", "Skills"]]) {
      const choice = button(label, () => { model.kind = id; invalidate(); paintFilters(); paintSources(); }, "btn small");
      choice.setAttribute("aria-pressed", String(model.kind === id)); filters.append(choice);
    }
  };
  paintSources(); paintFilters();
  input.addEventListener("input", invalidate);
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); const turn = ++sequence;
    search.disabled = true; status.textContent = "Searching…"; results.replaceChildren();
    try {
      const answer = await postJson("/api/discovery/search", { source: model.source, query: input.value, kind: model.kind });
      if (turn !== sequence || !body.isConnected) return;
      if (!answer.ok) throw new Error(answer.data?.detail || "Could not search this catalog. Try again.");
      remember(answer.data); draw(answer.data);
    } catch (error) { if (turn === sequence && body.isConnected) status.textContent = error.message; }
    finally { if (turn === sequence) search.disabled = false; }
  });
  const add = el("input"); add.placeholder = "owner/repo or a GitHub link";
  add.setAttribute("aria-label", "GitHub source");
  const sourceField = el("label", "field grow"); sourceField.append(el("span", null, "Repository"), add);
  const addForm = el("form", "form");
  const save = button("Add source", () => {}, "btn"); save.type = "submit"; addForm.append(sourceField, save);
  addForm.addEventListener("submit", async (event) => {
    event.preventDefault(); save.disabled = true;
    try {
      const answer = await postJson("/api/discovery/sources", { source: add.value });
      if (!body.isConnected) return;
      if (!answer.ok) throw new Error(answer.data?.detail || "Could not add this source.");
      sources = answer.data.sources.filter((source) => kind === "mcp" ? ["mcp", "github"].includes(source.kind) : source.kind !== "mcp");
      const repo = add.value.trim().replace(/^https:\/\/github.com\//, "").replace(/\.git$/, "").replace(/\/$/, "");
      model.source = repo; invalidate(); paintSources();
      status.textContent = "Source added. Search above, or leave the search empty to browse."; add.value = "";
    } catch (error) { if (body.isConnected) status.textContent = error.message; }
    finally { save.disabled = false; }
  });
  const more = el("details", "discovery-source-add");
  more.append(el("summary", null, "Add a GitHub source"), el("p", "muted", "Add a repository you want to browse. Client settings change only after Apply."), addForm);
  body.append(form, filters, sourceLabel, sourceButtons, more, status, results);
  if (saved?.answer) draw(saved.answer);
  input.focus();
}

async function itemDetails(row, clients, kind, options) {
  const installed = row.installed;
  const loading = el("div", "body", "Reading source…");
  openPanel([header("Online source", row.name, null), loading]);
  const answer = await postJson("/api/discovery/details", { id: row.id });
  if (!loading.isConnected) return;
  if (!answer.ok) { fail(loading, answer.data?.detail || "Could not read this item."); return; }
  row = { ...row, ...answer.data, installed };
  const head = header("Online source", row.name, row.description || LABELS[row.kind]);
  const body = el("div", "body discovery");
  body.append(button("Back to search", () => openDiscovery(kind, options), "btn ghost small"));
  const details = el("details");
  details.append(el("summary", null, "Source details"));
  details.append(el("p", "muted", `Source: ${row.repo || row.source}`));
  if (row.commit || row.version) details.append(el("p", "muted", `Version: ${row.commit || row.version}`));
  if (row.repo) {
    const link = el("a", null, "Open on GitHub");
    link.href = `https://github.com/${row.repo}${row.commit ? `/tree/${row.commit}` : ""}`;
    link.target = "_blank"; link.rel = "noopener noreferrer"; details.append(link);
  }
  if (row.path) details.append(el("p", "muted", `Skill folder: ${row.path}`));
  if (row.content) details.append(el("pre", "diff", row.content));
  body.append(details);
  body.append(el("p", "muted", "Review the source before installing. Plugins, skills and servers can run code through your coding client."));
  if (row.held) body.append(el("p", "muted", "Already in the Kitden gateway."));
  else if (row.refusal) body.append(el("p", "muted", row.refusal));
  else if (row.kind === "mcp") {
    const chosen = new Set(["gateway"]);
    body.append(el("p", "muted", "Adds to the Kitden gateway for all projects. Connect clients to the gateway to use it."));
    body.append(addFormBody(el("div"), chosen, () => installBody(row, []), (request) => review(request)));
  } else {
    const available = clients.filter((c) => (row.kind !== "plugin" || ["claude_code", "codex"].includes(c)) && !row.installed.includes(c));
    const chosen = new Set();
    let project = null;
    if (state.project && row.kind === "skill") {
      const scope = el("label", "field");
      const check = el("input"); check.type = "checkbox";
      check.addEventListener("change", () => { project = check.checked ? state.project : null; });
      scope.append(check, el("span", null, "Only this project")); body.append(scope);
    }
    if (available.length) {
      let submit;
      const checks = clientChecks(available, chosen, null, () => { if (submit) submit.disabled = !chosen.size; });
      const form = addFormBody(checks, chosen, () => installBody(row, chosen, project), (request) => review(request));
      submit = form.querySelector('button[type="submit"]'); submit.disabled = true;
      body.append(form);
    }
    else body.append(el("p", "muted", "Already installed, or no supported client is available."));
  }
  openPanel([head, body]);
}
