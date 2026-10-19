// Discover: plugins in the marketplaces already on this computer, the skills inside them and
// in the clients' own skill folders, and one review to add any of them.
import { getJson, query } from "./api.js";
import { button, el, plural, shortPath, webLink } from "./dom.js";
import { entrance, glide } from "./motion.js";
import { closePanel, openInfo, openPanel, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, mark, skeleton, socket } from "./parts.js";
import { data, freshness, go, render, state } from "./store.js";

// Clients whose own command line installs plugins. Cursor keeps its plugins in the account,
// and it loads Claude Code's plugins by itself when "Include Third-Party Plugins" is on.
const INSTALLERS = ["claude_code", "codex"];
const COLUMNS = ["claude_code", "codex", "cursor"];
const ROUTE_WORDS = { ready: "Ready", add_marketplace: "Adds the marketplace first" };
const CURSOR_NOTE = "Cursor loads Claude Code plugins when Include Third-Party Plugins is on.";
const NEEDS_PLUGIN = "This skill needs the rest of its plugin. Add the plugin instead.";
// What Cursor also loads, per way in; the server reads Cursor's switches. A Codex copy goes to
// ~/.agents/skills, which Cursor always reads (checked against Cursor's docs, 2026-10-19).
const ALSO_LOADS = {
  plugin: "Cursor will also load this through Claude Code.",
  skill: "Cursor will also load it from Claude Code's folder.",
  shared: "Cursor will also load it from the shared skills folder.",
};

const KINDS = [["plugin", "Plugins"], ["skill", "Skills"]];
const SHOW = [["all", "All"], ["new", "Not added"], ["added", "Added"]];
const filters = { show: "all", category: "", marketplace: "" };

// Plugins or skills: the Load map's kind word, read from the address.
const kind = () => (state.kind === "skill" ? "skill" : "plugin");

// The last answer, per kind, search and filter; a rescan or a change makes it old.
// `asked` keeps the search and filters the answer is for, so the summary never mixes them.
let cache = { key: null, at: 0, answer: null, asked: null, error: null, loading: false };

function cacheKey() {
  return [kind(), filters.show, filters.category, filters.marketplace, state.q].join("|");
}

// Whether Cursor loads Claude Code's plugins and the skills in its folder, from the last answer.
function cursorInherits() {
  return (cache.answer && cache.answer.inherits) || { plugin: false, skill: false };
}

async function load() {
  const key = cacheKey();
  const asked = { ...filters, kind: kind(), q: state.q };
  cache = { ...cache, key, loading: true };
  const params = {
    kind: kind() === "skill" ? "skill" : "",
    q: state.q,
    only: filters.show === "all" ? "" : filters.show,
    category: filters.category,
    marketplace: filters.marketplace,
  };
  try {
    const answer = await getJson(`/api/catalog${query(params)}`);
    if (cache.key !== key) return; // a newer search won
    cache = { key, at: performance.now(), answer, asked, error: null, loading: false };
  } catch (error) {
    if (cache.key !== key) return;
    cache = { ...cache, error, loading: false };
  }
  if (state.view === "discover") render();
}

// "386 plugins in 5 marketplaces", or "10 of 386 plugins match “git”, in Design" with filters.
function summary(answer, asked) {
  const skills = asked.kind === "skill";
  const things = skills ? ["skill", "skills"] : ["plugin", "plugins"];
  const filtered = asked.q || asked.show !== "all" || asked.category || asked.marketplace;
  if (!filtered) {
    if (skills) return `${plural(answer.all, ...things)} in the plugins on this computer and in your skill folders. Add one to Claude Code, Codex or Cursor in one review.`;
    const all = plural(answer.marketplaces.length, "marketplace", "marketplaces");
    return `${plural(answer.all, ...things)} in ${all} on this computer. Add one to Claude Code or Codex in one review.`;
  }
  const parts = [];
  if (asked.q) parts.push(`match “${asked.q}”`);
  if (asked.category) parts.push(`in ${asked.category}`);
  if (asked.marketplace) parts.push(`from ${asked.marketplace}`);
  else if (!skills) parts.push(`in ${plural(answer.facets.marketplaces.length, "marketplace", "marketplaces")}`);
  const added = { new: "not added yet", added: "already added" }[asked.show];
  if (added) parts.push(added);
  return `${answer.total} of ${plural(answer.all, ...things)} ${parts.join(", ")}.`;
}

