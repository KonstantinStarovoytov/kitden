// Details of the Library map (library-notes §3, with D25 and D26): a card builder for each thing the
// map selects (a plugin, a thing inside one, a skill, a hook, a client, a link and a marketplace's
// caption; on the Instructions tab a file and what it pulls in), each a plain object that
// detailsCard draws, so a test reads it without a page, and the steps "Add to <client>…" and "Turn
// off in some projects…" take. A press, a tick or a switch only
// adds a row to the tray; nothing is written before Apply. Paths stay under Technical details.
import { button, el, icon, joinWords, plural } from "./dom.js";
import { focusAfterStep, headTile, iconTile, lamp, openCard, pressOnce, projectChecklist, stepHead, tickRow, tiles } from "./gateway-details.js";
import { initLibraryAdd } from "./library-add.js";
import { addBody, decidedHere, importsOf, lampOf, libraryThing, onLibrarySelect, readers } from "./library-map.js";
import { copyBodies, offBodies, onBodies, removeBodies, skillOffBodies, skillRuleWaits } from "./library-rules.js";
import { closePanel, drawQuietly, followTray, isPanelOpen, keepFrom, panelState, review, stepTo, swapContent, technical } from "./panel.js";
import { ALL_PROJECTS, CLIENT_NAMES, CLIENT_ORDER, folderName, mark, menuItems, ORIGIN_WORDS, STATE_WORDS } from "./parts.js";
import { data, projectPath, state } from "./store.js";
import { inTray, keyFor, tray } from "./tray.js";

const IN_PREVIEW = "In preview";
const OFF_ALL = "Turn off for all projects…";
const OFF_SOME = "Turn off in some projects…";
const OFF_HERE = "Turn off in this project…";
// Takes the project's own key out of its local settings, so the shared rule applies there.
const USE_SHARED = "Use the shared rule…";
// A Codex skill only one project has: a rule for all projects that names this copy's path.
const OFF_COPY = "Turn off this copy in Codex…";
// A project row of the checklist whose own settings turn the skill off already.
const ALREADY_OFF = "Already off there";
// Why a project's own Claude Code skill has no "Turn off in this project…": the guard of
// changes/actions.py (NO_SKILL_MERGE), in words that offer nothing Kitden refuses.
const NO_MERGE = "Claude Code may not merge skill settings across files, so Kitden cannot turn it off in this project.";
const FOLLOWS = "Follows its plugin.";
const NO_PLUGIN = "None, a skill on its own";
const NO_PROJECT_SWITCH = "Codex has no switch for one project.";
const NO_CURSOR_SWITCH = "Cursor has no switch to turn off one skill.";
const SOME_WHY = "This turns it off in Claude Code. Codex and Cursor have no switch for one project.";
// Why a project cannot take a one-project skill rule (library_map.py `skill_rules`).
const PROJECT_LINES = { own: "Has its own skill settings", new: "No Claude Code settings yet" };
// A project whose rule file sits where Kitden does not write (`skill_rules.outside`: the folder,
// the engine's own test): no rule there, and one quiet line says why.
export const outsideWords = (folder) => `Claude Code keeps this project's local settings in ${folder}, where Kitden does not write.`;
// Why a tray cannot take both a skill rule for all projects and one for a project in Claude Code.
const ALL_FIRST = "Apply the rule for all projects first";
const SOME_FIRST = "Apply the project rules in preview first; then Claude Code can turn it off for all projects.";
// What a plugin holds, by its key in the answer: the word for one and for more.
const INSIDE_WORDS = [["skills", "skill", "skills"], ["commands", "command", "commands"], ["agents", "agent", "agents"], ["hooks", "hook", "hooks"], ["mcp_servers", "MCP server", "MCP servers"]];
const KIND_ICONS = { plugin: "puzzle", skill: "sparkles", hook: "webhook", file: "file-text" };
const KIND_WORDS = { plugin: "Plugin", skill: "Skill", hook: "Hook" };
const LAMP_WORDS = { on: STATE_WORDS.on, off: STATE_WORDS.off, unk: STATE_WORDS.unk };
// The Instructions tab (decisions "Instructions"): Kitden only reads these files.
const FILE_KIND = "Instruction file";
// A block of "Commands and agents" (`file.kind`): its kicker, and its word in a client's list.
const COMMAND_KINDS = { command: "Command", agent: "Agent" };
const IMPORT_KIND = "Imported file";
const READS_FILE = "Kitden only reads this file.";
const READS_IT = "Kitden only reads it.";
const IMPORTS_NOTHING = "It imports nothing.";
const MAY_ASK = "Claude Code may ask before it reads this.";
const NOT_FOUND = "Kitden could not find this file.";

