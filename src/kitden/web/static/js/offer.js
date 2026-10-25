// Details of a plugin or skill from the marketplaces on this computer, every way to add it (or
// why there is none), and the forms that add one to several clients in one review. The Library
// opens these Details for rows not on this computer; the panel's Details use the parts.
import { busyWhile, button, el, joinWords, plural, reportError, webLink } from "./dom.js";
import { noteFor, rowTitle, startAdd } from "./library.js";
import { closePanel, footerActions, footerButtons, openInfo, openPanel, review, technical } from "./panel.js";
import { CLIENT_NAMES, clientCheck, REACH_NOTES } from "./parts.js";
import { data, go, state } from "./store.js";

// Clients whose own command line installs plugins. Cursor keeps its plugins in the account,
// and it loads Claude Code's plugins by itself when "Include Third-Party Plugins" is on.
const INSTALLERS = ["claude_code", "codex"];
const COLUMNS = ["claude_code", "codex", "cursor"];
const ROUTE_WORDS = { ready: "Ready", add_marketplace: "Adds the marketplace first" };
const NEEDS_PLUGIN = "This skill needs the rest of its plugin. Add the plugin instead.";
// What Cursor also loads, per way in; the server reads Cursor's switches. A Codex copy goes to
// ~/.agents/skills, which Cursor always reads (checked against Cursor's docs, 2026-10-19).
const ALSO_LOADS = {
  plugin: "Cursor will also load this through Claude Code.",
  skill: "Cursor will also load it from Claude Code's folder.",
  shared: "Cursor will also load it from the shared skills folder.",
};
const PROJECT_NOTE = "Adds for all projects.";
const SKILL_COPIES = ["skill.install", "plugin.skills"];

// In a project view an add still goes to the user's settings; the review says so.
export function projectNote(project) {
  return project ? PROJECT_NOTE : null;
}

// Whether Cursor loads Claude Code's plugins and the skills in its folder; /api/offer says.
function inherits(offer) {
  return offer.inherits || { plugin: false, skill: false };
}

// The Cursor line in a plugin's Details, or "". Cursor loads it through Claude Code only when
// Claude Code has it and Cursor imports its plugins. If Claude Code can only take it, Cursor gets
// it after you add it there. A plugin Cursor holds itself is Cursor's own.
export function cursorLine(offer, inherits) {
  if (inherits.plugin && offer.installed.includes("claude_code")) return "Cursor: loads it through Claude Code.";
  if (offer.installed.includes("cursor")) return "Cursor: has it.";
  return inherits.plugin && offer.routes.claude_code ? "Cursor: gets it through Claude Code once you add it there." : "";
}

// The clients this computer has, in the Library's order; all three before they are read.
function columns() {
  const found = (data.clients || []).filter((c) => c.status === "found").map((c) => c.id);
  const shown = COLUMNS.filter((c) => !data.clients || found.includes(c));
  return shown.length ? shown : COLUMNS;
}

function section(title, children) {
  const box = el("section");
  box.append(el("h2", null, title), ...children);
  return box;
}

export function inside(offer) {
  const got = offer.inside;
  if (!got) return [el("p", "muted", "What it holds is read once the client downloads it.")];
  const lines = [];
  const add = (label, names) => { if (names.length) lines.push(el("li", null, `${label}: ${names.join(", ")}`)); };
  add("Skills", got.skills);
  add("Commands", got.commands);
  add("Agents", got.agents);
  // What each server runs waits under Technical details (mcpRows).
  add("MCP servers", got.mcp_servers.map((server) => server.name));
  const out = [];
  if (got.hooks.length) {
    out.push(el("p", "callout", `Runs by itself on: ${got.hooks.join(", ")}. Hooks run commands without asking each time.`));
  }
  const list = el("ul", "checklist");
  list.append(...lines);
  if (lines.length) out.push(list);
  if (!out.length) out.push(el("p", "muted", "Nothing that runs by itself."));
  return out;
}

// The evidence of a plugin's entry, as rows of Technical details: what each MCP server in it
// runs. None until the client downloads it.
export function mcpRows(offer) {
  const servers = (offer.inside && offer.inside.mcp_servers) || [];
  return servers.map((server) => ({ title: `MCP server ${server.name}`, summary: server.runs }));
}

// Where a plugin's files come from (a repository, an address or a folder) and the version it is
// pinned to, as rows of Technical details.
export function sourceRows(offer) {
  const source = offer.source || {};
  const where = source.repo || source.url || source.path;
  const rows = [];
  if (where) rows.push({ title: "Source", summary: where + (source.path && where !== source.path ? ` · ${source.path}` : "") });
  const pinned = [source.ref, source.sha && source.sha.slice(0, 12)].filter(Boolean).join(" · ");
  if (pinned) rows.push({ title: "Pinned to", summary: pinned });
  return rows;
}

