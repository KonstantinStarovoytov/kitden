// Details of the Library map (library-notes §3, with D25 and D26): a card builder for each thing the
// map selects (a plugin, a thing inside one, a skill, a hook, a client, a link and a marketplace's
// caption), each a plain object that detailsCard draws, so a test reads it without a page, and the
// steps "Add to <client>…" and "Turn off in some projects…" take. A press, a tick or a switch only
// adds a row to the tray; nothing is written before Apply. Paths stay under Technical details.
import { button, el, icon, joinWords, plural } from "./dom.js";
import { focusAfterStep, headTile, iconTile, lamp, openCard, pressOnce, projectChecklist, stepHead, tickRow, tiles } from "./gateway-details.js";
import { lampOf, libraryThing, onLibrarySelect } from "./library-map.js";
import { closePanel, drawQuietly, followTray, isPanelOpen, keepFrom, panelState, previewButton, review, stepTo, swapContent, technical } from "./panel.js";
import { ALL_PROJECTS, CLIENT_NAMES, CLIENT_ORDER, folderName, mark, menuItems, ORIGIN_WORDS, STATE_WORDS } from "./parts.js";
import { data, projectPath, state } from "./store.js";
import { inTray, keyFor, tray } from "./tray.js";

const IN_PREVIEW = "In preview";
const OFF_ALL = "Turn off for all projects…";
const OFF_SOME = "Turn off in some projects…";
const OFF_HERE = "Turn off in this project…";
const FOLLOWS = "Follows its plugin.";
const NO_PLUGIN = "None, a skill on its own";
const NO_PROJECT_SWITCH = "Codex has no switch for one project.";
const NO_CURSOR_SWITCH = "Cursor has no switch to turn off one skill.";
const SOME_WHY = "This turns it off in Claude Code. Codex and Cursor have no switch for one project.";
// Why a project cannot take a one-project skill rule (library_map.py `skill_rules`).
const PROJECT_LINES = { own: "Has its own skill settings", new: "No Claude Code settings yet" };
// Why a tray cannot take both a skill rule for all projects and one for a project in Claude Code.
const ALL_FIRST = "Apply the rule for all projects first";
const SOME_FIRST = "Apply the project rules in preview first; then Claude Code can turn it off for all projects.";
// What a plugin holds, by its key in the answer: the word for one and for more.
const INSIDE_WORDS = [["skills", "skill", "skills"], ["commands", "command", "commands"], ["agents", "agent", "agents"], ["hooks", "hook", "hooks"], ["mcp_servers", "MCP server", "MCP servers"]];
const KIND_ICONS = { plugin: "puzzle", skill: "sparkles", hook: "webhook" };
const KIND_WORDS = { plugin: "Plugin", skill: "Skill", hook: "Hook" };
const LAMP_WORDS = { on: STATE_WORDS.on, off: STATE_WORDS.off, unk: STATE_WORDS.unk };

const inOrder = (clients) => [...clients].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
const names = (clients) => inOrder(clients).map((client) => CLIENT_NAMES[client] || client);
const clientsBy = (item, look) => Object.entries(item.by || {}).filter(([, state]) => state === look).map(([client]) => client);
const verb = (clients, one, more) => (clients.length > 1 ? more : one);

// What a card is drawn for: the answer, the picked project (its id and folder) and the rules of
// where a one-project skill rule can go.
export function context(answer, project = state.project, folder = folderName(projectPath())) {
  return { answer, project, folder, rules: (answer && answer.skill_rules) || { some: false, projects: {} } };
}

// "3 skills · 1 command", from what Kitden read inside a plugin; null when it read nothing.
export function insideWords(inside) {
  if (!inside) return null;
  const parts = INSIDE_WORDS.filter(([key]) => (inside[key] || []).length).map(([key, one, more]) => plural(inside[key].length, one, more));
  return parts.length ? parts.join(" · ") : "Nothing";
}

