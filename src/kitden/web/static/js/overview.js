// Overview: what needs attention first, then the clients and, without a gateway, how to get one.
import { getJson, query } from "./api.js";
import { button, el, focusKey, plural } from "./dom.js";
import { SETUP_NOTE } from "./gateway.js";
import { loadLibraryFor, noClients } from "./library.js";
import { entrance, fly } from "./motion.js";
import { review, toast } from "./panel.js";
import { banner, CLIENT_NAMES, flag, kitdenClients, mark, skeleton, socket, STATE_WORDS, staleNote, versionWords } from "./parts.js";
import { current, currentError, data, go, goTo, libraryChoice, loadMap, projectPath, render, retry } from "./store.js";

let notesOpen = false;

export function renderOverview(main) {
  const model = current("overview");
  if (!model) {
    main.append(el("h1", null, "Overview"));
    if (currentError("overview")) main.append(banner("the overview", retry));
    else main.append(skeleton("card", 3));
    return;
  }

  const { none, headline, lede } = overviewHead(model, data.clients, (data.projects || []).length);
  main.append(el("h1", null, headline));
  if (lede) main.append(el("p", "lede", lede));
  if (currentError("overview")) main.append(staleNote(data.readAt.overview));

  const grid = el("div", "overview");
  const column = el("div", "attention");
  const left = el("section", "attention");
  left.setAttribute("aria-label", "Needs attention");
  const blocks = [];
  // No client found: what Kitden looks for comes first, in place of the all-clear line.
  if (none) {
    const box = noClients({ overview: false });
    left.append(box);
    blocks.push(box);
  }
  for (const card of model.attention) {
    const article = issueCard(card);
    left.append(article);
    blocks.push(article);
  }
  if (!model.attention.length && !none) {
    const clear = el("div", "all-clear", allClearWords(data.clients || []));
    left.append(clear);
    blocks.push(clear);
  }
  column.append(left);
  // Options, not problems: the same cards without the warning colour.
  if (model.suggestions.length) {
    const options = el("section", "attention");
    const title = el("h2", "section-title", "Can improve");
    options.append(title);
    blocks.push(title);
    for (const card of model.suggestions) {
      const article = issueCard(card, { option: true });
      options.append(article);
      blocks.push(article);
    }
    column.append(options);
  }
  if (model.notes) column.append(notesBlock(model.notes));
  grid.append(column);

  const side = el("div", "side");
  side.append(clientsCard(model.clients));
  // A registered gateway has no card: the Can improve card is the one place that mentions it.
  if (!model.gateway || model.gateway.kind === "kitden") side.append(gatewayCard(model.gateway));
  grid.append(side);
  main.append(grid);
  entrance("overview", [...blocks, ...side.children]);
}

// The page's title and lede. With no client found (once the clients are read) the title says
// so and there is no lede: "nothing needs your attention" would promise too much, and the
// counts would say the title again. The box below says what Kitden looks for.
export function overviewHead(model, clients, projects) {
  const none = Array.isArray(clients) && !clients.some((c) => c.status === "found");
  if (none) return { none, headline: "No clients found", lede: null };
  const found = (clients || []).filter((c) => c.status === "found").length;
  const counts = `${plural(found, "client", "clients")} found, ${plural(projects, "project", "projects")}`;
  const lede = model.attention.length ? `Everything else looks fine: ${counts}.` : `${counts}. Nothing needs your attention.`;
  return { none, headline: model.headline, lede };
}

// "No untested versions" only once every found client has a version; while one is still being
// checked, or cannot be read, the page says less.
export function allClearWords(clients) {
  const unknown = clients.some((c) => c.status === "found" && !c.version);
  return unknown ? "No duplicates, no unreadable files." : "No duplicates, no unreadable files, no untested versions.";
}

// One card per problem or option: a short title, one sentence, one button that names the action.
// An option is quieter than a problem: no warning border, a plain button.
function issueCard(card, { option = false } = {}) {
  const article = el("article", option ? "issue suggestion" : "issue");
  article.append(el("h3", null, card.title), el("p", null, card.text));
  if (card.action && card.target) article.append(button(card.action, () => follow(card.target), option ? "btn" : "btn primary"));
  return article;
}

// The item a card is about, for the address: its kind and name. Null for a card about a place.
// The server still names the Load map ("map"); its rows are the Library's "Installed".
export function targetSel(target) {
  return target.view === "map" ? { kind: target.kind, name: target.name } : null;
}

// A card about an item selects it and opens it in the Library's side panel; paths and the fix
// live there. The tab is read first, so the Library draws its rows inside the place change.
async function follow(target) {
  const sel = targetSel(target);
  if (sel) {
    await loadLibraryFor(libraryChoice(sel));
    goTo("library", sel);
  } else {
    go(target.view);
  }
}

