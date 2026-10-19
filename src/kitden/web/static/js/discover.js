// Discover: plugins in the marketplaces already on this computer, and one review to add them.
import { getJson, query } from "./api.js";
import { button, el, plural, webLink } from "./dom.js";
import { entrance, glide } from "./motion.js";
import { closePanel, openInfo, openPanel, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, mark, skeleton, socket } from "./parts.js";
import { data, freshness, render, state } from "./store.js";

// Clients whose own command line installs plugins. Cursor keeps its plugins in the account,
// and it loads Claude Code's plugins by itself when "Include Third-Party Plugins" is on.
const INSTALLERS = ["claude_code", "codex"];
const COLUMNS = ["claude_code", "codex", "cursor"];
const ROUTE_WORDS = { ready: "Ready", add_marketplace: "Adds the marketplace first" };
const CURSOR_NOTE = "Cursor loads Claude Code plugins when Include Third-Party Plugins is on.";

const SHOW = [["all", "All"], ["new", "Not added"], ["added", "Added"]];
const filters = { show: "all", category: "", marketplace: "" };

// The last answer, per search and filter; a rescan or a change makes it old.
// `asked` keeps the search and filters the answer is for, so the summary never mixes them.
let cache = { key: null, at: 0, answer: null, asked: null, error: null, loading: false };

function cacheKey() {
  return [filters.show, filters.category, filters.marketplace, state.q].join("|");
}

