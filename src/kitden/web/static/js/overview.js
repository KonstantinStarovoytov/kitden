// Overview: what needs attention first, then the clients and, without a gateway, how to get one.
import { getJson, query } from "./api.js";
import { button, el, plural, shortPaths } from "./dom.js";
import { openSelectedOnRender } from "./map.js";
import { entrance } from "./motion.js";
import { banner, mark, skeleton, socket } from "./parts.js";
import { data, go, loadOverview, projectPath, render } from "./store.js";

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

function notesBlock(count) {
  const box = el("div");
  const toggle = button(notesOpen ? "Hide notes" : `Show ${plural(count, "note", "notes")} (nothing to fix)`, async () => {
    notesOpen = !notesOpen;
    render();
  }, "btn ghost small notes-toggle");
  box.append(toggle);
  if (notesOpen) {
    const list = el("ul", "notes");
    list.append(el("li", "muted", "Loading…"));
    box.append(list);
    getJson(`/api/findings${query({ project: projectPath() })}`).then((findings) => {
      list.replaceChildren();
      for (const f of findings.filter((x) => x.severity === "info")) list.append(el("li", null, shortPaths(f.explanation)));
    }).catch(() => { list.replaceChildren(el("li", null, "Could not load the notes.")); });
  }
  return box;
}

function clientsCard(clients) {
  const card = el("section", "card");
  card.append(el("h2", null, "Clients"));
  for (const client of clients) {
    const row = el("div", "client-row");
    const info = el("div");
    info.append(el("div", "name", client.name), el("div", "meta", client.version ? client.version : "version unknown"));
    row.append(mark(client.id), info);
    // A status only when something is wrong: not installed, or a version Kitden has not tested.
    if (client.status !== "found") row.append(socket({ state: "missing" }));
    else if (client.version && !client.tested) row.append(socket({ state: "unk", word: "Not tested" }));
    card.append(row);
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
