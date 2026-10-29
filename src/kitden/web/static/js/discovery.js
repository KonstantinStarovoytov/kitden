// Online discovery is explicit. Results only enter the normal preview tray.
import { getJson, postJson } from "./api.js";
import { button, el, icon } from "./dom.js";
import { header, openPanel, review } from "./panel.js";
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

export async function openDiscovery(kind = "all") {
  const head = header(kind === "mcp" ? "Gateway" : "Library", kind === "mcp" ? "Find an MCP server" : "Find plugins and skills", "Search a source, review an item, then preview its install.");
  const body = el("div", "body discovery");
  openPanel([head, body]);
  let data;
  try { data = await getJson("/api/discovery/sources"); }
  catch { fail(body, "Could not read sources. Close and try again."); return; }
  if (!body.isConnected) return;
  if (data.offline) {
    body.append(el("p", "muted", "The sample stays offline. Open your own setup to search online sources."));
    return;
  }
  const source = el("select");
  source.setAttribute("aria-label", "Source");
  const sources = data.sources.filter((s) => kind === "mcp" ? ["mcp", "github"].includes(s.kind) : s.kind !== "mcp");
  for (const s of sources) {
    const option = el("option", null, s.name);
    option.value = s.id;
    source.append(option);
  }
  const input = el("input");
  input.type = "search";
  input.placeholder = "Search by name or topic";
  input.setAttribute("aria-label", "Search online sources");
  const kinds = el("select");
  kinds.setAttribute("aria-label", "Kind");
  for (const [value, label] of (kind === "mcp" ? [["mcp", "MCP servers"]] : [["all", "Plugins and skills"], ["plugin", "Plugins"], ["skill", "Skills"]])) {
    const option = el("option", null, label); option.value = value; kinds.append(option);
  }
  const form = el("form", "form");
  const status = el("p", "muted");
  status.setAttribute("role", "status");
  const results = el("div", "add-list");
  let sequence = 0;
  const search = button("Search", () => {}, "btn primary");
  search.type = "submit";
  kinds.addEventListener("change", () => {
    if (kinds.value === "plugin" && source.value === "skills.sh") source.value = sources.find((s) => s.kind === "github")?.id || source.value;
  });
  const field = (label, control, extra = "") => {
    const node = el("label", `field ${extra}`);
    node.append(el("span", null, label), control); return node;
  };
  form.append(field("Source", source));
  if (kind !== "mcp") form.append(field("Show", kinds));
  form.append(field("Search", input, "grow"), search);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const turn = ++sequence;
    search.disabled = true;
    status.textContent = "Searching…";
    results.replaceChildren();
    try {
      const answer = await postJson("/api/discovery/search", { source: source.value, query: input.value, kind: kinds.value });
      if (turn !== sequence || !body.isConnected) return;
      if (!answer.ok) throw new Error(answer.data?.detail || "Could not search this source. Try again.");
      status.textContent = answer.data.results.length ? `${answer.data.results.length} results. Open one to review.` : "No matches. Try another name or source.";
      for (const row of answer.data.results) {
        const line = button("", () => itemDetails(row, answer.data.clients, kind), "res");
        const tile = el("span", "itile");
        tile.append(icon(row.kind === "skill" ? "sparkles" : row.kind === "plugin" ? "puzzle" : "server", 14));
        const text = el("span", "tx");
        text.append(el("b", null, row.name), el("small", null, `${LABELS[row.kind]} · ${row.repo || row.source}`));
        line.append(tile, text, el("span", "st", row.held ? "In gateway" : row.installed.length ? "Installed" : "Available"));
        results.append(line);
      }
    } catch (error) { if (turn === sequence && body.isConnected) status.textContent = error.message; }
    finally { if (turn === sequence) search.disabled = false; }
  });
  const invalidate = () => {
    sequence++; search.disabled = false; status.textContent = ""; results.replaceChildren();
  };
  source.addEventListener("change", invalidate);
  kinds.addEventListener("change", invalidate);
  input.addEventListener("input", invalidate);
  const add = el("input");
  add.placeholder = "owner/repo or a GitHub repository link";
  add.setAttribute("aria-label", "GitHub source");
  const addForm = el("form", "form");
  const save = button("Add GitHub source", () => {}, "btn ghost"); save.type = "submit";
  addForm.append(field("GitHub repository", add, "grow"), save);
  addForm.addEventListener("submit", async (event) => {
    event.preventDefault(); save.disabled = true;
    try {
      const answer = await postJson("/api/discovery/sources", { source: add.value });
      if (!answer.ok) throw new Error(answer.data?.detail || "Could not add this source.");
      for (const s of answer.data.sources) {
        if ([...source.options].some((o) => o.value === s.id)) continue;
        const option = el("option", null, s.name); option.value = s.id; source.append(option);
      }
      source.value = answer.data.sources.find((s) => s.id === add.value.trim())?.id || answer.data.sources.at(-1).id;
      status.textContent = "Source added. Search it above; leave the search empty to browse.";
      add.value = "";
    } catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; }
  });
  const sourcesPanel = el("details");
  sourcesPanel.append(el("summary", null, "Add a GitHub source"), el("p", "muted", "Saves a catalog source only. Client settings wait for Apply."), addForm);
  body.append(form, sourcesPanel, status, results);
  input.focus();
}

async function itemDetails(row, clients, kind) {
  const installed = row.installed;
  const loading = el("div", "body", "Reading source…");
  openPanel([header("Online source", row.name, null), loading]);
  const answer = await postJson("/api/discovery/details", { id: row.id });
  if (!loading.isConnected) return;
  if (!answer.ok) { fail(loading, answer.data?.detail || "Could not read this item."); return; }
  row = { ...answer.data, installed };
  const head = header("Online source", row.name, row.description || LABELS[row.kind]);
  const body = el("div", "body discovery");
  body.append(button("Back to search", () => openDiscovery(kind), "btn ghost small"));
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
    const chosen = new Set(available);
    let project = null;
    if (state.project && row.kind === "skill") {
      const scope = el("label", "field");
      const check = el("input"); check.type = "checkbox";
      check.addEventListener("change", () => { project = check.checked ? state.project : null; });
      scope.append(check, el("span", null, "Only this project")); body.append(scope);
    }
    if (available.length) body.append(addFormBody(clientChecks(available, chosen), chosen, () => installBody(row, chosen, project), (request) => review(request)));
    else body.append(el("p", "muted", "Already installed, or no supported client is available."));
  }
  openPanel([head, body]);
}