// Where an item loads, in one or more sentences, from Kitden's own facts: "Claude Code and Codex
// load it in every project. Cursor gets it through Claude Code." `noun` is "it" or "this skill".
export function loadsSay(item, { folder = "", noun = "it" } = {}) {
  const through = item.through || {};
  const own = clientsBy(item, "on").filter((client) => !through[client]);
  const lines = [];
  if (own.length) lines.push(`${joinWords(names(own))} ${verb(own, "loads", "load")} ${noun} ${folder ? `in ${folder}` : "in every project"}.`);
  for (const owner of inOrder(new Set(Object.values(through)))) {
    const readers = Object.keys(through).filter((client) => through[client] === owner);
    lines.push(`${joinWords(names(readers))} ${verb(readers, "gets", "get")} it through ${CLIENT_NAMES[owner]}.`);
  }
  const off = clientsBy(item, "off");
  if (off.length) lines.push(`It is off in ${joinWords(names(off))}.`);
  const unknown = clientsBy(item, "unknown");
  if (unknown.length) lines.push(`Kitden can't tell whether ${joinWords(names(unknown))} ${verb(unknown, "loads", "load")} it.`);
  if (clientsBy(item, "via").length) lines.push("Cursor gets it once Claude Code adds it.");
  return lines.join(" ") || "No client loads it.";
}

// The facts every item shares.
function stateFact(item) {
  const look = lampOf(item);
  const value = el("span", "fact-mark");
  value.append(lamp(look), el("span", null, LAMP_WORDS[look]));
  return { label: "State", value, text: LAMP_WORDS[look] };
}

// The clients that load it, by their tiles and names ("Claude Code, Cursor"), or by how many.
function clientsFact(item, { count = false } = {}) {
  const clients = inOrder(clientsBy(item, "on"));
  if (!clients.length) return { label: "Clients", value: "None yet", quiet: true, text: "None yet" };
  const text = count ? plural(clients.length, "client", "clients") : names(clients).join(", ");
  return { label: "Clients", value: tiles(clients, text), text };
}

// "All projects", or the project's folder when its own settings decide there.
function comesFrom(item, c) {
  const here = c.project && (item.here || item.source === ORIGIN_WORDS.project);
  return here ? { label: "Comes from", value: `${ORIGIN_WORDS.override} · ${c.folder}`, accent: true } : { label: "Comes from", value: ALL_PROJECTS };
}

// A tile beside the title: a plugin's puzzle, a skill's sparkles, a hook's webhook.
const kindTile = (kind) => iconTile(KIND_ICONS[kind] || "puzzle");

// Technical details: only what Kitden read, each by its title.
function techOf(rows) {
  const shown = rows.filter((row) => row.path || row.summary);
  return shown.length ? technical(shown) : null;
}

// The tray rows -----------------------------------------------------------------------------------

// Turn it off for all projects: one row per client that loads its own copy and has a switch (`can.off`,
// library_map.py): a plugin's own switch, or a skill rule.
export function offBodies(item) {
  const clients = (item.can && item.can.off) || [];
  return clients.map((client) => {
    const target = item.items[client][0];
    if (item.kind === "plugin") return { action: "plugin.disable", targets: [{ item: target }], params: {} };
    return { action: "skill.rule", targets: [{ client, item: target }], params: { scope: "all", off: true } };
  });
}

// Add a plugin to one client, for all projects: the same body as a cell's add (library.js
// previewFor).
export function addBody(item, client) {
  return { action: "plugin.install", targets: [{ client }], params: { plugin: item.plugin } };
}

// A skill rule in one project, for Claude Code (a skill's skillOverrides, a plugin's
// enabledPlugins in the project's local settings).
export function projectBody(item, project) {
  return { action: "skill.rule", targets: [{ client: "claude_code", item: item.items.claude_code[0] }], params: { scope: "project", project, off: true } };
}

// "Turn off in this project…": in a project Claude Code can take a rule in, while Claude Code has
// the plugin on there; else null.
export function hereBody(item, c) {
  const on = (item.by || {}).claude_code === "on" && (item.items || {}).claude_code;
  const can = c.rules.projects[c.project];
  return c.project && on && (can === "ok" || can === "own") ? projectBody(item, c.project) : null;
}

// A skill of all projects, not only of the picked one.
const shared = (item) => item.source !== ORIGIN_WORDS.project;

// "Turn off in some projects…" for a skill of all projects that Claude Code has, while the user
// settings hold no skillOverrides (`rules.some`) and some project can take the rule.
export function offersSome(item, c) {
  return Boolean(shared(item) && (item.items || {}).claude_code && c.rules.some && Object.values(c.rules.projects).includes("ok"));
}