// A menu of the categories or marketplaces in the results, each with its count.
function picker(label, all, key, facets) {
  const select = el("select");
  select.setAttribute("aria-label", label);
  select.append(new Option(all, ""));
  const chosen = filters[key];
  const options = facets.some((f) => f.name === chosen) || !chosen ? facets : [{ name: chosen, count: 0 }, ...facets];
  for (const facet of options) select.append(new Option(`${facet.name} (${facet.count})`, facet.name));
  select.value = chosen;
  select.addEventListener("change", () => { filters[key] = select.value; render(); });
  const box = el("label", "filter");
  if (chosen) box.classList.add("on");
  box.append(select);
  return box;
}

function kindTabs() {
  const box = el("div", "tabs");
  box.setAttribute("role", "tablist");
  for (const [id, label] of KINDS) {
    const tab = button(label, () => go("discover", { kind: id, selected: null }), "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(kind() === id));
    box.append(tab);
  }
  return box;
}

export function renderDiscover(main) {
  main.append(el("h1", null, "Discover"));
  const stale = cache.key !== cacheKey() || cache.at < freshness.reloadStartedAt;
  if (stale && !cache.loading) load();
  const skills = kind() === "skill";
  // An answer for the other kind has rows of another shape: wait for the new one instead.
  const answer = cache.answer && cache.asked.kind === kind() ? cache.answer : null;
  const waiting = skills ? "Skills in the plugins on this computer and in your skill folders." : "Plugins in the marketplaces on this computer.";
  main.append(el("p", "lede", answer ? summary(answer, cache.asked) : waiting));
  const tabBox = kindTabs();
  main.append(tabBox);
  glide(tabBox, tabBox.querySelector('[aria-selected="true"]'), "discover-kind");
  const tools = el("div", "toolbar");
  const seg = el("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Show");
  for (const [id, label] of SHOW) {
    const b = button(label, () => { filters.show = id; render(); }, "");
    b.setAttribute("aria-pressed", String(filters.show === id));
    seg.append(b);
  }
  tools.append(seg);
  if (answer && answer.facets) {
    // Skills have no category, so that menu only shows when there is something to pick.
    if (answer.facets.categories.length || filters.category) tools.append(picker("Category", "All categories", "category", answer.facets.categories));
    tools.append(picker("Marketplace", "All marketplaces", "marketplace", answer.facets.marketplaces));
  }
  tools.append(el("span", "grow"), button("Add a marketplace…", () => marketplaceForm(), "btn small"));
  main.append(tools);
  glide(seg, seg.querySelector('[aria-pressed="true"]'), "discover-filter");
  if (cache.error && !answer) {
    main.append(banner(skills ? "the skills" : "the plugins", async () => { cache.at = 0; render(); }));
    return;
  }
  if (!answer) {
    main.append(skeleton("card", 3));
    return;
  }
  if (!answer.offers.length) {
    const empty = el("div", "empty");
    const searching = state.q || filters.show !== "all" || filters.category || filters.marketplace;
    const nothing = skills ? "No skills yet" : "No marketplaces yet";
    const hint = skills ? "Add a marketplace from a link to see its plugins' skills here." : "Add a marketplace from a link to see its plugins here.";
    empty.append(el("strong", null, searching ? "Nothing here" : nothing),
      el("span", null, searching ? "Try another word or filter, or add a marketplace." : hint));
    main.append(empty);
    return;
  }
  const table = offerTable(answer.offers, skills);
  const scroller = el("div", "table-scroll");
  scroller.append(table);
  main.append(scroller);
  if (answer.total > answer.offers.length) {
    main.append(el("p", "group-note", `Showing ${answer.offers.length} of ${answer.total}. Search to narrow it down.`));
  }
  entrance("discover", [tools, table]);
}

// The clients this computer has, in the Load map's order; all three before they are read.
function columns() {
  const found = (data.clients || []).filter((c) => c.status === "found").map((c) => c.id);
  const shown = COLUMNS.filter((c) => !data.clients || found.includes(c));
  return shown.length ? shown : COLUMNS;
}

function offerTable(offers, skills) {
  const clients = columns();
  const table = el("table", "map offers");
  const widths = el("colgroup");
  const share = `${(48 / clients.length).toFixed(1)}%`;
  for (const width of ["42%", ...clients.map(() => share), "10%"]) {
    const col = el("col");
    col.style.width = width;
    widths.append(col);
  }
  const head = el("tr");
  head.append(el("th", null, skills ? "Skill" : "Plugin"));
  for (const client of clients) {
    const th = el("th");
    const chip = el("span", "chip");
    chip.append(mark(client), el("span", null, CLIENT_NAMES[client]));
    th.append(chip);
    head.append(th);
  }
  const action = el("th");
  action.setAttribute("aria-label", "Add");
  head.append(action);
  const thead = el("thead");
  thead.append(head);
  const body = el("tbody");
  let apart = false;
  for (const offer of offers) {
    // Items found only by a word in their description come last, under their own line.
    if (offer.match === "text" && !apart) {
      apart = true;
      const tr = el("tr", "group");
      const td = el("td", null, `Also mention “${cache.asked.q}” in the description`);
      td.colSpan = clients.length + 2;
      tr.append(td);
      body.append(tr);
    }
    body.append(skills ? skillRow(offer, clients) : offerRow(offer, clients));
  }
  table.append(widths, thead, body);
  return table;
}

// How Cursor gets a plugin: only through Claude Code, and only when it imports Claude Code's
// plugins. "on" it loads it, "off" it will once Claude Code has it, "none" it cannot.
export function cursorPlugin(offer, inherits) {
  if (offer.installed.includes("cursor")) return "on";
  const viaClaude = offer.installed.includes("claude_code") || offer.routes.claude_code;
  return inherits.plugin && viaClaude ? "off" : "none";
}

// Where the plugin is, or how the client gets it: a filled dot is there, a ring can be added.
function cell(offer, client) {
  if (client === "cursor") {
    const how = cursorPlugin(offer, cursorInherits());
    const node = socket({ state: how, word: "Via Claude Code" });
    node.title = how === "none" ? "" : CURSOR_NOTE;
    return node;
  }
  if (offer.installed.includes(client)) return socket({ state: "on", word: "Installed" });
  const route = offer.routes[client];
  if (!route) {
    const none = socket({ state: "none" });
    none.setAttribute("aria-label", "Cannot add from this marketplace");
    return none;
  }
  const node = socket({ state: "off", word: "Can add", where: route === "add_marketplace" ? "+ marketplace" : null });
  if (route === "add_marketplace") node.title = `Adds the ${offer.marketplace} marketplace first`;
  return node;
}

// How the client loads the skill now ("Installed", "Via plugin", "Via Claude Code"), or that
// it can take a copy.
function skillCell(skill, client) {
  const word = skill.installed[client];
  if (word) return socket({ state: "on", word });
  if (skill.routes[client]) return socket({ state: "off", word: "Can add" });
  const none = socket({ state: "none" });
  none.setAttribute("aria-label", skill.self_contained ? "Not set up" : "Needs its plugin");
  return none;
}

// One row with the shared behaviour: a click or Enter opens Details, arrows move between rows.
function tableRow(key, show) {
  const tr = el("tr");
  tr.tabIndex = 0;
  tr.dataset.key = key;
  tr.setAttribute("aria-selected", String(state.selected === key));
  const select = () => {
    for (const other of tr.parentElement.querySelectorAll('tr[aria-selected="true"]')) other.setAttribute("aria-selected", "false");
    tr.setAttribute("aria-selected", "true");
    state.selected = key;
    show();
  };
  tr.addEventListener("click", select);
  tr.addEventListener("keydown", (event) => {
    if (event.target !== tr) return;
    if (event.key === "Enter") { event.preventDefault(); select(); }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? "nextElementSibling" : "previousElementSibling";
      let next = tr[step];
      while (next && !next.dataset.key) next = next[step]; // skip the group line
      if (next) next.focus();
    }
  });
  return tr;
}

