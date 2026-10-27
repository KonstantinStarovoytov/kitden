// The parts every Details card shares: the card itself (detailsCard), its facts, buttons and More,
// Technical details, the buttons and switches that follow the tray, and the way back from a step
// (keepFrom, backToDetails). Gateway and Library Details are drawn from them.
import { $, $$, button, el, joinWords, reportError, shortPath, withFocusKey } from "./dom.js";
import { fold } from "./motion.js";
import { header, isPanelOpen, isQuiet, openInfo, panelState } from "./panel.js";
import { ALL_PROJECTS, callout, CLIENT_NAMES, CLIENT_ORDER, folderName, gatewayName, ROUTE_WORDS } from "./parts.js";
import { review } from "./review.js";
import { data, projectPath } from "./store.js";
import { inTray, keyFor, takeOut } from "./tray.js";

export const KIND_WORDS = {
  mcp_server: "MCP server", plugin: "Plugin", skill: "Skill", hook: "Hook", marketplace: "Marketplace",
};
const WRITABLE = ["claude_code", "codex", "cursor"];
// A switch names its own client; a Remove names every client it reaches (offerLabel).
const ACTION_BUTTONS = {
  "plugin.disable": (client) => `Turn off in ${client}…`,
  "plugin.enable": (client) => `Turn on in ${client}…`,
  "mcp.remove_direct": (clients) => `Remove from ${clients}…`,
  "plugin.remove": (clients) => `Remove from ${clients}…`,
  "skill.remove": (clients) => `Remove from ${clients}…`,
};
const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove"];
export const clientName = (id) => CLIENT_NAMES[id] || id;

// The gateways that can take the direct servers of one group of the Gateway page, in the order
// offered: the Kitden gateway first (it runs on this Mac, so it also takes local servers), then
// each registered gateway that takes servers (remote ones only).
export function moveTargets(model, group) {
  if (!model) return [];
  const kitden = model.gateways.filter((g) => g.kind === "kitden");
  if (group === "local") return kitden;
  if (group !== "move") return [];
  return [...kitden, ...model.gateways.filter((g) => g.kind !== "kitden" && g.movable)];
}

// The preview request that moves `items` (entry ids) into `gateway`. A drag on the Gateway map
// asks the same (gateway-drag.js dropBody).
export function moveBody(gateway, items) {
  return { action: "gateway.move", targets: items.map((item) => ({ item })), params: { gateway: gateway.id } };
}

// Move entries into a gateway. With one gateway that can take them the move goes to the tray at
// once; with two the panel asks which, the Kitden gateway first. A move into the Kitden gateway
// may ask the server for its tools first, so the button that started it stays busy until then.
export function moveInto(gateways, items, title) {
  if (gateways.length === 1) return review(moveBody(gateways[0], items));
  const body = el("div", "body");
  body.append(el("p", "muted", "More than one gateway can take it. The Kitden gateway runs on this Mac and turns tools on or off per project."));
  const into = (gateway) => (gateway.kind === "kitden" ? "the Kitden gateway" : gatewayName(gateway));
  // The primary button sits last, so the Kitden gateway is drawn last.
  const choices = gateways.map((gateway, i) => previewButton(`Move into ${into(gateway)}…`, moveBody(gateway, items), { look: i === 0 ? "btn primary" : "btn" }));
  openInfo("Move into the gateway", title, body, choices.reverse());
  return null;
}

// A server in the Kitden gateway can leave it, or be written back into a client as its own
// entry. `clients` are the found clients Kitden can write. With `plain` (its entry still holds
// a secret) its secrets can move to the Keychain.
export function heldActions(server, clients, plain = false) {
  return [
    { label: "Remove from the Kitden gateway…", body: { action: "gateway.remove", targets: [], params: { server } } },
    ...clients.map((client) => ({
      label: `Put back in ${CLIENT_NAMES[client]}…`,
      body: { action: "gateway.put_back", targets: [{ client }], params: { server } },
    })),
    ...(plain ? [{ label: "Move secrets to the Keychain…", body: { action: "gateway.keychain", targets: [], params: { server } } }] : []),
  ];
}

// The other actions wait behind one button, so the primary one stands alone. They show the tray as
// it is when they come out: it may have changed while they waited. One other action stands as it
// is: a More that hides one button only adds a press.
function moreNodes(buttons) {
  if (buttons.length === 1) return buttons;
  const more = button("More", () => {
    more.replaceWith(...buttons);
    buttons.forEach(showTrayLook);
    buttons[0].focus();
  }, "btn");
  more.dataset.focus = "more";
  return [more];
}