// Whether the tray holds a Claude Code skill rule of `scope` ("all" or "project"). Claude Code may
// not merge skillOverrides across files, so the server never takes one in the user file and one in
// a project's in one tray (changes/batch.py); the page offers neither while the other waits. A
// plugin's rule in one project is enabledPlugins, not skillOverrides: it does not count.
export function skillRuleWaits(scope, answer) {
  const plugins = new Set(answer.groups.flatMap((group) => group.items).filter((item) => item.kind === "plugin").flatMap((item) => (item.items || {}).claude_code || []));
  return tray.rows.some(({ body }) => {
    const target = (body.targets || [])[0] || {};
    return body.action === "skill.rule" && (body.params || {}).scope === scope && target.client === "claude_code" && !plugins.has(target.item);
  });
}

// "Turn off for all projects…" for a skill: one row per client that can, without Claude Code's while
// a one-project skill rule waits in the tray.
export function skillOffBodies(item, answer) {
  const blocked = skillRuleWaits("project", answer);
  return offBodies(item).filter((body) => !(blocked && body.targets[0].client === "claude_code"));
}

// A button that adds every row of `bodies` (a list, or a function that gives the list now) to the
// tray, one after the other. While they all wait there it says "In preview" and takes no press, as
// a preview button does (details.js); with none to add now it hides.
function rowsButton(label, bodies, look = "btn") {
  const list = typeof bodies === "function" ? bodies : () => bodies;
  const words = el("span", "cut", label);
  const node = el("button", look);
  node.type = "button";
  node.title = label;
  node.dataset.focus = `action:${label}`;
  node.append(words);
  const waiting = () => list().every((body) => inTray(keyFor(body)));
  pressOnce(node, async () => {
    if (waiting()) return;
    for (const body of list()) if (!inTray(keyFor(body))) await review(body);
  });
  followTray(node, keyFor(list()[0] || {}), () => {
    node.hidden = !list().length;
    const now = waiting();
    words.textContent = now ? IN_PREVIEW : label;
    if (now) node.setAttribute("aria-disabled", "true");
    else node.removeAttribute("aria-disabled");
  });
  return node;
}

// Words in a quiet line that show while `when()` holds, after every change of the tray.
function trayNote(words, when) {
  const node = el("p", "muted");
  followTray(node, "skill-rules", () => {
    node.textContent = when() ? words : "";
    node.hidden = !node.textContent;
  });
  return node;
}

// The cards ---------------------------------------------------------------------------------------

// "Add to Codex…", or "Add to Claude Code or Codex…" when both can take it.
export const addLabel = (clients) => `Add to ${names(clients).join(" or ")}…`;

// A plugin: State, Inside, Clients and Comes from; where it loads; "Add to <client>…" (a step to a
// checklist, `addStep`), "Turn off for all projects…" and, in a project, "Turn off in this
// project…"; its folder and its marketplace's source under Technical details.
export function pluginCard(item, c, { addStep = () => {} } = {}) {
  const inside = insideWords(item.inside);
  const facts = [stateFact(item), { label: "Inside", value: inside || "Not known", quiet: !inside }, clientsFact(item), comesFrom(item, c)];
  const actions = [];
  const adds = (item.can && item.can.add) || [];
  if (adds.length) actions.push({ label: addLabel(adds), run: addStep, primary: true });
  const off = offBodies(item);
  if (off.length) actions.push({ label: OFF_ALL, node: rowsButton(OFF_ALL, off) });
  const here = hereBody(item, c);
  if (here) actions.push({ label: OFF_HERE, body: here });
  const tech = item.technical || {};
  return { kind: KIND_WORDS.plugin, title: item.name, id: item.source, tile: kindTile("plugin"), facts, why: loadsSay(item, c), actions, technical: techOf([{ title: "Plugin folder", path: tech.path }, { title: "Marketplace", summary: tech.marketplace }]) };
}