// Details: what the plugin is, where it comes from, what is inside, and how each client gets it.
// Its source, pinned version and commands wait under Technical details.
export function showOffer(offer, row) {
  const body = el("div", "body");
  if (offer.description) body.append(el("p", null, offer.description));
  const from = [];
  from.push(el("li", null, `Marketplace: ${offer.marketplace}`));
  if (offer.author) from.push(el("li", null, `By ${offer.author}`));
  const fromList = el("ul", "checklist");
  fromList.append(...from);
  const links = offer.homepage ? [webLink(offer.homepage, "Homepage ↗")] : [];
  body.append(section("Where it comes from", [fromList, ...links]), section("What's inside", inside(offer)));
  const clients = el("ul", "checklist");
  for (const client of INSTALLERS) {
    const word = offer.installed.includes(client) ? "Installed" : ROUTE_WORDS[offer.routes[client]] || "Cannot get it from this marketplace";
    clients.append(el("li", null, `${CLIENT_NAMES[client]}: ${word}`));
  }
  const cursor = cursorLine(offer, inherits(offer));
  if (cursor) clients.append(el("li", "muted", cursor));
  body.append(section("Clients", [clients]));
  const rows = [...sourceRows(offer), ...mcpRows(offer)];
  if (rows.length) body.append(technical(rows));
  openInfo("Plugin", rowTitle(row), body, addActions(row, offer, body));
}

// Details: what the skill is, where it comes from, the files it brings (scripts marked, because
// the agent may run them), and how each client loads it.
export function showSkill(skill, row) {
  const body = el("div", "body");
  if (skill.description) body.append(el("p", null, skill.description));
  if (!skill.self_contained) {
    body.append(el("p", "callout", `${NEEDS_PLUGIN} ${skill.needs.length ? `It ${skill.needs.join("; ")}.` : ""}`.trim()));
    if (skill.plugin) {
      const find = button("Find the plugin", () => {
        closePanel({ focus: false });
        go("library", { kind: "plugin", show: "all", category: "", attention: false, q: skill.plugin.split("@")[0], selected: null });
      }, "btn small");
      body.append(find);
    }
  }
  const from = el("ul", "checklist");
  from.append(el("li", null, skill.plugin ? `Plugin: ${skill.plugin}` : `In your skills: ${skill.from}`));
  body.append(section("Where it comes from", [from]), section("What it brings", brings(skill)));
  const clients = el("ul", "checklist");
  for (const client of columns()) {
    const word = skill.installed[client] || (skill.routes[client] ? "Can add" : skill.self_contained ? "Not set up" : "Needs its plugin");
    clients.append(el("li", null, `${CLIENT_NAMES[client]}: ${word}`));
  }
  // Its folder waits under Technical details, as in Details of an item on this computer.
  body.append(section("Clients", [clients]), technical([{ title: "Skill folder", path: skill.path }]));
  openInfo("Skill", rowTitle(row), body, addActions(row, skill, body));
}

// The files a skill brings, the scripts marked and counted first.
function brings(skill) {
  const files = el("ul", "checklist");
  for (const file of skill.files) {
    const li = el("li", "mono", file.path);
    if (file.script) li.append(el("span", "badge warn", "script"));
    files.append(li);
  }
  const scripts = skill.files.filter((f) => f.script).length;
  if (!scripts) return [files];
  return [el("p", "callout", `${plural(scripts, "script", "scripts")} the agent may run. Read them before you add the skill.`), files];
}

// What the item is, for Details of a row on this computer: the description, then what the
// plugin holds or the files the skill brings.
export function about(offer) {
  const out = offer.description ? [el("p", null, offer.description)] : [];
  out.push(offer.kind === "skill" ? section("What it brings", brings(offer)) : section("What's inside", inside(offer)));
  return out;
}

// Every way to add the row's item, as Details offer them: each cell's add ("+ Add" in the Codex
// column is "Add to Codex…"), the real install first, then "Add the plugin", then "Add skills",
// each in column order. Then "Add…" when two or more clients can take it as a plain add, to add
// to several in one review. "Add…" needs the marketplace's entry (`offer`).
export function addOptions(row, offer) {
  const plain = row.kind === "skill" ? "skill.install" : "plugin.install";
  const rank = (add) => (add.action === plain ? 0 : add.action === "plugin.skills" ? 2 : 1);
  const options = COLUMNS.filter((c) => row.cells[c] && row.cells[c].add).map((client) => {
    const add = row.cells[client].add;
    return { client, add, label: `${add.label.replace(/^\+ /, "")} to ${CLIENT_NAMES[client]}…` };
  });
  options.sort((a, b) => rank(a.add) - rank(b.add));
  if (offer && options.filter((o) => o.add.action === plain).length > 1) options.push({ form: true, label: "Add…" });
  return options;
}

