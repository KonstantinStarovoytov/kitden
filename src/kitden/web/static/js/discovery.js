// Online discovery is explicit. Results only enter the normal preview tray.
import { getJson, postJson } from "./api.js";
import { button, el, icon } from "./dom.js";
import { header, openPanel, panelState, review } from "./panel.js";
import { accessForm, openAccess } from "./access-form.js";
import { addFormBody, clientChecks } from "./offer.js";
import { state } from "./store.js";
import { cancelTray, inTray, keyFor, tray } from "./tray.js";

// The token field a remote server gets when its entry declares none (actions.py TOKEN_FIELD).
const TOKEN_FIELD = { field: "headers", name: "Authorization", label: "Access token", prefix: "Bearer " };

const LABELS = { skill: "Skill", plugin: "Plugin", mcp: "MCP server" };

export function sourceFitsPage(source, kind) {
  if (kind !== "mcp") return source.kind !== "mcp";
  return source.kind === "mcp" || (source.kind === "github" && source.id !== "anthropics/claude-plugins-official");
}


// The kind ("remote" or "local") of each online server a body was made for, by its server param:
// the Gateway map puts its preview in that group.
const serverKinds = new Map();
export const onlineKind = (server) => serverKinds.get(server) || null;

export function installBody(row, clients, project = null) {
  const params = { discovery: row.id };
  const action = row.kind === "mcp" ? "gateway.add" : `${row.kind}.install`;
  params[row.kind === "mcp" ? "server" : row.kind] = row.kind === "mcp" ? `online@registry/${row.short || row.name.split("/").pop()}` : row.name;
  if (row.kind === "mcp") serverKinds.set(params.server, row.remote ? "remote" : "local");
  // Access values typed in the details (headers, env) go with the change; Preview checks them.
  if (row.kind === "mcp" && row.access) Object.assign(params, structuredClone(row.access));
  if (project && row.kind !== "mcp") params.project = project;
  return { action, targets: [...clients].map((client) => ({ client })), params };
}

function fail(body, message) {
  body.classList.remove("catalog-progress", "catalog-loading");
  body.removeAttribute("role"); body.removeAttribute("aria-label"); body.removeAttribute("aria-busy");
  const note = el("p", "muted", message);
  note.setAttribute("role", "alert");
  body.replaceChildren(note);
}