// A thing a plugin holds: Plugin, Kind, Source and Clients, and "Follows its plugin." It has no
// switch (D25); in a project a skill has one quiet line that turns its plugin off there.
export function partCard(block, c) {
  const plugin = block.plugin;
  const tile = el("span", "fact-mark");
  tile.append(icon("puzzle", 13), el("span", null, plugin.name));
  const facts = [{ label: "Plugin", value: tile, text: plugin.name }, { label: "Kind", value: block.label.words }, { label: "Source", value: plugin.source }, clientsFact(plugin, { count: true })];
  const here = block.label.words === "Skill" ? hereBody(plugin, c) : null;
  let after = null;
  if (here) {
    const label = `Turn off ${plugin.name} in this project…`;
    after = previewButton(label, here, { look: "btn ghost small" });
    after.dataset.focus = `action:${label}`;
  }
  return { kind: block.label.words, title: block.name, id: plugin.name, tile: iconTile(block.label.icon), facts, why: FOLLOWS, after };
}

// A skill on its own: Plugin ("None, a skill on its own"), State, Comes from, Source and Clients;
// where it loads, and which clients have no switch; "Turn off for all projects…" and "Turn off in
// some projects…" (the project checklist, `someStep`); its file under Technical details.
export function skillCard(item, c, { someStep = () => {} } = {}) {
  const source = el("span", "fact-mark");
  source.append(icon(item.source === ORIGIN_WORDS.project ? "folder" : "user-round", 13), el("span", null, item.source));
  const facts = [{ label: "Plugin", value: NO_PLUGIN, quiet: true }, stateFact(item), comesFrom(item, c), { label: "Source", value: source, text: item.source }, clientsFact(item, { count: true })];
  const actions = [];
  if (offBodies(item).length) actions.push({ label: OFF_ALL, node: rowsButton(OFF_ALL, () => skillOffBodies(item, c.answer)) });
  if (offersSome(item, c)) actions.push({ label: OFF_SOME, run: someStep });
  const notes = [];
  if (shared(item) && (item.by || {}).codex) notes.push(NO_PROJECT_SWITCH);
  if ((item.by || {}).cursor === "on") notes.push(NO_CURSOR_SWITCH);
  const why = [loadsSay(item, { folder: c.project ? c.folder : "", noun: "this skill" }), ...notes].join(" ");
  const claude = ((item.can && item.can.off) || []).includes("claude_code");
  const after = claude ? trayNote(SOME_FIRST, () => skillRuleWaits("project", c.answer)) : null;
  return { kind: KIND_WORDS.skill, title: item.name, id: item.source, tile: kindTile("skill"), facts, why, actions, after, technical: techOf([{ title: "Skill file", path: (item.technical || {}).path }]) };
}

// A hook: its facts and Technical details only; hooks have no switch yet.
export function hookCard(item, c) {
  const facts = [stateFact(item), comesFrom(item, c), { label: "Source", value: item.source }, clientsFact(item, { count: true })];
  return { kind: KIND_WORDS.hook, title: item.name, id: item.source, tile: kindTile("hook"), facts, technical: techOf([{ title: "Settings file", path: (item.technical || {}).path }]) };
}

// One framed list of items (tools.js's look): a tile, the name over a quiet line.
function itemList(head, rows) {
  const section = el("section", "tool-list");
  section.append(el("h2", "sw-head", head));
  if (!rows.length) {
    section.append(el("p", "muted", "Nothing yet"));
    return section;
  }
  const list = el("div", "sw-list");
  for (const { kind, name, line } of rows) {
    const row = el("div", "sw-row");
    const words = el("span", "sw-tx");
    const title = el("span", "sw-name");
    title.append(el("b", null, name));
    words.append(title, el("small", null, line));
    row.append(iconTile(KIND_ICONS[kind] || "puzzle"), words);
    list.append(row);
  }
  section.append(list);
  return section;
}

// "Plugin · 3 items", "Skill", "Hook".
function itemLine(item) {
  if (item.kind !== "plugin") return KIND_WORDS[item.kind];
  return typeof item.count === "number" ? `Plugin · ${plural(item.count, "item", "items")}` : KIND_WORDS.plugin;
}