// The first cell of a row. Line one: the name, which stays one line, and a flag. Line two: where
// it comes from, never cut, then what it does, on up to two lines.
function itemCell(item, flagged, from, fromTitle) {
  const cell = el("td");
  const top = el("div", "item");
  const name = el("span", "mono", item.name);
  name.title = item.id;
  top.append(name);
  if (flagged) top.append(flagged);
  cell.append(top);
  const meta = el("div", "meta");
  if (from) {
    const source = el("span", "from", from);
    if (fromTitle) source.title = fromTitle;
    meta.append(source);
  }
  if (item.description) {
    const desc = el("span", "desc", item.description);
    desc.title = item.description;
    meta.append(desc);
  }
  if (meta.children.length) cell.append(meta);
  return cell;
}

// One row: the name, the marketplace and what it does, one cell per client, and Add.
function offerRow(offer, clients) {
  const tr = tableRow(offer.id, () => showOffer(offer));
  tr.append(itemCell(offer, offer.category ? flag({ text: offer.category, level: "info" }) : null, offer.marketplace));
  for (const client of clients) {
    const td = el("td");
    td.append(cell(offer, client));
    tr.append(td);
  }
  const act = el("td", "act");
  if (openFor(offer).length) {
    const add = button("Add…", (event) => { event.stopPropagation(); addForm(offer); }, "btn small");
    add.setAttribute("aria-label", `Add ${offer.name}`);
    act.append(add);
  }
  tr.append(act);
  return tr;
}