// The same rows a link's × adds (library-rules.js).
export { offBodies, skillOffBodies, skillRuleWaits };

const inOrder = (clients) => [...clients].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
const names = (clients) => inOrder(clients).map((client) => CLIENT_NAMES[client] || client);
const clientsBy = (item, look) => Object.entries(item.by || {}).filter(([, state]) => state === look).map(([client]) => client);
const verb = (clients, one, more) => (clients.length > 1 ? more : one);

// What a card is drawn for: the answer, the picked project (its id and folder) and the rules of
// where a one-project skill rule can go.
export function context(answer, project = state.project, folder = folderName(projectPath())) {
  return { answer, project, folder, rules: { outside: {}, ...((answer && answer.skill_rules) || { some: false, projects: {} }) } };
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
  const here = c.project && (decidedHere(item) || item.source === ORIGIN_WORDS.project);
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

// "Turn off in this project…" for a skill the picked project decides (its own skill, or its rule
// for a skill of all projects): Claude Code has it on there and the project can take a rule. A
// rule for all projects would write the user's file instead (library_map.py `_can`).
export function skillHereBody(item, c) {
  const on = (item.by || {}).claude_code === "on" && (item.items || {}).claude_code;
  const decides = !shared(item) || decidedHere(item, "claude_code");
  return c.project && on && decides && c.rules.some && c.rules.projects[c.project] === "ok" ? projectBody(item, c.project) : null;
}

// "Use the shared rule…": in a project whose local settings decide for Claude Code (`can.local`),
// one skill.rule row that takes that key out; else null. The committed file is never changed here.
export function sharedBody(item, c) {
  const target = ((item.items || {}).claude_code || [])[0];
  const local = ((item.can && item.can.local) || []).includes("claude_code");
  return c.project && local && target ? { action: "skill.rule", targets: [{ client: "claude_code", item: target }], params: { scope: "project", project: c.project, off: false } } : null;
}

// Why a project's own Claude Code skill gets no "Turn off in this project…": a file with skill
// settings blocks the rule (as changes/actions.py refuses it); else null.
function mergeLine(item, c) {
  const can = c.rules.projects[c.project];
  const blocked = (!c.rules.some || can === "own") && can !== "outside";
  return c.project && !shared(item) && (item.by || {}).claude_code === "on" && blocked ? el("p", "muted", NO_MERGE) : null;
}

// "Turn off in some projects…" for a skill of all projects that Claude Code has, while the user
// settings hold no skillOverrides (`rules.some`) and some project can take the rule.
export function offersSome(item, c) {
  return Boolean(shared(item) && (item.items || {}).claude_code && c.rules.some && Object.values(c.rules.projects).includes("ok"));
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
  const waiting = () => list().every(queued);
  pressOnce(node, async () => {
    if (waiting()) return;
    for (const body of list()) if (!queued(body)) await review(body);
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

// The tray holds this very row: its key, and the same `off` (a skill rule's on and off share a key).
function queued(body) {
  const off = (body.params || {}).off;
  return tray.rows.some((row) => row.key === keyFor(body) && (row.body.params || {}).off === off);
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

// "Turn on in Claude Code…" for each client that has a plugin off, and "Remove from Codex…" for each
// client whose own entry Kitden can remove, under More: the same rows as the old Details' buttons
// and a link's ×.
const onLabel = (client) => `Turn on in ${CLIENT_NAMES[client]}…`;
const removeLabel = (client) => `Remove from ${CLIENT_NAMES[client]}…`;
const onActions = (item) => onBodies(item).map(({ client, body }) => ({ label: onLabel(client), body }));
const removeActions = (item) => removeBodies(item).map(({ client, body }) => ({ label: removeLabel(client), body }));
// They act only on a client's own entry for all projects. Where the picked project's own settings
// decide (`can.project`), one quiet line says so instead: its local settings (`can.local`), its
// shared, committed settings (`can.shared`), or its own copy.
export const fromProject = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s own settings.`;
export const fromLocal = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s local settings.`;
export const fromShared = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s shared settings.`;
function projectLine(item, c) {
  const can = item.can || {};
  const clients = can.project || [];
  if (!clients.length || !c.folder) return null;
  const line = (client) => ((can.local || []).includes(client) ? fromLocal : (can.shared || []).includes(client) ? fromShared : fromProject)(client, c.folder);
  return el("p", "muted", inOrder(clients).map(line).join(" "));
}
// In a project whose rule file Kitden does not write, for an item Claude Code has: one quiet line.
function outsideLine(item, c) {
  const folder = c.project && c.rules.projects[c.project] === "outside" && (item.items || {}).claude_code ? c.rules.outside[c.project] : null;
  return folder ? el("p", "muted", outsideWords(folder)) : null;
}
// The nodes under a card's actions, in one box when there are several.
function afterOf(...nodes) {
  const shown = nodes.filter(Boolean);
  if (shown.length < 2) return shown[0] || null;
  const box = el("div");
  box.append(...shown);
  return box;
}

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
  if (here) actions.push({ label: OFF_HERE, node: rowsButton(OFF_HERE, [here]) });
  const back = sharedBody(item, c);
  if (back) actions.push({ label: USE_SHARED, node: rowsButton(USE_SHARED, [back]) });
  actions.push(...onActions(item));
  const tech = item.technical || {};
  return { kind: KIND_WORDS.plugin, title: item.name, id: item.source, tile: kindTile("plugin"), facts, why: loadsSay(item, c), actions, more: removeActions(item), after: afterOf(projectLine(item, c), outsideLine(item, c)), technical: techOf([{ title: "Plugin folder", path: tech.path }, { title: "Marketplace", summary: tech.marketplace }]) };
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
  if (here) after = rowsButton(`Turn off ${plugin.name} in this project…`, [here], "btn ghost small");
  return { kind: block.label.words, title: block.name, id: plugin.name, tile: iconTile(block.label.icon), facts, why: FOLLOWS, after };
}

// A skill on its own: Plugin ("None, a skill on its own"), State, Comes from, Source and Clients;
// where it loads, and which clients have no switch; "Turn off for all projects…", "Turn off in
// this project…" where the project decides, and "Turn off in some projects…" (the project
// checklist, `someStep`); its file under Technical details.
export function skillCard(item, c, { someStep = () => {} } = {}) {
  const source = el("span", "fact-mark");
  source.append(icon(item.source === ORIGIN_WORDS.project ? "folder" : "user-round", 13), el("span", null, item.source));
  const facts = [{ label: "Plugin", value: NO_PLUGIN, quiet: true }, stateFact(item), comesFrom(item, c), { label: "Source", value: source, text: item.source }, clientsFact(item, { count: true })];
  const actions = [];
  if (offBodies(item).length) actions.push({ label: OFF_ALL, node: rowsButton(OFF_ALL, () => skillOffBodies(item, c.answer)) });
  const here = skillHereBody(item, c);
  if (here) actions.push({ label: OFF_HERE, node: rowsButton(OFF_HERE, () => (skillRuleWaits("all", c.answer) ? [] : [here])) });
  const back = sharedBody(item, c);
  if (back) actions.push({ label: USE_SHARED, node: rowsButton(USE_SHARED, [back]) });
  const copy = copyBodies(item);
  if (copy.length) actions.push({ label: OFF_COPY, node: rowsButton(OFF_COPY, copy) });
  if (offersSome(item, c)) actions.push({ label: OFF_SOME, run: someStep });
  const notes = [];
  if (shared(item) && (item.by || {}).codex === "on") notes.push(NO_PROJECT_SWITCH);
  if ((item.by || {}).cursor === "on") notes.push(NO_CURSOR_SWITCH);
  const why = [loadsSay(item, { folder: c.project ? c.folder : "", noun: "this skill" }), ...notes].join(" ");
  const claude = ((item.can && item.can.off) || []).includes("claude_code");
  const after = afterOf(projectLine(item, c), outsideLine(item, c), mergeLine(item, c), claude ? trayNote(SOME_FIRST, () => skillRuleWaits("project", c.answer)) : null);
  return { kind: KIND_WORDS.skill, title: item.name, id: item.source, tile: kindTile("skill"), facts, why, actions, more: removeActions(item), after, technical: techOf([{ title: "Skill file", path: (item.technical || {}).path }]) };
}

// What Claude Code keeps in the account (the List's "Claude account plugins and connectors"): its
// name, Unknown, and the reason Kitden gives for it. Kitden cannot change it.
export function accountCard(block) {
  return { kind: KIND_WORDS.plugin, title: block.name, tile: kindTile("plugin"), facts: [stateFact(block.item)], why: block.reason || null };
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
// "Loads in <folder>"), its plugins, skills and hooks, or on the Instructions tab the files it reads.
export function clientCard(id, c) {
  const client = c.answer.clients.find((one) => one.id === id) || { id, name: CLIENT_NAMES[id], words: "" };
  const head = c.project ? `Loads in ${c.folder}` : "Loads in every project";
  return { kind: "Client", title: client.name, id: client.words, tile: headTile(mark(id)), list: itemList(head, clientRows(id, c.answer)) };
}

function clientRows(id, answer) {
  return answer.groups.flatMap((group) => [
    ...(group.items || []).filter((item) => (item.by || {})[id] === "on").map((item) => ({ kind: item.kind, name: item.name, line: itemLine(item) })),
    ...(group.files || []).filter((file) => (file.by || {})[id]).map((file) => ({ kind: "file", name: file.name, line: COMMAND_KINDS[file.kind] || "File" })),
  ]);
}

// An instruction file: Read by, Through (Claude Code reads AGENTS.md in place of a CLAUDE.md) and
// Size ("42 lines"; none for a file longer than Kitden reads, nor for a folder of rules); what it
// brings in; its path and first lines (a folder: its rules) under Technical details. A command or an
// agent says only that Kitden reads it: it brings nothing in.
export function fileCard(block, c) {
  const { file } = block;
  const facts = [{ label: "Read by", value: readers(file).map((client) => CLIENT_NAMES[client]).join(", ") }];
  if (file.through) facts.push({ label: "Through", value: file.through });
  if (typeof file.size === "number") facts.push({ label: "Size", value: plural(file.size, "line", "lines") });
  const pulls = importsOf(file).length;
  const command = COMMAND_KINDS[file.kind];
  const why = command ? READS_FILE : `${READS_FILE} ${pulls ? `It brings in ${pulls} more.` : IMPORTS_NOTHING}`;
  const tech = file.technical || {};
  const title = typeof file.count === "number" ? "Rules folder" : "File";
  const rows = tech.path ? [{ title, path: tech.path, preview: tech.lines && tech.lines.length ? tech.lines : null }] : [];
  return { kind: command || FILE_KIND, title: file.name, id: block.meta, tile: iconTile("file-text"), facts, why, technical: rows.length ? technical(rows) : null };
}

// A file a CLAUDE.md pulls in: which files bring it in, and that Kitden only reads it; Claude Code
// may ask before it reads one outside the project. One Kitden could not find says so.
export function importCard(block, c) {
  const { imported } = block;
  const files = (c.answer.groups || []).flatMap((group) => group.files || []).filter((file) => (imported.by_files || []).includes(file.id));
  const by = [...new Set(files.map((file) => file.name))];
  const why = imported.missing ? NOT_FOUND : [READS_IT, imported.outside && MAY_ASK].filter(Boolean).join(" ");
  const path = (imported.technical || {}).path;
  return { kind: IMPORT_KIND, title: imported.name, id: by.length ? `Brought in by ${joinWords(by)}` : null, tile: iconTile("scroll-text"), why, technical: path ? technical([{ title: "File", path }]) : null };
}

// A link on the Instructions tab: a client reads a file, or a file brings in another.
export function readsCard({ from, to }) {
  const title = [from.name, el("span", "arrow", " → "), to.name];
  const facts = [{ label: "From", value: from.name }, { label: "To", value: to.name }];
  if (from.kind === "client") return { kind: "Connection", title, id: "Read by the client", facts, why: `${from.name} reads ${to.name}. ${READS_FILE}` };
  return { kind: "Connection", title, id: "An import", facts, why: `${from.name} brings in ${to.name}. ${READS_IT}` };
}

// Why a Cursor plugin's link has no ×: Cursor keeps its plugins in its own app. The words are
// clients/cursor.py CURSOR_HINT (checked 2026-10-22, cursor.com/docs/plugins).
const CURSOR_PLUGINS = "Cursor keeps its plugins in its own database. Remove it in Cursor: Customize → Plugins.";

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
  const loads = owner ? `${client} loads ${item.name} through ${ownerName}'s folder.` : `${client} loads ${item.name} ${c.project ? `in ${c.folder}` : "in every project"}.`;
  const why = item.kind === "plugin" && from.client === "cursor" && !owner ? `${loads} ${CURSOR_PLUGINS}` : loads;
  return { kind: "Connection", title, id: owner ? `Through ${ownerName}` : "Loaded by the client", facts, why };
}

// A marketplace's caption: its plugins on the map, and its source under Technical details.
export function marketplaceCard(group) {
  const items = group.items || [];
  const source = items.map((item) => (item.technical || {}).marketplace).find(Boolean);
  return { kind: "Marketplace", title: group.name, list: itemList("Plugins on the map", items.map((item) => ({ kind: "plugin", name: item.name, line: itemLine(item) }))), technical: techOf([{ title: "Source", summary: source }]) };
}

// The card of what the map shows for `id` (library-map.js libraryThing).
const INSTRUCTION_CARDS = { file: fileCard, import: importCard };
function cardOf(thing, c, id) {
  if (thing.link) return INSTRUCTION_CARDS[thing.to.kind] ? readsCard(thing) : connectionCard(thing, c);
  const { block } = thing;
  if (INSTRUCTION_CARDS[block.kind]) return INSTRUCTION_CARDS[block.kind](block, c);
  if (block.kind === "client") return clientCard(block.client, c);
  if (block.kind === "account") return accountCard(block);
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
// project whose folder is there; a project that turns it off already ("Already off there", `off_in`),
// one with skill settings of its own, or none yet, cannot be ticked, nor can any while a Claude Code
// skill rule for all projects waits in the tray. Each tick is one skill.rule row for Claude Code.
export function someNodes(item, c, back) {
  const known = (data.projects || []).filter((p) => c.rules.projects[p.id]);
  const rows = menuItems(known, "").filter((p) => p.id).map((p) => {
    const can = c.rules.projects[p.id];
    const body = projectBody(item, p.id);
    const ticked = () => queued(body);
    const waits = () => !ticked() && skillRuleWaits("all", c.answer);
    const already = (item.off_in || []).includes(p.id);
    const away = can === "outside" ? outsideWords(c.rules.outside[p.id]) : null;
    const line = () => (already ? ALREADY_OFF : away || PROJECT_LINES[can] || (waits() ? ALL_FIRST : ""));
    return { id: p.id, name: p.name, line, off: () => already || can !== "ok" || waits(), body, ticked };
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
  // The map's "+ Add" opens the add panel.
  initLibraryAdd();
}