const sessions = new Map();
function progress(label) {
  const node = el("div", "catalog-progress");
  node.setAttribute("role", "progressbar"); node.setAttribute("aria-label", label);
  return node;
}

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
  const loading = progress("Loading catalogs"); body.append(loading);
  panelState.current = { type: "discovery" };
  openPanel([head, body]);
  let data;
  try { data = await getJson("/api/discovery/sources"); }
  catch { fail(loading, "Could not read catalogs. Close and try again."); return; }
  if (!body.isConnected) return;
  loading.remove();
  if (data.offline) {
    body.append(el("p", "muted", "This sample stays offline. Choose On this Mac to browse its items."));
    return;
  }
  const saved = sessions.get(kind);
  const model = { source: saved?.source || (kind === "mcp" ? "mcp-registry" : "skills.sh"), kind: saved?.kind || kind };
  let sources = data.sources.filter((source) => sourceFitsPage(source, kind));
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
  const results = el("div", "add-list discovery-results");
  const inspector = el("section", "discovery-inspector");
  inspector.setAttribute("aria-label", "Item details");
  inspector.append(el("p", "muted", "Choose an item to see what it does and where to add it."));
  const workspace = el("div", "discovery-workspace"); workspace.append(results, inspector);
  let sequence = 0;
  const invalidate = () => {
    inspector.replaceChildren(el("p", "muted", "Choose an item to see its details.")); sequence++; search.disabled = false; status.textContent = ""; results.replaceChildren();
    sessions.delete(kind);
  };
  const remember = (answer) => sessions.set(kind, { ...model, query: input.value, answer });
  const draw = (answer) => {
    results.replaceChildren();
    status.textContent = answer.results.length ? `${answer.results.length} results` : "No matches. Try another search or catalog.";
    const query = input.value.trim().toLowerCase().replace(/[-_]/g, " ");
    const score = (r) => { const name = r.name.toLowerCase().replace(/[-_]/g, " "); return name === query ? 3 : name.startsWith(query) ? 2 : 1; };
    for (const row of [...answer.results].sort((a, b) => score(b) - score(a) || (b.installs || 0) - (a.installs || 0))) {
      const line = button("", () => {
        for (const sibling of results.children) sibling.setAttribute("aria-pressed", "false");
        line.setAttribute("aria-pressed", "true");
        line.classList.add("catalog-loading"); line.setAttribute("aria-busy", "true");
        itemDetails(row, answer.clients, kind, options, inspector, (resolved) => { Object.assign(row, resolved); paint(); }).finally(() => { line.classList.remove("catalog-loading"); line.removeAttribute("aria-busy"); }).catch(() => { if (inspector.isConnected) fail(inspector, "Could not read this item. Select it to try again."); });
      }, "res");
      const tile = el("span", "itile");
      tile.append(icon(row.kind === "skill" ? "sparkles" : row.kind === "plugin" ? "puzzle" : "server", 14));
      const text = el("span", "tx");
      const displayName = row.kind === "mcp" ? row.short || row.name.split("/").pop() : row.name;
      const publisher = row.kind === "mcp" ? row.name.split("/").slice(0, -1).join("/").replace(/^io\.github\./, "") : row.repo || row.source;
      text.append(el("b", null, displayName), el("small", null, publisher || row.source));
      const st = el("span", "st", row.held ? "In gateway" : row.refusal ? "Unavailable" : row.installed.length ? "Installed" : "");
      line.append(tile, text, st);
      if (Number.isFinite(row.installs)) text.append(el("small", "catalog-popularity", `${new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(row.installs)} installs`));
      // A free row drags. One that needs access says "Needs token" (or "Needs sign-in") in amber
      // until its details hold values that work (`row.access`); dropped without them, it waits in
      // preview for its token.
      const free = !row.held && !row.refusal && !row.installed.length && Boolean(options.drag);
      let grip = null;
      const paint = () => {
        if (!free) return;
        const waits = Boolean((row.access_required || row.setup?.length) && (!row.access || row.refused));
        line.classList.add("drags");
        if (!grip) { grip = icon("grip-vertical", 12, "ic grip"); line.prepend(grip); }
        st.textContent = waits ? (row.access_kind === "sign-in" ? "Needs sign-in" : "Needs token") : "";
        st.classList.toggle("warn", waits);
        line.title = waits ? "Needs a token. Click to add it, or drag it to wait in preview."
          : row.kind === "mcp" ? "Drag to the gateway to preview" : "Drag onto a client to preview";
      };
      if (free) line.addEventListener("pointerdown", (event) => { if (line.classList.contains("drags")) options.drag(event, row, answer.clients, line); });
      paint();
      results.append(line);
    }
  };
  const paintSources = () => {
    const available = sources.filter((source) => model.kind !== "plugin" || source.kind === "github");
    if (!available.some((source) => source.id === model.source)) model.source = available[0]?.id;
    sourceButtons.replaceChildren();
    // One catalog is no choice: its label and chip stay hidden.
    sourceLabel.hidden = sourceButtons.hidden = available.length < 2;
    for (const source of available) {
      const choice = button(source.name, () => { model.source = source.id; invalidate(); paintSources(); runSearch(); }, "btn small");
      choice.setAttribute("aria-pressed", String(source.id === model.source)); sourceButtons.append(choice);
    }
  };
  const paintFilters = () => {
    filters.replaceChildren();
    if (kind === "mcp") return;
    for (const [id, label] of [["all", "All"], ["plugin", "Plugins"], ["skill", "Skills"]]) {
      const choice = button(label, () => { model.kind = id; invalidate(); paintFilters(); paintSources(); runSearch(); }, "btn small");
      choice.setAttribute("aria-pressed", String(model.kind === id)); filters.append(choice);
    }
  };
  paintSources(); paintFilters();
  let searchTimer;
  input.addEventListener("input", () => {
    invalidate(); clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { if (body.isConnected && (!input.value.trim() || input.value.trim().length >= 3)) runSearch(); }, 350);
  });
  const runSearch = async () => {
    clearTimeout(searchTimer); const turn = ++sequence;
    search.disabled = true; status.textContent = "Searching…";
    if (!results.children.length) for (let i = 0; i < 3; i++) results.append(progress("Loading results"));
    for (const block of results.children) block.classList.add("catalog-loading");
    try {
      const answer = await postJson("/api/discovery/search", { source: model.source, query: input.value, kind: model.kind });
      if (turn !== sequence || !body.isConnected) return;
      if (!answer.ok) throw new Error(answer.data?.detail || "Could not search this catalog. Try again.");
      remember(answer.data); draw(answer.data);
    } catch (error) { if (turn === sequence && body.isConnected) { status.textContent = error.message; for (const block of [...results.children]) if (block.classList.contains("catalog-progress")) block.remove(); } }
    finally { if (turn === sequence) { search.disabled = false; for (const block of results.children) block.classList.remove("catalog-loading"); } }
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); runSearch(); });
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
      sources = answer.data.sources.filter((source) => sourceFitsPage(source, kind));
      const repo = add.value.trim().replace(/^https:\/\/github.com\//, "").replace(/\.git$/, "").replace(/\/$/, "");
      model.source = repo; invalidate(); paintSources();
      status.textContent = "Source added."; add.value = ""; showSources(); more.open = false; runSearch();
    } catch (error) { if (body.isConnected) status.textContent = error.message; }
    finally { save.disabled = false; }
  });
  const more = el("details", "discovery-source-add");
  more.append(el("summary", null, "Add a GitHub source"), el("p", "muted", "Add a repository you want to browse. Client settings change only after Apply."), addForm);
  const manage = button("Sources", () => { more.open = !more.open; }, "btn");
  form.append(manage);
  const sourceList = el("div", "discovery-source-list");
  const showSources = () => {
    sourceList.replaceChildren();
    for (const source of sources.filter((s) => !["skills.sh", "mcp-registry", "anthropics/claude-plugins-official"].includes(s.id))) {
      const line = el("div", "discovery-source-row");
      line.append(el("span", null, source.name));
      const change = async (operation, value = source.id) => {
        const answer = await postJson("/api/discovery/sources", { operation, previous: source.id, source: value });
        if (!body.isConnected) return;
        if (!answer.ok) { status.textContent = answer.data?.detail || "Could not update source."; return false; }
        sources = answer.data.sources.filter((s) => sourceFitsPage(s, kind));
        invalidate(); paintSources(); showSources(); runSearch(); return true;
      };
      line.append(button("Edit", () => {
        const edit = el("input"); edit.value = source.id; edit.setAttribute("aria-label", "Repository");
        line.replaceChildren(edit, button("Save", () => change("edit", edit.value), "btn"), button("Cancel", showSources, "btn ghost"));
      }, "btn ghost small"), button("Remove", async () => {
        if (!await change("remove") || !body.isConnected) return;
        const undo = button("Undo removal", async () => { await change("add"); undo.remove(); }, "btn");
        sourceList.append(undo);
      }, "btn ghost small"));
      sourceList.append(line);
    }
  };
  more.prepend(el("p", "muted", "Built-in catalogs are available above. Add public GitHub repositories here. Removing a source keeps installed items."), sourceList);
  showSources();
  const hint = el("p", "muted discovery-hint", kind === "mcp"
    ? "Click to review · drag onto the gateway"
    : "Click to review · drag onto a client");
  body.append(form, filters, sourceLabel, sourceButtons, more, hint, status, workspace);
  if (saved?.answer) draw(saved.answer);
  else runSearch();
  input.focus();
}