// A cell's add does what the cell's own button does (its change goes to the tray, or it asks
// where first); "Add…" opens the form.
export function addButton(option, row, offer, look) {
  const node = option.form
    ? button(option.label, () => (row.kind === "skill" ? addSkillForm(offer) : addForm(offer, row)), look)
    : button(option.label, () => startAdd(option.add, option.client, row), look);
  // A redraw of these Details gives focus back here by this key (details.js backToDetails).
  node.dataset.focus = option.form ? "add:form" : `add:${option.client}`;
  return node;
}

// Why Details offer nothing to do, in one line: each cell's reason once, in column order, and
// clients whose reasons match after their name in one sentence ("Claude Code and Cursor can't
// install this plugin, …"); else where to change it, from the item's own settings; else "".
export function whyNoAction(row, definitions = []) {
  const reasons = new Map(); // what follows the client's name, or a whole reason -> the names
  for (const client of COLUMNS) {
    const reason = row.cells[client] && row.cells[client].reason;
    if (!reason) continue;
    const name = CLIENT_NAMES[client];
    const named = reason.startsWith(`${name} `);
    const key = named ? reason.slice(name.length) : reason;
    if (!reasons.has(key)) reasons.set(key, named ? [] : null);
    if (named) reasons.get(key).push(name);
  }
  if (reasons.size) {
    return [...reasons].map(([rest, names]) => {
      if (!names) return rest;
      // "Codex has it" for one client, "Codex and Cursor have it" for two.
      return joinWords(names) + (names.length > 1 ? rest.replace(/^ has /, " have ") : rest);
    }).join(" ");
  }
  const hint = definitions.find((d) => d.change_hint);
  return hint ? hint.change_hint : "";
}

// The footer of Details for a row not on this computer: every way to add it. With none, the
// body's first line says why.
function addActions(row, offer, body) {
  const options = addOptions(row, offer);
  const why = options.length ? "" : whyNoAction(row);
  if (why) body.prepend(el("p", "muted", why));
  return footerButtons(footerActions([], [], null, options), (option, look) => [addButton(option, row, offer, look)]);
}

// The clients that can take it now: the choices in its Add form.
function openFor(offer) {
  if (offer.kind === "skill") return columns().filter((c) => offer.routes[c]);
  return INSTALLERS.filter((c) => offer.routes[c] && !offer.installed.includes(c));
}

// A client starts checked only when it is the one choice; otherwise the developer picks.
export function startChosen(open) {
  return new Set(open.length === 1 ? open : []);
}

// The clients an add to `client` reaches, and why, as the Affects line in Details says it. A
// skill copy for Codex lands in .agents/skills, which Cursor reads whatever its third-party
// switch says; a copy for Claude Code reaches Cursor when Cursor reads Claude Code's folder.
// Cursor loads Claude Code's plugins of all projects only, so a plugin add that asks where it
// goes (`asks`) names Claude Code alone. `found`: the clients on this computer.
export function addReach(client, action, inherits, found, asks) {
  const cursor = client !== "cursor" && found.includes("cursor");
  let note = null;
  if (cursor && SKILL_COPIES.includes(action)) {
    if (client === "codex" || (client === "claude_code" && inherits.skill)) note = REACH_NOTES[client];
  } else if (cursor && action === "plugin.install" && client === "claude_code" && inherits.plugin && !asks) {
    note = REACH_NOTES.plugin;
  }
  return note ? { clients: [client, "cursor"], note } : { clients: [client], note: null };
}

// The line naming Cursor while it would load the change without being checked, or "": the
// same rule as addReach. `open` holds the clients the form offers; Cursor is one only when it
// is here and lacks the item. A checked Cursor is named already, so no line is needed then.
// `found`: the clients on this computer, all three before they are read (as columns()).
export function alsoLoads(kind, inherits, chosen, open = [], found = COLUMNS) {
  if (chosen.has("cursor")) return "";
  const reaches = (client, action) => chosen.has(client) && addReach(client, action, inherits, found, false).clients.includes("cursor");
  if (kind === "plugin") return reaches("claude_code", "plugin.install") ? ALSO_LOADS.plugin : "";
  if (reaches("claude_code", "skill.install")) return ALSO_LOADS.skill;
  return reaches("codex", "skill.install") && open.includes("cursor") ? ALSO_LOADS.shared : "";
}