// One skill: the name, where it comes from and what it does, one cell per client, and Add.
function skillRow(skill, clients) {
  const tr = tableRow(skill.id, () => showSkill(skill));
  // The plugin's short name; the marketplace is in the filter and in Details.
  const from = skill.plugin ? skill.plugin.split("@")[0] : skill.from;
  tr.append(itemCell(skill, skill.self_contained ? null : flag({ text: "Needs its plugin", level: "warning" }), from, skill.from));
  for (const client of clients) {
    const td = el("td");
    td.append(skillCell(skill, client));
    tr.append(td);
  }
  const act = el("td", "act");
  if (openFor(skill).length) {
    const add = button("Add…", (event) => { event.stopPropagation(); addSkillForm(skill); }, "btn small");
    add.setAttribute("aria-label", `Add ${skill.name}`);
    act.append(add);
  }
  tr.append(act);
  return tr;
}

function section(title, children) {
  const box = el("section");
  box.append(el("h2", null, title), ...children);
  return box;
}

function inside(offer) {
  const got = offer.inside;
  if (!got) return [el("p", "muted", "What it holds is read once the client downloads it.")];
  const lines = [];
  const add = (label, names) => { if (names.length) lines.push(el("li", null, `${label}: ${names.join(", ")}`)); };
  add("Skills", got.skills);
  add("Commands", got.commands);
  add("Agents", got.agents);
  const out = [];
  if (got.hooks.length) {
    out.push(el("p", "callout", `Runs by itself on: ${got.hooks.join(", ")}. Hooks run commands without asking each time.`));
  }
  for (const server of got.mcp_servers) lines.push(el("li", "mono", `MCP ${server.name}: ${server.runs}`));
  const list = el("ul", "checklist");
  list.append(...lines);
  if (lines.length) out.push(list);
  if (!out.length) out.push(el("p", "muted", "Nothing that runs by itself."));
  return out;
}