// A note in short words; the full explanation, with its paths, is in the item's panel.
const NOTE_WORDS = {
  cross_loaded: "Loaded from another client",
  same_in_other_clients: "Set up in more than one client",
  same_name_other_source: "Same name, another source",
  scope_override: "One definition replaces another",
  unknown_state: "On/off state not readable",
  bypasses_gateway: "Not connected to the gateway",
};

function notesBlock(count) {
  const box = el("div");
  const toggle = button(notesOpen ? "Hide notes" : `Show ${plural(count, "note", "notes")} (nothing to fix)`, async () => {
    notesOpen = !notesOpen;
    render();
  }, "btn ghost small notes-toggle");
  box.append(toggle);
  if (notesOpen) {
    const list = el("div", "list notes");
    list.append(el("p", "muted", "Loading…"));
    box.append(list);
    getJson(`/api/findings${query({ project: projectPath() })}`).then((findings) => {
      list.replaceChildren();
      for (const group of noteGroups(findings.filter((x) => x.severity === "info"))) list.append(noteRow(group));
    }).catch(() => { list.replaceChildren(el("p", "muted", "Could not load the notes.")); });
  }
  return box;
}

// A found client opens to what it loads, counted from the load map data; each count opens the Library.
const LOAD_KINDS = [
  ["mcp_server", "MCP server", "MCP servers"], ["plugin", "plugin", "plugins"],
  ["skill", "skill", "skills"], ["hook", "hook", "hooks"],
  ["instructions", "instruction file", "instruction files"],
];

// [kind, count, words] for each kind the client loads or has here; empty when it has nothing.
// An item that needs review loads too: only its source is in question.
export function loadCounts(rows, clientId) {
  return LOAD_KINDS.map(([kind, one, many]) => {
    const n = rows.filter((r) => r.kind === kind && ["on", "review", "gw"].includes(r.cells[clientId] && r.cells[clientId].state)).length;
    return [kind, n, plural(n, one, many)];
  }).filter(([, n]) => n);
}
const openClients = new Set();

// A count opens that Library tab; the client's tile flies to its column there. The tab is read
// first (the button shows a spinner if that takes a while), so its table is drawn inside the place
// change, where the tile can land.
function loadsLine(clientId, tile) {
  const line = el("div", "loads");
  const map = current("map");
  if (!map) {
    line.append(el("span", "muted", "Counting…"));
    const failed = () => line.replaceChildren(el("span", "muted", "Could not count."));
    loadMap().then(() => (current("map") ? line.replaceWith(loadsLine(clientId, tile)) : failed())).catch(failed);
    return line;
  }
  const counts = loadCounts(map.rows, clientId);
  if (!counts.length) line.append(el("span", "muted", "Nothing on here."));
  for (const [kind, , words] of counts) {
    line.append(button(words, async () => {
      const choice = { kind, show: "mine", category: "", attention: false, q: "" };
      await loadLibraryFor(choice);
      fly(tile, `client-${clientId}`);
      go("library", choice);
    }, "btn small ghost"));
  }
  return line;
}

// The notes by item: one group per name, in the order first seen. A note about several names
// (unknown on/off state) joins each name's group. A group has the clients of all its notes, the
// distinct note words, and its first note for Details.
export function noteGroups(findings) {
  const groups = new Map();
  for (const finding of findings) {
    const words = NOTE_WORDS[finding.type] || finding.type.replaceAll("_", " ");
    for (const name of new Set(finding.names)) {
      if (!groups.has(name)) groups.set(name, { name, clients: [], notes: [], first: finding });
      const group = groups.get(name);
      for (const client of finding.clients || []) if (!group.clients.includes(client)) group.clients.push(client);
      if (!group.notes.includes(words)) group.notes.push(words);
    }
  }
  return [...groups.values()];
}

// One row per item: the mark of every client its notes are about, the name, each note as a
// quiet flag, Details.
function noteRow(group) {
  const node = el("div", "list-row");
  const marks = el("span", "who");
  for (const client of group.clients) marks.append(mark(client));
  const what = el("span", "what");
  const name = el("span", "mono", group.name);
  name.title = group.name;
  what.append(name, ...group.notes.map((text) => flag({ text, level: "info" })));
  const actions = el("span", "row-actions");
  actions.append(button("Details", () => showNote(group), "btn small ghost"));
  node.append(marks, what, actions);
  return node;
}

// The Library row a note row names: the row that holds one of its note's items of that name. A
// note about several names (unknown on/off state) opens each name's own row.
export function noteItemRow(group, rows) {
  const { items, names } = group.first;
  const mine = items.filter((_, i) => names[i] === group.name);
  return rows.find((r) => Object.values(r.cells).some((cell) => (cell.items || []).some((id) => mine.includes(id)))) || null;
}