async function itemDetails(row, clients, kind, options, inspector = null, onResolved = () => {}) {
  const installed = row.installed;
  const loading = progress("Loading details");
  if (inspector) inspector.replaceChildren(loading);
  else openPanel([header("Online source", row.name, null), loading]);
  let answer;
  try { answer = await postJson("/api/discovery/details", { id: row.id }); }
  catch {
    if (loading.isConnected) fail(loading, "Could not read this item. Select it to try again.");
    return;
  }
  if (!loading.isConnected) return;
  if (!answer.ok) { fail(loading, answer.data?.detail || "Could not read this item."); return; }
  row = { ...row, ...answer.data, installed };
  if (row.choices) {
    const choices = el("div", "body discovery");
    choices.append(el("h2", null, "Choose a skill"), el("p", "muted", "Choose the folder to review from this repository."));
    for (const candidate of row.choices) {
      const choice = button(candidate.name, () => {
        const target = inspector || choices;
        itemDetails({ ...candidate, installed: installed || [] }, clients, kind, options, target, onResolved)
          .catch(() => { if (target.isConnected) fail(target, "Could not read this skill. Select the result to try again."); });
      }, "btn");
      const details = el("details");
      details.append(el("summary", null, "Folder"), el("p", "muted", candidate.path));
      choices.append(choice, details);
    }
    if (inspector) inspector.replaceChildren(choices);
    else loading.replaceWith(choices);
    return;
  }
  onResolved(row);
  if (row.kind === "skill" && row.content?.startsWith("---")) {
    const front = row.content.split("---")[1] || "";
    const match = front.match(/^description:\s*(.+)$/m);
    if (match && ![">", "|", ">-", "|-"].includes(match[1].trim())) row.description = match[1].trim().replace(/^["']|["']$/g, "");
  }
  const head = header("Online source", row.name, row.description || LABELS[row.kind]);
  const body = el("div", "body discovery");
  if (!inspector) body.append(button("Back to search", () => openDiscovery(kind, options), "btn ghost small"));
  else body.append(el("h2", null, row.kind === "mcp" ? row.short || row.name.split("/").pop() : row.name));
  const description = row.description || LABELS[row.kind];
  body.append(el("p", "muted", description.length > 240 ? description.slice(0, 237).trimEnd() + "…" : description));
  if (description.length > 240) {
    const more = el("details");
    more.append(el("summary", null, "Read more"), el("p", "muted", description));
    body.append(more);
  }
  const details = el("details");
  details.append(el("summary", null, "Source details"));
  details.append(el("p", "muted", `Source: ${row.repo || row.source}`));
  if (row.kind === "mcp") details.append(el("p", "muted", `Identifier: ${row.name}`));
  if (row.commit || row.version) details.append(el("p", "muted", `Version: ${row.commit || row.version}`));
  if (row.repo) {
    const link = el("a", null, "Open on GitHub");
    link.href = `https://github.com/${row.repo}${row.commit ? `/tree/${row.commit}` : ""}`;
    link.target = "_blank"; link.rel = "noopener noreferrer"; details.append(link);
  }
  if (row.path) details.append(el("p", "muted", `Skill folder: ${row.path}`));
  if (row.content) details.append(el("pre", "diff", row.content));
  body.append(details);
  if (row.kind !== "mcp") body.append(el("p", "muted", "Review the source before installing. Plugins and skills can run code through your coding client."));
  if (row.held) body.append(el("p", "muted", "Already in the Kitden gateway."));
  else if (row.refusal) body.append(el("p", "muted", row.refusal));
  else if (row.kind === "mcp") {
    const chosen = new Set(["gateway"]);
    body.append(el("p", "muted", "Adds to the gateway for all projects."));
    if (row.access_note) body.append(el("p", "muted", row.access_note));
    const definitions = [...(row.setup || [])];
    if (row.remote && !definitions.some((f) => f.field === "headers" && f.name === "Authorization")) {
      definitions.push({ ...TOKEN_FIELD, optional: !row.access_required });
    }
    const name = row.short || row.name.split("/").pop();
    const requestOf = (access) => installBody({ ...row, access }, []);
    if (row.access_kind === "sign-in" && !(row.setup || []).length) {
      // Sign in adds the row, which waits for its sign-in, then starts it in the row's panel.
      const go = el("button", "btn primary", "Sign in");
      go.type = "button";
      go.addEventListener("click", async () => {
        const request = requestOf(null);
        await review(request);
        const found = tray.rows.find((each) => each.key === keyFor(request));
        if (found && found.waits && found.waits.sign_in) openAccess(found, { start: true });
        else if (found) options.added?.(request);
      });
      body.append(go);
    } else if (!definitions.length) {
      body.append(addFormBody(null, chosen, () => requestOf(null), async (request) => {
        await review(request);
        if (inTray(keyFor(request))) options.added?.(request);
      }));
    } else {
      // One form for the values the server needs: Add token previews it, which is the check.
      const waits = { server: name, kind: row.access_kind === "sign-in" ? "sign-in" : "token", fields: definitions };
      const form = accessForm(waits, async (access) => {
        const request = requestOf(access);
        const before = tray.refused;
        const prior = tray.rows.find((each) => each.key === keyFor(request));
        await review(request);
        // A row that is still the one from before means this ask did not join.
        const found = tray.rows.find((each) => each.key === keyFor(request));
        const queued = found !== prior ? found : null;
        if (queued && !queued.waits) {
          if (access) form.works();
          onResolved({ access, refused: false });
          options.added?.(request);
        } else if (queued && queued.waits.refused) {
          form.refuse(queued.waits.reason);
          onResolved({ access: null, refused: true });
        } else if (queued) options.added?.(request);
        else if (tray.refused && tray.refused !== before) {
          form.refuse(tray.refused.reason);
          // Said here, by the token: an empty tray's own notice would only repeat it.
          if (!tray.rows.length) cancelTray();
        }
      });
      body.append(form.node);
    }
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
  if (inspector) inspector.replaceChildren(body);
  else openPanel([head, body]);
}