// Details: what the plugin is, where it comes from, what is inside, and how each client gets it.
function showOffer(offer) {
  const body = el("div", "body");
  if (offer.description) body.append(el("p", null, offer.description));
  const from = [];
  const source = offer.source || {};
  const where = source.repo || source.url || source.path;
  from.push(el("li", null, `Marketplace: ${offer.marketplace}`));
  if (offer.author) from.push(el("li", null, `By ${offer.author}`));
  if (where) from.push(el("li", "mono", where + (source.path && where !== source.path ? ` · ${source.path}` : "")));
  if (source.sha || source.ref) from.push(el("li", "mono", `Pinned to ${source.ref || ""}${source.ref && source.sha ? " · " : ""}${source.sha ? source.sha.slice(0, 12) : ""}`));
  const fromList = el("ul", "checklist");
  fromList.append(...from);
  const links = offer.homepage ? [webLink(offer.homepage, "Homepage ↗")] : [];
  body.append(section("Where it comes from", [fromList, ...links]), section("What's inside", inside(offer)));
  const clients = el("ul", "checklist");
  for (const client of INSTALLERS) {
    const state = offer.installed.includes(client) ? "Installed" : ROUTE_WORDS[offer.routes[client]] || "Cannot get it from this marketplace";
    clients.append(el("li", null, `${CLIENT_NAMES[client]}: ${state}`));
  }
  // Only when the server says Cursor loads Claude Code's plugins, and Claude Code can have this one.
  if (cursorPlugin(offer, cursorInherits()) !== "none") clients.append(el("li", "muted", "Cursor: loads it through Claude Code."));
  body.append(section("Clients", [clients]));
  const add = openFor(offer).length ? [button("Add…", () => addForm(offer), "btn primary")] : [];
  openInfo("Plugin", offer.name, body, add);
}

// Details: what the skill is, where it comes from, the files it brings (scripts marked, because
// the agent may run them), and how each client loads it.
function showSkill(skill) {
  const body = el("div", "body");
  if (skill.description) body.append(el("p", null, skill.description));
  if (!skill.self_contained) {
    body.append(el("p", "callout", `${NEEDS_PLUGIN} ${skill.needs.length ? `It ${skill.needs.join("; ")}.` : ""}`.trim()));
    if (skill.plugin) {
      const find = button("Find the plugin", () => {
        closePanel({ focus: false });
        go("discover", { kind: "plugin", q: skill.plugin.split("@")[0], selected: null });
      }, "btn small");
      body.append(find);
    }
  }
  const from = el("ul", "checklist");
  from.append(el("li", null, skill.plugin ? `Plugin: ${skill.plugin}` : `In your skills: ${skill.from}`));
  const path = el("li", "mono", shortPath(skill.path));
  path.title = skill.path;
  from.append(path);
  body.append(section("Where it comes from", [from]));
  const files = el("ul", "checklist");
  for (const file of skill.files) {
    const li = el("li", "mono", file.path);
    if (file.script) li.append(el("span", "badge warn", "script"));
    files.append(li);
  }
  const brings = [files];
  const scripts = skill.files.filter((f) => f.script).length;
  if (scripts) brings.unshift(el("p", "callout", `${plural(scripts, "script", "scripts")} the agent may run. Read them before you add the skill.`));
  body.append(section("What it brings", brings));
  const clients = el("ul", "checklist");
  for (const client of columns()) {
    const word = skill.installed[client] || (skill.routes[client] ? "Can add" : skill.self_contained ? "Not set up" : "Needs its plugin");
    clients.append(el("li", null, `${CLIENT_NAMES[client]}: ${word}`));
  }
  body.append(section("Clients", [clients]));
  const add = openFor(skill).length ? [button("Add…", () => addSkillForm(skill), "btn primary")] : [];
  openInfo("Skill", skill.name, body, add);
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

// The line naming Cursor while it would load the change without being checked, or "".
// `open` holds the clients the form offers; Cursor is one only when it is here and lacks the item.
// A checked Cursor is named already, so the skill lines are not needed then.
export function alsoLoads(kind, inherits, chosen, open = []) {
  if (kind === "plugin") return inherits.plugin && chosen.has("claude_code") ? ALSO_LOADS.plugin : "";
  if (chosen.has("cursor")) return "";
  if (inherits.skill && chosen.has("claude_code")) return ALSO_LOADS.skill;
  // A Codex copy lands in ~/.agents/skills, which Cursor reads whatever its third-party switch says.
  return chosen.has("codex") && open.includes("cursor") ? ALSO_LOADS.shared : "";
}

// Checkboxes for the clients that can take it, checked as `chosen` says; `onChange` hears each.
function clientChecks(open, chosen, note, onChange) {
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of open) {
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.checked = chosen.has(client);
    box.addEventListener("change", () => {
      if (box.checked) chosen.add(client); else chosen.delete(client);
      if (onChange) onChange();
    });
    label.append(box, el("span", null, CLIENT_NAMES[client]));
    const extra = note ? note(client) : null;
    if (extra) label.append(el("span", "muted", ` · ${extra}`));
    checks.append(label);
  }
  return checks;
}