// The note is about an item on this computer: select it and open it in the Library, in the panel.
async function showNote(group) {
  if (!current("map")) await loadMap();
  const map = current("map");
  const row = noteItemRow(group, (map && map.rows) || []);
  if (row) await follow({ view: "map", kind: row.kind, name: row.lookup });
  else toast("Could not find this item in the Library.");
}

// The clients' versions came in the background: the Clients card reads them and redraws only
// itself, keeping focus on the same row; the all-clear line follows.
globalThis.document?.addEventListener("kitden:versions", async () => {
  let clients;
  try { clients = await getJson("/api/clients"); } catch { return; }
  data.clients = clients;
  const model = current("overview");
  if (!model) return;
  model.clients = clients.map((c) => ({ id: c.id, name: c.display_name, version: c.version, tested: c.version_supported, status: c.status }));
  const clear = document.querySelector(".all-clear");
  if (clear) clear.textContent = allClearWords(clients);
  const old = document.querySelector('[data-part="clients"]');
  if (!old) return;
  const key = old.contains(document.activeElement) ? focusKey(document.activeElement) : null;
  const card = clientsCard(model.clients);
  old.replaceWith(card);
  const same = key && [...card.querySelectorAll("[data-focus]")].find((node) => node.dataset.focus === key);
  if (same) same.focus({ preventScroll: true });
});

// A client's status, only when something is wrong: Kitden could not read it, it is not installed,
// or Kitden has not tested its version. Null when all is well.
export function clientStatus(client) {
  if (client.status === "unreadable") return { state: "unk", word: STATE_WORDS.unread };
  if (client.status !== "found") return { state: "missing" };
  if (client.version && !client.tested) return { state: "unk", word: "Not tested" };
  return null;
}

function clientsCard(clients) {
  const card = el("section", "card");
  card.dataset.part = "clients";
  card.append(el("h2", null, "Clients"));
  const map = current("map");
  const columns = new Set((map ? map.columns : []).map((c) => c.id).concat(["claude_code", "codex", "cursor"]));
  for (const client of clients) {
    const row = el("div", "client-row");
    const info = el("div");
    info.append(el("div", "name", client.name), el("div", "meta", versionWords(client.version, data.progress, client.status === "found")));
    const tile = mark(client.id);
    row.append(tile, info);
    const status = clientStatus(client);
    if (status) row.append(socket(status));
    if (client.status !== "found" || !columns.has(client.id)) {
      card.append(row);
      continue;
    }
    // The whole row is the switch; the counts slide open under it.
    row.classList.add("expandable");
    row.tabIndex = 0;
    row.dataset.focus = `client:${client.id}`;
    row.setAttribute("role", "button");
    const more = el("div", "client-more");
    const inner = el("div");
    more.append(inner);
    const sync = () => {
      const open = openClients.has(client.id);
      row.setAttribute("aria-expanded", String(open));
      more.classList.toggle("open", open);
      if (open && !inner.firstChild) inner.append(loadsLine(client.id, tile));
    };
    const toggle = () => {
      if (openClients.has(client.id)) openClients.delete(client.id);
      else openClients.add(client.id);
      sync();
    };
    row.addEventListener("click", toggle);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
    });
    row.append(el("span", "chevron"));
    sync();
    card.append(row, more);
  }
  return card;
}

// The words of the gateway card. The Kitden gateway says what it holds and who reaches it, and
// offers the first client without its entry; without any gateway the card offers "Set up".
export function gatewayCardWords(gateway) {
  if (!gateway) return { title: "Gateway", line: "No gateway yet.", action: "Set up" };
  const names = gateway.clients.map((c) => CLIENT_NAMES[c]).join(", ");
  const parts = [gateway.servers ? plural(gateway.servers, "server", "servers") : "", names].filter(Boolean);
  const line = gateway.problem || parts.join(" · ") || "Nothing in it yet.";
  const [lacking] = gateway.lacking;
  return { title: gateway.name, line, action: lacking ? `Set up in ${CLIENT_NAMES[lacking]}…` : null };
}

function gatewayCard(gateway) {
  const words = gatewayCardWords(gateway);
  const card = el("section", "card");
  card.append(el("h2", null, words.title), el("p", null, words.line));
  if (!gateway) card.append(el("p", "muted", "Manage MCP tools in one place and connect it to every client."));
  if (words.action === "Set up") card.append(button(words.action, () => go("gateway")));
  else if (words.action) {
    // The same review the Gateway page opens for this client.
    const entry = kitdenClients(data.setupServer).setup.find((s) => s.client === gateway.lacking[0]);
    card.append(button(words.action, () => (entry ? review(entry.body, { note: SETUP_NOTE }) : go("gateway"))));
  }
  return card;
}