// A client: Kitden's words for it under its name, and what it loads: "Loads in every project" (or
// "Loads in <folder>"), its plugins, skills and hooks.
export function clientCard(id, c) {
  const client = c.answer.clients.find((one) => one.id === id) || { id, name: CLIENT_NAMES[id], words: "" };
  const items = c.answer.groups.flatMap((group) => group.items).filter((item) => (item.by || {})[id] === "on");
  const head = c.project ? `Loads in ${c.folder}` : "Loads in every project";
  return { kind: "Client", title: client.name, id: client.words, tile: headTile(mark(id)), list: itemList(head, items.map((item) => ({ kind: item.kind, name: item.name, line: itemLine(item) }))) };
}

// Where a link's change would be written, in words, never a path.
const WRITTEN = { plugin: (owner) => `${owner}'s settings`, skill: (owner) => `${owner}'s skills folder`, hook: (owner) => `${owner}'s settings` };

// A link: From, To, State and Written in, and what it means. A client's link to what it loads, a
// faint one through another client's folder, or a plugin's to what it holds.
export function connectionCard({ from, to }, c) {
  const title = [from.name, el("span", "arrow", " → "), to.name];
  const on = el("span", "fact-mark");
  on.append(lamp("on"), el("span", null, STATE_WORDS.on));
  if (from.kind !== "client") {
    const facts = [{ label: "From", value: from.name }, { label: "To", value: to.name }, { label: "State", value: FOLLOWS }, { label: "Written in", value: "The plugin's files" }];
    return { kind: "Connection", title, id: "Inside the plugin", facts, why: `${from.name} holds ${to.name}. It follows its plugin.` };
  }
  const item = to.item;
  const client = CLIENT_NAMES[from.client];
  const owner = (item.through || {})[from.client];
  const ownerName = owner ? CLIENT_NAMES[owner] : client;
  const facts = [{ label: "From", value: from.name }, { label: "To", value: to.name }, { label: "State", value: on, text: STATE_WORDS.on }, { label: "Written in", value: WRITTEN[item.kind](ownerName) }];
  const why = owner ? `${client} loads ${item.name} through ${ownerName}'s folder.` : `${client} loads ${item.name} ${c.project ? `in ${c.folder}` : "in every project"}.`;
  return { kind: "Connection", title, id: owner ? `Through ${ownerName}` : "Loaded by the client", facts, why };
}

// A marketplace's caption: its plugins on the map, and its source under Technical details.
export function marketplaceCard(group) {
  const items = group.items || [];
  const source = items.map((item) => (item.technical || {}).marketplace).find(Boolean);
  return { kind: "Marketplace", title: group.name, list: itemList("Plugins on the map", items.map((item) => ({ kind: "plugin", name: item.name, line: itemLine(item) }))), technical: techOf([{ title: "Source", summary: source }]) };
}

// The card of what the map shows for `id` (library-map.js libraryThing).
function cardOf(thing, c, id) {
  if (thing.link) return connectionCard(thing, c);
  const { block } = thing;
  if (block.kind === "client") return clientCard(block.client, c);
  if (block.kind === "group") return marketplaceCard(block.group);
  if (block.kind === "part") return partCard(block, c);
  if (block.kind === "plugin") return pluginCard(block.item, c, { addStep: () => addStep(id) });
  if (block.kind === "skill") return skillCard(block.item, c, { someStep: () => someStep(id) });
  return hookCard(block.item, c);
}

// Showing a card ----------------------------------------------------------------------------------

// Open the Details of what the map selected, beside the page, drawn from the map as it is now (also
// after Apply all). Gone from the map since: they close. `step` ("back") slides them in from a step.
export function showLibrary(id, { step = null } = {}) {
  const thing = libraryThing(id);
  if (!thing) {
    closePanel({ focus: false });
    return Promise.resolve();
  }
  const card = cardOf(thing, context(thing.answer), id);
  const nodes = openCard(card, { type: "library", id }, () => showLibrary(id), () => showLibrary(id), step);
  return Promise.resolve(nodes);
}

// Back from a step to its card, focus on the button that stepped there.
function backFrom(id, label) {
  return () => showLibrary(id, { step: "back" }).then(() => focusAfterStep(`action:${label}`));
}

