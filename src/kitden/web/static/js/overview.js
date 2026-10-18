// Overview: what needs attention first, then the clients and, without a gateway, how to get one.
import { getJson, query } from "./api.js";
import { button, el, plural } from "./dom.js";
import { openSelectedOnRender } from "./map.js";
import { entrance, fly } from "./motion.js";
import { toast } from "./panel.js";
import { banner, flag, mark, skeleton, socket } from "./parts.js";
import { data, go, loadMap, loadOverview, projectPath, render } from "./store.js";

let notesOpen = false;

export function renderOverview(main) {
  const model = data.overview;
  if (!model) {
    main.append(el("h1", null, "Overview"));
    if (data.errors.overview) main.append(banner("the overview", async () => { await loadOverview(); render(); }));
    else main.append(skeleton("card", 3));
    return;
  }

  main.append(el("h1", null, model.headline));
  const found = (data.clients || []).filter((c) => c.status === "found").length;
  const projects = (data.projects || []).length;
  main.append(el("p", "lede", model.attention.length
    ? `Everything else looks fine: ${plural(found, "client", "clients")} found, ${plural(projects, "project", "projects")}.`
    : `${plural(found, "client", "clients")} found, ${plural(projects, "project", "projects")}. Nothing needs your attention.`));

  const grid = el("div", "overview");
  const left = el("section", "attention");
  left.setAttribute("aria-label", "Needs attention");
  const blocks = [];
  // One card per problem: a short title, one sentence, one button that names the action.
  for (const card of model.attention) {
    const article = el("article", "issue");
    article.append(el("h3", null, card.title), el("p", null, card.text));
    if (card.action && card.target) article.append(button(card.action, () => follow(card.target), "btn primary"));
    left.append(article);
    blocks.push(article);
  }
  if (!model.attention.length) {
    const clear = el("div", "all-clear", "No duplicates, no unreadable files, no untested versions.");
    left.append(clear);
    blocks.push(clear);
  }
  if (model.notes) left.append(notesBlock(model.notes));
  grid.append(left);

  const side = el("div", "side");
  side.append(clientsCard(model.clients));
  // With a gateway, the attention card is the one place on this page that mentions it.
  if (!model.gateway) side.append(gatewayCard());
  grid.append(side);
  main.append(grid);
  entrance("overview", [...blocks, ...side.children]);
}

// A card about an item opens that item in the side panel; paths and the fix live there.
function follow(target) {
  if (target.view === "map") {
    openSelectedOnRender();
    go("map", { kind: target.kind, only: "all", q: "", selected: target.row });
  } else {
    go(target.view);
  }
}

// A note in short words; the full explanation, with its paths, is in the item's panel.
const NOTE_WORDS = {
  cross_loaded: "Loaded from another client",
  same_in_other_clients: "Set up in more than one client",
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
      for (const f of findings.filter((x) => x.severity === "info")) list.append(noteRow(f));
    }).catch(() => { list.replaceChildren(el("p", "muted", "Could not load the notes.")); });
  }
  return box;
}

// A found client opens to what it loads, counted from the Load map; each count goes there.
const LOAD_KINDS = [
  ["mcp_server", "MCP server", "MCP servers"], ["plugin", "plugin", "plugins"],
  ["skill", "skill", "skills"], ["hook", "hook", "hooks"],
];
const openClients = new Set();

// A count opens that Load map tab; the client's tile flies to its column there.
function loadsLine(clientId, tile) {
  const line = el("div", "loads");
  if (!data.map) {
    line.append(el("span", "muted", "Counting…"));
    const failed = () => line.replaceChildren(el("span", "muted", "Could not count."));
    loadMap().then(() => (data.map ? line.replaceWith(loadsLine(clientId, tile)) : failed())).catch(failed);
    return line;
  }
  const counts = LOAD_KINDS.map(([kind, one, many]) => {
    const n = data.map.rows.filter((r) => r.kind === kind && ["on", "gw"].includes(r.cells[clientId] && r.cells[clientId].state)).length;
    return [kind, n, plural(n, one, many)];
  }).filter(([, n]) => n);
  if (!counts.length) line.append(el("span", "muted", "Loads nothing here."));
  for (const [kind, , words] of counts) {
    line.append(button(words, () => {
      fly(tile, `client-${clientId}`);
      go("map", { kind, only: "all", q: "" });
    }, "btn small ghost"));
  }
  return line;
}

// One row per note: the client it is about, the item names, what kind of note, Details.
function noteRow(finding) {
  const node = el("div", "list-row");
  const marks = el("span", "chip");
  if (finding.client) marks.append(mark(finding.client));
  const what = el("span", "what");
  const names = [...new Set(finding.names)];
  const name = el("span", "mono", names.join(", "));
  name.title = names.join(", ");
  what.append(name, flag({ text: NOTE_WORDS[finding.type] || finding.type.replaceAll("_", " "), level: "info" }));
  const actions = el("span", "row-actions");
  actions.append(button("Details", () => showNote(finding), "btn small ghost"));
  node.append(marks, what, actions);
  return node;
}

// The note is about items on the Load map; open the first one there, in the panel.
async function showNote(finding) {
  if (!data.map) await loadMap();
  const rows = (data.map && data.map.rows) || [];
  const row = rows.find((r) => Object.values(r.cells).some((cell) => (cell.items || []).some((id) => finding.items.includes(id))));
  if (row) follow({ view: "map", kind: row.kind, row: row.key });
  else toast("Could not find this item on the Load map.");
}

function clientsCard(clients) {
  const card = el("section", "card");
  card.append(el("h2", null, "Clients"));
  const columns = new Set((data.map ? data.map.columns : []).map((c) => c.id).concat(["claude_code", "codex", "cursor"]));
  for (const client of clients) {
    const row = el("div", "client-row");
    const info = el("div");
    info.append(el("div", "name", client.name), el("div", "meta", client.version ? client.version : "version unknown"));
    const tile = mark(client.id);
    row.append(tile, info);
    // A status only when something is wrong: not installed, or a version Kitden has not tested.
    if (client.status !== "found") row.append(socket({ state: "missing" }));
    else if (client.version && !client.tested) row.append(socket({ state: "unk", word: "Not tested" }));
    if (client.status !== "found" || !columns.has(client.id)) {
      card.append(row);
      continue;
    }
    // The whole row is the switch; the counts slide open under it.
    row.classList.add("expandable");
    row.tabIndex = 0;
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

function gatewayCard() {
  const card = el("section", "card");
  card.append(el("h2", null, "Gateway"), el("p", null, "No gateway yet."));
  card.append(el("p", "muted", "Manage MCP tools in one place and connect it to every client."));
  card.append(button("Set up", () => go("gateway")));
  return card;
}