async function load() {
  const key = cacheKey();
  const asked = { ...filters, q: state.q };
  cache = { ...cache, key, loading: true };
  const params = {
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
  const filtered = asked.q || asked.show !== "all" || asked.category || asked.marketplace;
  if (!filtered) {
    const all = plural(answer.marketplaces.length, "marketplace", "marketplaces");
    return `${plural(answer.all, "plugin", "plugins")} in ${all} on this computer. Add one to Claude Code or Codex in one review.`;
  }
  const parts = [];
  if (asked.q) parts.push(`match “${asked.q}”`);
  if (asked.category) parts.push(`in ${asked.category}`);
  const among = plural(answer.facets.marketplaces.length, "marketplace", "marketplaces");
  parts.push(asked.marketplace ? `from ${asked.marketplace}` : `in ${among}`);
  const added = { new: "not added yet", added: "already added" }[asked.show];
  if (added) parts.push(added);
  return `${answer.total} of ${plural(answer.all, "plugin", "plugins")} ${parts.join(", ")}.`;
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

export function renderDiscover(main) {
  main.append(el("h1", null, "Discover"));
  const stale = cache.key !== cacheKey() || cache.at < freshness.reloadStartedAt;
  if (stale && !cache.loading) load();
  const answer = cache.answer;
  main.append(el("p", "lede", answer ? summary(answer, cache.asked) : "Plugins in the marketplaces on this computer."));
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
    tools.append(
      picker("Category", "All categories", "category", answer.facets.categories),
      picker("Marketplace", "All marketplaces", "marketplace", answer.facets.marketplaces),
    );
  }
  tools.append(el("span", "grow"), button("Add a marketplace…", () => marketplaceForm(), "btn small"));
  main.append(tools);
  glide(seg, seg.querySelector('[aria-pressed="true"]'), "discover-filter");
  if (cache.error && !answer) {
    main.append(banner("the plugins", async () => { cache.at = 0; render(); }));
    return;
  }
  if (!answer) {
    main.append(skeleton("card", 3));
    return;
  }
  if (!answer.offers.length) {
    const empty = el("div", "empty");
    const searching = state.q || filters.show !== "all" || filters.category || filters.marketplace;
    empty.append(el("strong", null, searching ? "Nothing here" : "No marketplaces yet"),
      el("span", null, searching ? "Try another word or filter, or add a marketplace." : "Add a marketplace from a link to see its plugins here."));
    main.append(empty);
    return;
  }
  const table = offerTable(answer.offers);
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

function offerTable(offers) {
  const clients = columns();
  const table = el("table", "map offers");
  const widths = el("colgroup");
  const share = `${(56 / clients.length).toFixed(1)}%`;
  for (const width of ["34%", ...clients.map(() => share), "10%"]) {
    const col = el("col");
    col.style.width = width;
    widths.append(col);
  }
  const head = el("tr");
  head.append(el("th", null, "Plugin"));
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
  const names = new Map();
  for (const offer of offers) names.set(offer.name, (names.get(offer.name) || 0) + 1);
  let apart = false;
  for (const offer of offers) {
    // Plugins found only by a word in their description come last, under their own line.
    if (offer.match === "text" && !apart) {
      apart = true;
      const tr = el("tr", "group");
      const td = el("td", null, `Also mention “${cache.asked.q}” in the description`);
      td.colSpan = clients.length + 2;
      tr.append(td);
      body.append(tr);
    }
    body.append(offerRow(offer, clients, names.get(offer.name) > 1));
  }
  table.append(widths, thead, body);
  return table;
}

// Where the plugin is, or how the client gets it: a filled dot is there, a ring can be added.
function cell(offer, client) {
  if (client === "cursor") {
    const viaClaude = offer.installed.includes("claude_code") || offer.routes.claude_code;
    const node = offer.installed.includes("cursor")
      ? socket({ state: "on", word: "Via Claude Code" })
      : viaClaude ? socket({ state: "off", word: "Via Claude Code" }) : socket({ state: "none" });
    node.title = viaClaude ? CURSOR_NOTE : "";
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

// One row: the name and what it does, one cell per client, and Add.
function offerRow(offer, clients, twin) {
  const tr = el("tr");
  tr.tabIndex = 0;
  tr.dataset.key = offer.id;
  tr.setAttribute("aria-selected", String(state.selected === offer.id));
  const nameCell = el("td");
  const top = el("div", "item");
  const name = el("span", "mono", offer.name);
  name.title = offer.id;
  top.append(name);
  if (offer.category) top.append(flag({ text: offer.category, level: "info" }));
  // Two marketplaces can offer a plugin with one name: then say which one this is.
  if (twin) top.append(el("span", "from", offer.marketplace));
  nameCell.append(top);
  if (offer.description) {
    const desc = el("div", "desc", offer.description);
    desc.title = offer.description;
    nameCell.append(desc);
  }
  tr.append(nameCell);
  for (const client of clients) {
    const td = el("td");
    td.append(cell(offer, client));
    tr.append(td);
  }
  const act = el("td", "act");
  const open = INSTALLERS.filter((c) => offer.routes[c] && !offer.installed.includes(c));
  if (open.length) {
    const add = button("Add…", (event) => { event.stopPropagation(); addForm(offer, open); }, "btn small");
    add.setAttribute("aria-label", `Add ${offer.name}`);
    act.append(add);
  }
  tr.append(act);
  const show = () => {
    for (const other of tr.parentElement.querySelectorAll('tr[aria-selected="true"]')) other.setAttribute("aria-selected", "false");
    tr.setAttribute("aria-selected", "true");
    state.selected = offer.id;
    showOffer(offer);
  };
  tr.addEventListener("click", show);
  tr.addEventListener("keydown", (event) => {
    if (event.target !== tr) return;
    if (event.key === "Enter") { event.preventDefault(); show(); }
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
  clients.append(el("li", "muted", "Cursor: loads Claude Code plugins when Include Third-Party Plugins is on."));
  body.append(section("Clients", [clients]));
  openInfo("Plugin", offer.name, body);
}

// Choose the clients, then the usual review: exactly what runs and what is written.
function addForm(offer, open) {
  const body = el("div", "body");
  const form = el("form", "form");
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  const chosen = new Set(open);
  for (const client of open) {
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.checked = true;
    box.addEventListener("change", () => { if (box.checked) chosen.add(client); else chosen.delete(client); });
    label.append(box, el("span", null, CLIENT_NAMES[client]));
    if (offer.routes[client] === "add_marketplace") label.append(el("span", "muted", ` · adds ${offer.marketplace} first`));
    checks.append(label);
  }
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(checks, submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!chosen.size) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    review({ action: "plugin.install", targets: [...chosen].map((client) => ({ client })), params: { plugin: offer.id } });
  });
  if (offer.inside && offer.inside.hooks.length) body.append(el("p", "callout", `It brings hooks that run by themselves (${offer.inside.hooks.join(", ")}). Open Details to see them.`));
  body.append(form);
  openPanel([panelHead("Add plugin", offer.name), body, el("footer")]);
}

// Add a marketplace from a folder here or a GitHub repository.
function marketplaceForm() {
  const body = el("div", "body");
  const form = el("form", "form");
  const field = el("label", "field grow");
  const input = el("input");
  input.required = true;
  input.placeholder = "owner/repo, a github.com address, or a folder";
  input.autocomplete = "off";
  input.spellcheck = false;
  field.append(el("span", null, "Marketplace link"), input);
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  const chosen = new Set(INSTALLERS);
  for (const client of INSTALLERS) {
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.checked = true;
    box.addEventListener("change", () => { if (box.checked) chosen.add(client); else chosen.delete(client); });
    label.append(box, el("span", null, CLIENT_NAMES[client]));
    checks.append(label);
  }
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  form.append(field, checks, submit, message);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!chosen.size) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    review({ action: "marketplace.add", targets: [...chosen].map((client) => ({ client })), params: { source: input.value.trim() } });
  });
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