// A button's words. A Remove names every client it reaches (def.affects.clients): "Remove from
// Codex and Cursor…". When one client has more than one definition that can change, the label
// names the scope too, or the folder when the scopes are the same (one skill in two folders).
export function offerLabel({ def, action }, offers) {
  const twins = offers.filter((o) => o.def.client === def.client && o.def.id !== def.id);
  let where = "";
  if (twins.length) {
    const same = twins.some((o) => scopeWords(o.def) === scopeWords(def));
    where = ` (${same ? placeWords(def) : scopeWords(def).toLowerCase()})`;
  }
  const clients = REMOVES.includes(action) && def.affects ? def.affects.clients : [def.client];
  return ACTION_BUTTONS[action](`${joinWords(clients.map(clientName))}${where}`);
}

// The folder a definition sits in, by its last two parts so the label stays short: a skill's
// skills folder (".agents/skills"), or the file of any other entry (".cursor/mcp.json").
function placeWords(def) {
  const parts = String(def.source || "").split("/").filter(Boolean);
  const place = parts[parts.length - 1] === "SKILL.md" ? parts.slice(0, -2) : parts;
  return place.slice(-2).join("/");
}

// Facts: a label and a value each, in two columns. A value is words or a node (client marks);
// `accent` draws it in the accent color, for what applies in the picked project, `warn` in amber,
// for a tool that may write or rules that do not reach a server, and `quiet` in the quiet color,
// for nothing there.
export function factsBlock(rows) {
  const list = el("dl", "facts");
  for (const { label, value, accent = false, warn = false, quiet = false } of rows) {
    const detail = el("dd", accent ? "accent" : warn ? "warn" : quiet ? "quiet" : null);
    if (typeof value === "string") detail.textContent = value;
    else detail.append(value);
    list.append(el("dt", null, label), detail);
  }
  return list;
}

// One action of a card as a button: `run()` on press, else a preview button that adds `body`, with
// its `note`, to the tray; or a control the card made itself (`node`). The whole label stays in the
// hover text when the column cuts it.
function cardButton({ label, run, body, note = null, primary = false, node: own = null }) {
  if (own) return own;
  const look = primary ? "btn primary" : "btn";
  let node = null;
  if (run) {
    node = button(null, () => run(), look);
    node.title = label;
    node.append(el("span", "cut", label));
  } else {
    node = previewButton(label, body, { note, look });
  }
  node.dataset.focus = `action:${label}`;
  return node;
}

// A card as the nodes openPanel shows, in the order of every Details card: the kind and Close, the
// title with the id quiet under it (and `tile`, a node, beside both), the facts, a list (`list`, a
// node: a server's switches, a tool's projects with rules of their own, a gateway's clients), one
// sentence (words, or a node that changes), the actions stacked in the footer in order (`more`
// waits behind one More button, `after` is a quiet node under them), and the evidence folded last
// (`technical`, a node from technical(rows)). At most one action is `primary`. Card builders return
// this plain object, so a test reads its fields without a page.
export function detailsCard({ kind, title, id = null, tile = null, facts = [], why = null, list = null, actions = [], more = [], after = null, technical: evidence = null }) {
  const body = el("div", "body");
  if (facts.length) body.append(factsBlock(facts));
  if (list) body.append(list);
  if (why) body.append(typeof why === "string" ? el("p", "why", why) : why);
  const footer = el("footer", "stack");
  footer.append(...actions.map(cardButton));
  if (more.length) footer.append(...moreNodes(more.map(cardButton)));
  if (after) footer.append(after);
  return [cardHead(kind, title, id, tile), body, ...(footer.children.length ? [footer] : []), ...(evidence ? [evidence] : [])];
}

// A card's head: the kind and Close over its title (words, or parts: a link's two ends and the
// arrow between them) and its id; a tile (a client's, the house, a server's icon) sits beside the
// title and the id, after them for a screen reader, which hears nothing of it.
function cardHead(kind, title, id, tile) {
  const head = header(kind, typeof title === "string" ? title : null, id);
  if (typeof title !== "string") head.children[1].append(...title);
  if (tile) {
    head.classList.add("has-tile");
    tile.setAttribute("aria-hidden", "true");
    head.append(tile);
  }
  return head;
}

// The client whose folder or file this definition is read from, when it is another of the
// three clients (WRITABLE). "shared" (~/.agents/skills) and the Kitden gateway are not
// clients: the Why says a shared folder in words, and a held server's route.
function ownerName(def) {
  const owner = def.owner_client;
  return owner && owner !== def.client && WRITABLE.includes(owner) ? clientName(owner) : null;
}