// "Add <name> to the clients you pick": one row per client that can take it or has it already
// ("Has it already", off); Cursor is never a choice (D26: it gets plugins through Claude Code). Each
// tick is one plugin.install row; a ticked row says "In preview".
export function addNodes(item, back) {
  const has = (client) => Boolean((item.items || {})[client]);
  const clients = ["claude_code", "codex"].filter((client) => item.can.add.includes(client) || has(client));
  const picks = el("div", "picks");
  picks.setAttribute("role", "group");
  picks.setAttribute("aria-label", "Clients");
  for (const client of clients) {
    const body = addBody(item, client);
    picks.append(tickRow({ id: client, name: CLIENT_NAMES[client], line: has(client) ? "Has it already" : "Not added", onLine: IN_PREVIEW, look: mark(client), off: has(client), body, ticked: () => inTray(keyFor(body)) }));
  }
  const body = el("div", "body");
  body.append(el("p", "why", "Each client you tick waits in preview until Apply."), picks);
  const done = el("footer", "stack");
  done.append(button("Done", back, "btn"));
  return [stepHead(`Plugin · ${item.name}`, `Add ${item.name} to the clients you pick`, back), body, done];
}

// A step in the panel: its nodes come in as the next step (`dir`), or drawn again in place (null);
// what it shows stays the selection's, with the step named.
function openStep(id, name, nodes, dir, focus) {
  panelState.current = { type: "library", id, step: name };
  keepFrom(() => (name === "add" ? addStep(id, null) : someStep(id, null)), nodes, () => showLibrary(id));
  if (!dir) return swapContent(nodes);
  return stepTo(nodes, dir).then(() => focusAfterStep(focus));
}

function addStep(id, dir = "fwd") {
  const thing = libraryThing(id);
  if (!thing) return closePanel({ focus: false });
  const { item } = thing.block;
  const nodes = addNodes(item, backFrom(id, addLabel(item.can.add)));
  return openStep(id, "add", nodes, dir, `tick:${item.can.add[0]}`);
}

// "Turn off <name> in the projects you pick": the Gateway's project checklist (D13), one row per
// project whose folder is there; a project with skill settings of its own, or none yet, cannot be
// ticked, nor can any while a Claude Code skill rule for all projects waits in the tray. Each tick
// is one skill.rule row for Claude Code.
export function someNodes(item, c, back) {
  const known = (data.projects || []).filter((p) => c.rules.projects[p.id]);
  const rows = menuItems(known, "").filter((p) => p.id).map((p) => {
    const can = c.rules.projects[p.id];
    const body = projectBody(item, p.id);
    const ticked = () => inTray(keyFor(body));
    const waits = () => !ticked() && skillRuleWaits("all", c.answer);
    const line = () => PROJECT_LINES[can] || (waits() ? ALL_FIRST : "");
    return { id: p.id, name: p.name, line, off: () => can !== "ok" || waits(), body, ticked };
  });
  return projectChecklist({ crumb: `Skill · ${item.name}`, title: `Turn off ${item.name} in the projects you pick`, why: SOME_WHY, rows, back });
}

function someStep(id, dir = "fwd") {
  const thing = libraryThing(id);
  if (!thing) return closePanel({ focus: false });
  const nodes = someNodes(thing.block.item, context(thing.answer), backFrom(id, OFF_SOME));
  return openStep(id, "some", nodes, dir, "find");
}

// The map selected something (`id`), let go (null), or drew another project in place (`follow`).
// Letting go closes these Details (not a row's review: that belongs to the tray).
function heard(id, { follow = false } = {}) {
  if (follow) return followProject(id);
  if (id) return showLibrary(id);
  const now = panelState.current;
  if (isPanelOpen() && !(now && now.type === "row-review")) closePanel({ focus: false });
  return Promise.resolve();
}

// Another project drawn in place: Details follow the same thing, drawn again quietly for the new
// project, or close when it is not there. A step stays as it is; its Back draws the card anew.
function followProject(id) {
  const now = panelState.current;
  if (!isPanelOpen() || !now || now.type !== "library") return Promise.resolve();
  if (!id) {
    closePanel({ focus: false });
    return Promise.resolve();
  }
  if (now.step) return Promise.resolve();
  return drawQuietly(() => showLibrary(id));
}

export function initLibraryDetails() {
  onLibrarySelect((id, how) => {
    heard(id, how).catch((error) => console.error(error));
  });
}