// The form: the clients, an optional note about them, then Preview and its message.
function addFormBody(checks, chosen, onSubmit, note = null) {
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
    onSubmit();
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
  const showAlso = () => { also.textContent = alsoLoads(offer.kind, cursorInherits(), chosen, open); };
  showAlso();
  body.append(addFormBody(clientChecks(open, chosen, checkNote, showAlso), chosen, () => preview([...chosen]), also));
  openPanel([panelHead(kicker, offer.name), body, el("footer")]);
}

// Choose the clients, then the usual review: exactly what runs and what is written.
function addForm(offer) {
  const notes = [];
  if (offer.inside && offer.inside.hooks.length) notes.push(el("p", "callout", `It brings hooks that run by themselves (${offer.inside.hooks.join(", ")}). Open Details to see them.`));
  addPanel("Add plugin", offer, {
    source: offer.marketplace,
    notes,
    checkNote: (client) => (offer.routes[client] === "add_marketplace" ? `adds ${offer.marketplace} first` : null),
    preview: (clients) => review({ action: "plugin.install", targets: clients.map((client) => ({ client })), params: { plugin: offer.id } }),
  });
}

// Choose the clients; the review then shows the fewest copies so each one loads the skill once.
function addSkillForm(skill) {
  const notes = [];
  const scripts = skill.files.filter((f) => f.script).length;
  if (scripts) notes.push(el("p", "callout", `It brings ${plural(scripts, "script", "scripts")} the agent may run. Open Details to see them.`));
  notes.push(el("p", "muted", "The skill folder is copied, so it keeps working when the marketplace changes. Undo removes the copy while it is unchanged."));
  // A plugin's skill comes from the plugin; one already set up, from the clients that hold it.
  addPanel("Add skill", skill, {
    source: skill.from,
    notes,
    preview: (clients) => review({ action: "skill.install", targets: clients.map((client) => ({ client })), params: { skill: skill.id } }),
  });
}

// Add a marketplace from a folder here or a GitHub repository.
function marketplaceForm() {
  const body = el("div", "body");
  const field = el("label", "field grow");
  const input = el("input");
  input.required = true;
  input.placeholder = "owner/repo, a github.com address, or a folder";
  input.autocomplete = "off";
  input.spellcheck = false;
  field.append(el("span", null, "Marketplace link"), input);
  const chosen = new Set(INSTALLERS);
  const form = addFormBody(clientChecks(INSTALLERS, chosen), chosen, () => {
    review({ action: "marketplace.add", targets: [...chosen].map((client) => ({ client })), params: { source: input.value.trim() } });
  });
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