// Where a definition applies, in the words the cells use: the picked project is "This project".
export function scopeWords(def, picked = projectPath()) {
  const project = folderName(def.project);
  const words = {
    user: ALL_PROJECTS,
    project: def.project && def.project === picked ? "This project" : `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const owner = ownerName(def);
  return owner ? `${words} · ${ROUTE_WORDS.folder.replace("{}", owner)}` : words;
}

// Where a definition's file sits, in file words. Only the technical details say these: spec
// 2.1 keeps "global settings" there.
export function fileScopeWords(def) {
  const project = folderName(def.project);
  const words = {
    user: "Global settings",
    project: `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const owner = ownerName(def);
  return owner ? `${words} · via ${owner}` : words;
}

const inClientOrder = (definitions) => [...definitions].sort((a, b) => CLIENT_ORDER.indexOf(a.client) - CLIENT_ORDER.indexOf(b.client));
const clientsOf = (definitions) => [...new Set(definitions.map((d) => clientName(d.client)))];

// The evidence under "Technical details", in client order: one row per file, file key,
// command and first lines, titled with every client that reads it and the file words
// ("Codex and Cursor · Global settings"). A held server's entry is the Kitden gateway's own.
export function techRows(definitions) {
  const rows = new Map(); // the same evidence -> one row and its definitions
  for (const def of inClientOrder(definitions)) {
    const row = {
      client: def.client,
      path: String(def.source || "").includes("/") ? def.source : null,
      key: def.key || null,
      summary: def.summary || null,
      preview: def.preview && def.preview.length ? def.preview : null,
    };
    if (!row.path && !row.key && !row.summary && !row.preview) continue;
    const id = JSON.stringify([row.path, row.key, row.summary, row.preview]);
    if (!rows.has(id)) rows.set(id, { row, defs: [] });
    rows.get(id).defs.push(def);
  }
  return [...rows.values()].map(({ row, defs }) => {
    const who = defs[0].via_gateway === "kitden" ? CLIENT_NAMES.kitden : joinWords(clientsOf(defs));
    return { ...row, title: `${who} · ${fileScopeWords(defs[0])}` };
  });
}

// The evidence, folded: per definition its file (the whole path in the hover text), file key,
// command and first lines. It opens like "Show file change" in a review.
export function technical(rows) {
  const box = el("details", "tech");
  box.append(el("summary", null, "Technical details"));
  for (const r of rows) {
    const part = el("div", "tech-row");
    part.append(el("div", "name", r.title));
    if (r.path) {
      const where = el("div", "mono", shortPath(r.path));
      where.title = r.path;
      part.append(where);
    }
    if (r.key) part.append(el("div", "mono", r.key));
    if (r.summary) part.append(el("div", "mono", r.summary));
    // An instruction file's first lines, secrets hidden by the server.
    if (r.preview) part.append(el("pre", "preview", r.preview.join("\n")));
    box.append(part);
  }
  return fold(box);
}

// The tray in Details --------------------------------------------------------------------------

const IN_PREVIEW = "In preview";
// How each control whose change can wait in the tray shows whether it does: `look(waiting)`.
const trayLooks = new WeakMap();

// `node` follows the tray: `data-tray` names its row, and `look(waiting)` draws it now and after
// every change of the tray (syncTray).
export function followTray(node, key, look) {
  node.dataset.tray = key;
  trayLooks.set(node, look);
  look(inTray(key));
}

function showTrayLook(node) {
  const look = trayLooks.get(node);
  if (look) look(inTray(node.dataset.tray));
}

// The tray changed (panel.js listens): every switch and button in Details shows whether its change
// waits there. Only those controls change; nothing is drawn again.
export function syncTray() {
  syncTrayIn($("#drawer"));
}

// The same for the controls under `root` (the Overview's card buttons).
export function syncTrayIn(root) {
  for (const node of $$("[data-tray]", root)) showTrayLook(node);
}

// A switch that shows a real state; it flips only when the change is written and checked, never
// before. A press runs `press`, which adds its change to the tray. While that change waits there
// (`key`, its row) the switch rests half-way, pending, and a press takes it out again; its name
// (`label`) then ends "(in preview)", since its checked state stays the real one. Without `press`
// it only shows.
export function switchNode(on, press, key = null, label = null) {
  const node = el("button", "switch");
  node.type = "button";
  node.setAttribute("role", "switch");
  node.setAttribute("aria-checked", String(on));
  if (label) node.setAttribute("aria-label", label);
  node.append(el("span", "thumb"));
  if (!press) return node;
  const idle = on ? "On. Press to preview turning it off." : "Off. Press to preview turning it on.";
  node.title = idle;
  if (key) {
    followTray(node, key, (waiting) => {
      node.classList.toggle("pending", waiting);
      if (label) node.setAttribute("aria-label", waiting ? `${label} (in preview)` : label);
      // A switch that is off here keeps the words that say why.
      if (!node.disabled) node.title = waiting ? "In preview. Press to take it out." : idle;
    });
  }
  node.addEventListener("click", () => {
    Promise.resolve(key && inTray(key) ? takeOut(key) : press()).catch(reportError);
  });
  return node;
}

// A Details button that adds `body` to the tray (review, with `note`, and `back` for a tool list).
// While that change waits there it says "In preview" and takes no press. It never turns :disabled,
// so it keeps focus and a keyboard user stays where they were: while its add is asked it shows
// the busy spinner after a moment (aria-busy) and takes no second press. The hover text keeps
// what it does.
export function previewButton(label, body, { note = null, look = "btn", back = null } = {}) {
  const key = keyFor(body);
  const words = el("span", "cut", label);
  const node = el("button", look);
  node.type = "button";
  node.title = label;
  node.append(words);
  node.addEventListener("click", () => {
    if (inTray(key) || node.dataset.working) return;
    node.dataset.working = "1";
    let shown = false;
    const slow = setTimeout(() => {
      shown = true;
      node.classList.add("busy");
      node.setAttribute("aria-busy", "true");
    }, 150);
    Promise.resolve(review(body, { note, back })).catch(reportError).finally(() => {
      clearTimeout(slow);
      delete node.dataset.working;
      if (!shown) return;
      node.classList.remove("busy");
      node.removeAttribute("aria-busy");
    });
  });
  showInPreview(node, words, label, key);
  return node;
}

// A button that says "In preview" in place of its `label` (in `words`) while the tray row `key`
// waits, and takes no press then. Called again with another `key`, it follows that row instead.
export function showInPreview(node, words, label, key) {
  followTray(node, key, (waiting) => {
    words.textContent = waiting ? IN_PREVIEW : label;
    if (waiting) node.setAttribute("aria-disabled", "true");
    else node.removeAttribute("aria-disabled");
  });
}

// What a press in this panel comes back to (backToDetails): `draw()` draws the panel again from
// what it read, `read()` reads it again (when `stale`: after Apply all, review.js detailsAgain),
// `focus` is the control pressed last, by its focus key, heard by one capture click listener on
// each of `nodes` (the body and the footer), and `shown()` says whether the panel still shows them.
export function keepFrom(draw, nodes, read = draw) {
  const from = { draw, read, focus: null, shown: () => nodes.some((node) => node && node.isConnected) };
  panelState.from = from;
  const remember = (event) => {
    const node = event.target && event.target.closest ? event.target.closest("[data-focus]") : null;
    if (node) from.focus = node.dataset.focus;
  };
  for (const node of nodes) if (node) node.addEventListener("click", remember, true);
  return from;
}

// Where focus goes back to in Details: the control pressed (`key`) when it is drawn again, else
// More when that control waits under it again, else null (the panel itself).
export function focusAfterBack(key, keys) {
  if (!key) return null;
  if (keys.includes(key)) return key;
  return keys.includes("more") ? "more" : null;
}

// Back to the panel a press in it left (Details, or the Kitden gateway's own panel of a held
// server): from Add missing's list, or drawn again after Apply all or an Undo. Drawn again from
// what it read then (no new read), or read again when `stale`. `error`: why the list was refused,
// first in the body. Focus goes back to the control pressed, unless the panel closed while it read,
// the person opened other Details meanwhile (a quiet read, panel.js), or `refocus` is false (focus
// was not in Details).
export async function backToDetails({ error = null, refocus = true } = {}) {
  const from = panelState.from;
  if (!from) return;
  const { focus } = from;
  if (from.stale) {
    const quietly = isQuiet();
    await from.read();
    // Other Details the person opened during the read keep their focus.
    if (!isPanelOpen() || (quietly && !isQuiet())) return;
  } else {
    from.draw();
  }
  const drawer = $("#drawer");
  const body = $(".body", drawer);
  if (error && body) body.prepend(callout(error, "error"));
  if (!refocus) return;
  const keys = $$("[data-focus]", drawer).map((node) => node.dataset.focus);
  (withFocusKey(drawer, focusAfterBack(focus, keys)) || drawer).focus();
}
