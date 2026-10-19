// Discover: plugins in the marketplaces already on this computer, and one review to add them.
import { getJson, query } from "./api.js";
import { button, el, plural, webLink } from "./dom.js";
import { entrance } from "./motion.js";
import { closePanel, openInfo, openPanel, review } from "./panel.js";
import { banner, CLIENT_NAMES, flag, mark, skeleton } from "./parts.js";
import { freshness, render, state } from "./store.js";

// Clients whose own command line installs plugins. Cursor keeps its plugins in the account,
// and it loads Claude Code's plugins by itself when "Include Third-Party Plugins" is on.
const INSTALLERS = ["claude_code", "codex"];
const ROUTE_WORDS = { ready: "Ready", add_marketplace: "Adds the marketplace first" };

// The last answer, per search; a rescan or a change makes it old.
let cache = { q: null, at: 0, answer: null, error: null, loading: false };

async function load(q) {
  cache = { ...cache, q, loading: true };
  try {
    const answer = await getJson(`/api/catalog${query({ q })}`);
    if (cache.q !== q) return; // a newer search won
    cache = { q, at: performance.now(), answer, error: null, loading: false };
  } catch (error) {
    if (cache.q !== q) return;
    cache = { ...cache, error, loading: false };
  }
  if (state.view === "discover") render();
}

export function renderDiscover(main) {
  main.append(el("h1", null, "Discover"));
  const stale = cache.q !== state.q || cache.at < freshness.reloadStartedAt;
  if (stale && !cache.loading) load(state.q);
  const answer = cache.answer;
  const lede = el("p", "lede", answer
    ? `${plural(answer.marketplaces.reduce((n, m) => n + m.count, 0), "plugin", "plugins")} in ${plural(answer.marketplaces.length, "marketplace", "marketplaces")} on this computer. Add one to Claude Code or Codex in one review.`
    : "Plugins in the marketplaces on this computer.");
  main.append(lede);
  const tools = el("div", "toolbar");
  tools.append(button("Add a marketplace…", () => marketplaceForm(), "btn small"));
  main.append(tools);
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
    empty.append(el("strong", null, state.q ? `Nothing matches “${state.q}”` : "No marketplaces yet"),
      el("span", null, state.q ? "Try another word, or add a marketplace." : "Add a marketplace from a link to see its plugins here."));
    main.append(empty);
    return;
  }
  const list = el("div", "list");
  for (const offer of answer.offers) list.append(offerRow(offer));
  main.append(list);
  if (answer.total > answer.offers.length) {
    main.append(el("p", "group-note", `Showing ${answer.offers.length} of ${answer.total}. Search to narrow it down.`));
  }
  entrance("discover", [tools, list]);
}

// One row: the plugin's name, where it is installed, and Add.
function offerRow(offer) {
  const node = el("div", "list-row");
  const marks = el("span", "chip");
  for (const client of offer.installed) marks.append(mark(client));
  marks.setAttribute("aria-label", offer.installed.length ? `Installed in ${offer.installed.map((c) => CLIENT_NAMES[c] || c).join(", ")}` : "Not installed");
  const what = el("span", "what");
  const name = el("span", "mono", offer.name);
  name.title = offer.id;
  what.append(name);
  if (offer.category) what.append(flag({ text: offer.category, level: "info" }));
  const actions = el("span", "row-actions");
  actions.append(button("Details", () => showOffer(offer), "btn small ghost"));
  const open = INSTALLERS.filter((c) => offer.routes[c] && !offer.installed.includes(c));
  if (open.length) actions.append(button("Add…", () => addForm(offer, open), "btn small"));
  else actions.append(el("span", "muted", offer.installed.length ? "Added" : "Not for these clients"));
  node.append(marks, what, actions);
  return node;
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