// Checkboxes for the clients that can take it, checked as `chosen` says; `onChange` hears each.
export function clientChecks(open, chosen, note, onChange) {
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of open) {
    checks.append(clientCheck(client, chosen.has(client), note ? note(client) : null, (checked) => {
      if (checked) chosen.add(client); else chosen.delete(client);
      if (onChange) onChange();
    }));
  }
  return checks;
}

// The form: the clients, an optional note about them, then Preview and its message.
export function addFormBody(checks, chosen, onSubmit, note = null) {
  const form = el("form", "form");
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(...[checks, note, submit, message].filter(Boolean));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!chosen.size) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    busyWhile(submit, onSubmit()).catch(reportError);
  });
  return form;
}

// The Add form for both kinds: what it is, where it comes from, notes, the clients, Preview.
// Between the clients and Preview, a line names Cursor while it would load the change too.
function addPanel(kicker, offer, { source, notes, checkNote, preview }) {
  const open = openFor(offer);
  const chosen = startChosen(open);
  const body = el("div", "body");
  if (offer.description) body.append(el("p", null, offer.description));
  body.append(el("p", "muted", `Source: ${source}`), ...notes);
  // Always in the page, so a screen reader hears the line when it changes.
  const also = el("p", "also muted");
  also.setAttribute("aria-live", "polite");
  const showAlso = () => { also.textContent = alsoLoads(offer.kind, inherits(offer), chosen, open, columns()); };
  showAlso();
  body.append(addFormBody(clientChecks(open, chosen, checkNote, showAlso), chosen, () => preview([...chosen]), also));
  openPanel([panelHead(kicker, offer.name), body, el("footer")]);
}

// The Add form's review note: the warning of each checked client, as its cell's button passes
// it ("It will load both"), then the project line.
export function formNote(row, clients, project) {
  const warns = clients.map((client) => row.cells[client] && row.cells[client].add && row.cells[client].add.warn);
  return noteFor({ warn: warns.filter(Boolean).join(" ") }, project);
}

// Choose the clients, then the usual review: exactly what runs and what is written.
export function addForm(offer, row) {
  const notes = [];
  if (offer.inside && offer.inside.hooks.length) notes.push(el("p", "callout", `It brings hooks that run by themselves (${offer.inside.hooks.join(", ")}). Open Details to see them.`));
  addPanel("Add plugin", offer, {
    source: offer.marketplace,
    notes,
    checkNote: (client) => (offer.routes[client] === "add_marketplace" ? `adds ${offer.marketplace} first` : null),
    preview: (clients) => review(
      { action: "plugin.install", targets: clients.map((client) => ({ client })), params: { plugin: offer.id } },
      { note: formNote(row, clients, state.project) },
    ),
  });
}

// Choose the clients; the review then shows the fewest copies so each one loads the skill once.
export function addSkillForm(skill) {
  const notes = [];
  const scripts = skill.files.filter((f) => f.script).length;
  if (scripts) notes.push(el("p", "callout", `It brings ${plural(scripts, "script", "scripts")} the agent may run. Open Details to see them.`));
  notes.push(el("p", "muted", "The skill folder is copied, so it keeps working when the marketplace changes. Undo removes the copy while it is unchanged."));
  // A plugin's skill comes from the plugin; one already set up, from the clients that hold it.
  addPanel("Add skill", skill, {
    source: skill.from,
    notes,
    preview: (clients) => review(
      { action: "skill.install", targets: clients.map((client) => ({ client })), params: { skill: skill.id } },
      { note: projectNote(state.project) },
    ),
  });
}

// Add a marketplace from a folder here or a GitHub repository.
export function marketplaceForm() {
  const body = el("div", "body");
  const field = el("label", "field grow");
  const input = el("input");
  input.required = true;
  input.placeholder = "owner/repo, a github.com address, or a folder";
  input.autocomplete = "off";
  input.spellcheck = false;
  field.append(el("span", null, "Marketplace link"), input);
  const chosen = new Set(INSTALLERS);
  const form = addFormBody(clientChecks(INSTALLERS, chosen), chosen, () => review(
    { action: "marketplace.add", targets: [...chosen].map((client) => ({ client })), params: { source: input.value.trim() } },
    { note: projectNote(state.project) },
  ));
  form.prepend(field);
  body.append(el("p", "muted", "For a GitHub repository, Kitden reads its marketplace file once to name it. Cursor keeps its marketplaces in the Cursor account: add them in Cursor."), form);
  openPanel([panelHead("Add marketplace", "From a link"), body, el("footer")]);
  setTimeout(() => input.focus(), 0);
}

function panelHead(kicker, title) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kicker), button("Close", () => closePanel(), "btn ghost small"));
  const h1 = el("h1", "title-mono", title);
  h1.id = "panel-title";
  head.append(top, h1);
  return head;
}
