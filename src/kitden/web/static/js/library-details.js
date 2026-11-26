// Details of the Library map (library-notes §3, with D25 and D26): a card builder for each thing the
// map selects (a plugin, a thing inside one, a skill, a hook, a client, a link and a marketplace's
// caption; on the Instructions tab a file and what it pulls in), each a plain object that
// detailsCard draws, so a test reads it without a page, and the steps "Add to <client>…" and "Turn
// off in some projects…" take. A press, a tick or a switch only
// adds a row to the tray; nothing is written before Apply. Paths stay under Technical details.
import { getJson, query } from "./api.js";
import { $, button, el, icon, joinWords, plural } from "./dom.js";
import { IN_PREVIEW, previewLook } from "./details.js";
import { focusAfterStep, headTile, iconTile, lamp, openCard, pressOnce, projectChecklist, stepHead, tickRow, tiles } from "./gateway-details.js";
import { initLibraryAdd } from "./library-add.js";
import { addBody, decidedHere, importsOf, lampOf, libraryThing, onLibrarySelect, readers } from "./library-map.js";
import { copyBodies, offBodies, onBodies, removeBodies } from "./library-rules.js";
import { closePanel, drawQuietly, followTray, isPanelOpen, keepFrom, panelState, review, stepTo, swapContent, technical } from "./panel.js";
import { ALL_PROJECTS, byClientOrder, CLIENT_NAMES, folderName, mark, menuItems, ORIGIN_WORDS, SKILL_STATE_WORDS, STATE_WORDS } from "./parts.js";
import { openContextGroup } from "./context.js";
import { takesLine } from "./context-groups.js";
import { current, data, loadContext, projectPath, state } from "./store.js";
import { say } from "./toast.js";
import { inTray, keyFor, ruleState, trayRow } from "./tray.js";
import { skillSwitch } from "./skill-switch.js";

export const OFF_ALL = "Turn off for all projects…";
const OFF_SOME = "Turn off in some projects…";
const OFF_HERE = "Turn off in this project…";
export const ON_ALL = "Turn on for all projects…";
const ON_HERE = "Turn on in this project…";
// Takes the project's own key out of its local settings, so the shared rule applies there.
const USE_SHARED = "Use the shared rule…";
// A Codex skill only one project has: a rule for all projects that names this copy's path.
const OFF_COPY = "Turn off this copy in Codex…";
// A project row of the checklist whose own settings turn the skill off already.
const ALREADY_OFF = "Already off there";
const FOLLOWS = "Follows its plugin.";
const NO_PLUGIN = "None, a skill on its own";
const NO_PROJECT_SWITCH = "Codex has no switch for one project.";
const NO_CURSOR_SWITCH = "Cursor has no switch to turn off one skill.";
const SOME_WHY = "This turns it off in Claude Code. Codex and Cursor have no switch for one project.";
// Why a project cannot take a one-project skill rule (library_map.py `skill_rules`).
const PROJECT_LINES = { new: "No .claude folder yet; Kitden makes none" };
// A project whose rule file sits where Kitden does not write (`skill_rules.outside`: the folder,
// the engine's own test): no rule there, and one quiet line says why.
const outsideWords = (folder) => `Claude Code keeps this project's local settings in ${folder}, where Kitden does not write.`;
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
// "Commands…" (FR-029): what the developer runs to install, update or move it, never this page.
const COMMANDS = "Commands…";
const RUN_YOURSELF = "You run these yourself. This page never runs them.";
const NO_COMMANDS = "No commands for this item.";
const NOT_LOADED = "Could not load the commands.";
const COPY = "Copy";
const COPIED = "Copied";
const NOT_COPIED = "Could not copy";

const inOrder = (clients) => [...clients].sort(byClientOrder);
const names = (clients) => inOrder(clients).map((client) => CLIENT_NAMES[client] || client);
const clientsBy = (item, look) => Object.entries(item.by || {}).filter(([, state]) => state === look).map(([client]) => client);
const verb = (clients, one, more) => (clients.length > 1 ? more : one);

// What a card is drawn for: the answer, the picked project (its id and folder) and the rules of
// where a one-project skill rule can go.
export function context(answer, project = state.project, folder = folderName(projectPath())) {
  return { answer, project, folder, rules: { outside: {}, ...((answer && answer.skill_rules) || { projects: {} }) } };
}

// "3 skills · 1 command", from what Kitden read inside a plugin; null when it read nothing.
function insideWords(inside) {
  if (!inside) return null;
  const parts = INSIDE_WORDS.filter(([key]) => (inside[key] || []).length).map(([key, one, more]) => plural(inside[key].length, one, more));
  return parts.length ? parts.join(" · ") : "Nothing";
}

// Where an item loads, in one or more sentences, from Kitden's own facts: "Claude Code and Codex
// load it in every project. Cursor gets it through Claude Code." `noun` is "it" or "this skill".
function loadsSay(item, { folder = "", noun = "it" } = {}) {
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
  lines.push(...(item.off_where || []));
  const unknown = clientsBy(item, "unknown");
  if (unknown.length) lines.push(`Kitden can't tell whether ${joinWords(names(unknown))} ${verb(unknown, "loads", "load")} it.`);
  if (clientsBy(item, "via").length) lines.push("Cursor gets it once Claude Code adds it.");
  return lines.join(" ") || "No client loads it.";
}

// The facts every item shares.
// On in one client and off in another, it names both ("On in Cursor · Off in Claude Code"), so the
// header never says On for a skill a client has off.
function stateFact(item) {
  const look = lampOf(item);
  const on = clientsBy(item, "on");
  const off = clientsBy(item, "off");
  const words = on.length && off.length ? `On in ${names(inOrder(on)).join(", ")} · Off in ${names(inOrder(off)).join(", ")}` : LAMP_WORDS[look];
  const value = el("span", "fact-mark");
  value.append(lamp(look), el("span", null, words));
  return { label: "State", value, text: words };
}

// The clients that load it, by their tiles and names ("Claude Code, Cursor"), or by how many.
function clientsFact(item, { count = false } = {}) {
  // An item that is off where it is set up names those clients: it is there, not "None yet".
  const on = clientsBy(item, "on");
  const clients = inOrder(on.length ? on : clientsBy(item, "off"));
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
  return c.project && on && c.rules.projects[c.project] === "ok" ? projectBody(item, c.project) : null;
}

// A skill of all projects, not only of the picked one.
const shared = (item) => item.source !== ORIGIN_WORDS.project;

// "Turn off in this project…" for a skill the picked project decides (its own skill, or its rule
// for a skill of all projects): Claude Code has it on there and the project can take a rule. A
// rule for all projects would write the user's file instead (library_map.py `_can`).
export function skillHereBody(item, c) {
  const on = (item.by || {}).claude_code === "on" && (item.items || {}).claude_code;
  const decides = !shared(item) || decidedHere(item, "claude_code");
  return c.project && on && decides && c.rules.projects[c.project] === "ok" ? projectBody(item, c.project) : null;
}

// "Use the shared rule…": in a project whose local settings decide for Claude Code (`can.local`),
// one skill.rule row that takes that key out; else null. The committed file is never changed here.
export function sharedBody(item, c) {
  const target = ((item.items || {}).claude_code || [])[0];
  const local = ((item.can && item.can.local) || []).includes("claude_code");
  return c.project && local && target ? { action: "skill.rule", targets: [{ client: "claude_code", item: target }], params: { scope: "project", project: c.project, off: false } } : null;
}

// "Turn off in some projects…" for a skill of all projects that Claude Code has, while some
// project can take the rule.
export function offersSome(item, c) {
  return Boolean(shared(item) && (item.items || {}).claude_code && Object.values(c.rules.projects).includes("ok"));
}

// A button that adds every row of `bodies` to the tray, one after the other. While they all wait
// there it says "In preview" and takes no press, as a preview button does (details.js).
// `goes`: what goes with each row, said on it (a plugin's parts).
function rowsButton(label, bodies, look = "btn", goes = null) {
  const words = el("span", "cut", label);
  const node = el("button", look);
  node.type = "button";
  node.title = label;
  node.dataset.focus = `action:${label}`;
  node.append(words);
  const waiting = () => bodies.every(queued);
  pressOnce(node, async () => {
    if (waiting()) return;
    for (const body of bodies) if (!queued(body)) await review(body, { goes });
  });
  followTray(node, keyFor(bodies[0] || {}), () => previewLook(node, words, label, waiting()));
  return node;
}

// The copies a client loads of one thing (`item.copies`, library_map.py): each copy's folder (a
// plugin's marketplace) and whose it is, and "Keep this one…", which adds a Remove of every other
// copy to the tray. A copy Kitden cannot remove leaves its others without the button. Null with none.
const KEEP_ONE = "Keep this one…";
function copiesNode(item) {
  const copies = item.copies || {};
  const clients = Object.keys(copies).sort(byClientOrder);
  if (!clients.length) return null;
  const box = el("div", "copies");
  for (const client of clients) {
    const { say, list } = copies[client];
    const rows = el("ul", "copy-list");
    rows.setAttribute("aria-label", `Copies in ${CLIENT_NAMES[client]}`);
    list.forEach((copy, index) => {
      const row = el("li", "copy-row");
      row.append(el("span", "copy-where", `${copy.where} · ${copyOwner(copy, client)}`));
      const others = list.filter((_, at) => at !== index);
      const bodies = others.filter((other) => other.remove).map((other) => ({ action: item.kind === "plugin" ? "plugin.remove" : "skill.remove", targets: [{ item: other.remove }], params: {} }));
      if (bodies.length && bodies.length === others.length) {
        const keep = rowsButton(KEEP_ONE, bodies);
        keep.dataset.focus = `keep:${client}:${index}`;
        row.append(keep);
      }
      rows.append(row);
    });
    box.append(el("p", "muted", say), rows);
  }
  return box;
}
// Whose a copy is: the client's own, a folder clients share, or another client's (removing it there
// removes it for that client too, which the tray row says).
function copyOwner(copy, client) {
  if (copy.owner === client) return `${CLIENT_NAMES[client]}'s own`;
  const also = (copy.also || []).map((one) => CLIENT_NAMES[one]);
  if (copy.owner === "shared") return also.length ? `shared with ${joinWords(also)}` : "shared";
  return `${CLIENT_NAMES[copy.owner] || copy.owner}'s`;
}

// The tray holds this very row: its key, and the same state (a skill rule's states share a key).
export function queued(body) {
  const row = trayRow(keyFor(body));
  return Boolean(row) && ruleState(row.body.params) === ruleState(body.params);
}

// The cards ---------------------------------------------------------------------------------------

// "Remove from Codex…" for each client whose own entry Kitden can remove, under More: the same rows
// as a link's ×.
const removeLabel = (client) => `Remove from ${CLIENT_NAMES[client]}…`;

// What goes with a plugin's switch, as Context's own switch says it: "Turns off all of plug: 2
// skills, 1 command and 3 agents." Null for a skill, or when Kitden read nothing inside.
const GOES_PARTS = [["skills", "skill", "skills"], ["commands", "command", "commands"], ["agents", "agent", "agents"], ["hooks", "hook", "hooks"], ["mcp_servers", "MCP server", "MCP servers"]];
function goesWords(item, way) {
  const inside = item.kind === "plugin" ? item.inside : null;
  const parts = GOES_PARTS.filter(([key]) => ((inside || {})[key] || []).length).map(([key, one, more]) => plural(inside[key].length, one, more));
  return parts.length ? `Turns ${way} all of ${item.name}: ${joinWords(parts)}.` : null;
}
const removeActions = (item) => removeBodies(item).map(({ client, body }) => ({ label: removeLabel(client), body }));
// They act only on a client's own entry for all projects. Where the picked project's own settings
// decide (`can.project`), one quiet line says so instead: its local settings (`can.local`), its
// shared, committed settings (`can.shared`), or its own copy.
const fromProject = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s own settings.`;
const fromLocal = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s local settings.`;
const fromShared = (client, folder) => `${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s shared settings.`;
function projectLine(item, c) {
  const can = item.can || {};
  // In a project whose rule file Kitden does not write, the outside line says it for Claude Code.
  const clients = (can.project || []).filter((client) => client !== "claude_code" || !outsideFolder(item, c));
  if (!clients.length || !c.folder) return null;
  // A rule in the repository root's local file names the root's folder (`can.local_in`).
  const line = (client) => ((can.local || []).includes(client) ? fromLocal(client, (can.local_in || {})[client] || c.folder) : ((can.shared || []).includes(client) ? fromShared : fromProject)(client, c.folder));
  return el("p", "muted", inOrder(clients).map(line).join(" "));
}
// In a project whose rule file Kitden does not write, for an item Claude Code has: one quiet line.
const outsideFolder = (item, c) => (c.project && c.rules.projects[c.project] === "outside" && (item.items || {}).claude_code ? c.rules.outside[c.project] : null);
function outsideLine(item, c) {
  const folder = outsideFolder(item, c);
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

// What a plugin or a skill takes of Claude Code's and Codex's skill lists, as the Context page counts
// it, each with a link that opens its group there. The Context page's read is asked for once when
// it is not there yet (an Apply drops it, store.js reload), one read at a time; these Details are
// drawn again quietly when it comes.
const SHOW_IN_CONTEXT = "Show in Context";
let contextAsked = null;
function takesNode(item, id) {
  const model = current("context");
  if (!model) {
    if (!contextAsked) {
      contextAsked = loadContext().then(() => {
        const now = panelState.current;
        if (current("context") && isPanelOpen() && now && now.type === "library" && now.id === id && !now.step) drawQuietly(() => showLibrary(id));
      }).catch(() => {}).finally(() => { contextAsked = null; });
    }
    return null;
  }
  const lines = [];
  for (const card of model.clients || []) {
    const own = (item.items || {})[card.client];
    if (!own || !own.length) continue;
    const match = item.kind === "plugin" ? { plugin: item.plugin } : item.kind === "part" ? { plugin: item.plugin, skill: item.skill } : { items: own };
    const line = takesLine(card, match);
    if (line) lines.push(line);
  }
  if (!lines.length) return null;
  const box = el("div", "takes");
  for (const line of lines) {
    const row = el("p", "muted");
    const link = button(SHOW_IN_CONTEXT, () => { closePanel({ keepSelection: true, focus: false }); openContextGroup(line.client, line.group); }, "lnk");
    link.setAttribute("aria-label", `${SHOW_IN_CONTEXT}: ${line.say}`);
    link.dataset.focus = `takes:${line.client}`;
    row.append(`${line.say} `, link);
    box.append(row);
  }
  return box;
}

// "Add to Codex…", or "Add to Claude Code or Codex…" when both can take it.
export const addLabel = (clients) => `Add to ${names(clients).join(" or ")}…`;

// A plugin: State, Inside, Clients and Comes from; where it loads; "Add to <client>…" (a step to a
// checklist, `addStep`), "Turn off for all projects…" and, in a project, "Turn off in this
// project…"; its folder and its marketplace's source under Technical details. A plugin of the
// Claude account adds its `note`: the app adds it, and where its switch is.
export function pluginCard(item, c, { addStep = () => {}, commandsStep = () => {} } = {}) {
  const inside = insideWords(item.inside);
  const facts = [stateFact(item), { label: "Inside", value: inside || "Not known", quiet: !inside }, clientsFact(item), comesFrom(item, c)];
  const actions = [];
  const adds = (item.can && item.can.add) || [];
  if (adds.length) actions.push({ label: addLabel(adds), run: addStep, primary: true });
  for (const one of pluginSwitches(item, c)) actions.push({ label: one.label, node: rowsButton(one.label, one.bodies, "btn", one.goes) });
  const tech = item.technical || {};
  const more = [...removeActions(item), ...commandsAction(pluginEntries(item), commandsStep)];
  // Cursor's own plugin has no switch or Remove here: its Details say where it is changed.
  const cursorOnly = (item.by || {}).cursor && !(item.through || {}).cursor && !Object.keys(item.by).some((client) => client !== "cursor");
  return { kind: KIND_WORDS.plugin, title: item.name, id: item.source, tile: kindTile("plugin"), facts, list: copiesNode(item), why: [loadsSay(item, c), item.note, item.no_switch, cursorOnly ? CURSOR_REMOVES : null].filter(Boolean).join(" "), actions, more, after: afterOf(projectLine(item, c), outsideLine(item, c)), technical: techOf([{ title: "Plugin folder", path: tech.path }, { title: "Marketplace", summary: tech.marketplace }]) };
}

// A plugin's switches, the one answer Library Details and Context's group header read (`only`: one
// client's): "Turn off for all projects…" and "Turn on for all projects…" (its own entry, every
// client at once), in a project "Turn off in this project…" and "Use the shared rule…" (Claude
// Code's rule there) and Codex's own table there ("Turn off in this project…", "Turn on in this
// project…", `can.project_switch`). Each is `{ label, bodies, goes }`.
export function pluginSwitches(item, c, only = null) {
  const mine = (client) => !only || client === only;
  const out = [];
  const add = (label, bodies, goes = null) => { if (bodies.length) out.push({ label, bodies, goes }); };
  add(OFF_ALL, offBodies(item).filter((b) => mine(clientOf(item, b))), goesWords(item, "off"));
  if (mine("claude_code")) {
    const here = hereBody(item, c);
    if (here) add(OFF_HERE, [here]);
    const back = sharedBody(item, c);
    if (back) add(USE_SHARED, [back]);
  }
  const own = projectSwitchBodies(item, c).filter((one) => mine(one.client));
  add(OFF_HERE, own.filter((one) => one.body.action === "plugin.disable").map((one) => one.body));
  add(ON_HERE, own.filter((one) => one.body.action === "plugin.enable").map((one) => one.body));
  add(ON_ALL, onBodies(item).filter((one) => mine(one.client)).map((one) => one.body), goesWords(item, "on"));
  return out;
}

// The client a plugin row is for, by its item.
const clientOf = (item, body) => Object.keys(item.items || {}).find((client) => item.items[client].includes((body.targets[0] || {}).item));

// Codex's own table in the picked project turns the plugin on or off there (`can.project_switch`,
// its deciding item first): Kitden writes that project's `.codex/config.toml`.
function projectSwitchBodies(item, c) {
  if (!c.project) return [];
  return ((item.can && item.can.project_switch) || []).map((client) => {
    const action = (item.by || {})[client] === "on" ? "plugin.disable" : "plugin.enable";
    return { client, body: { action, targets: [{ item: item.items[client][0] }], params: {} } };
  });
}

// A thing a plugin holds: Plugin, Kind, Source and Clients, and "Follows its plugin." It has no
// switch (D25); in a project a skill has one quiet line that turns its plugin off there.
export function partCard(block, c) {
  const plugin = block.plugin;
  const tile = el("span", "fact-mark");
  tile.append(icon("puzzle", 13), el("span", null, plugin.name));
  const facts = [{ label: "Plugin", value: tile, text: plugin.name }, { label: "Kind", value: block.label.words }, { label: "Source", value: plugin.source }, clientsFact(plugin, { count: true })];
  // Its plugin's own switches, as on the plugin's Details and on Context (the switch is the plugin's).
  const actions = pluginSwitches(plugin, c).map((one) => ({ label: one.label, node: rowsButton(one.label, one.bodies, "btn", one.goes) }));
  return { kind: block.label.words, title: block.name, id: plugin.name, tile: iconTile(block.label.icon), facts, why: actions.length ? `${FOLLOWS} Its switch is ${plugin.name}'s, for the whole plugin.` : FOLLOWS, actions };
}

// A skill on its own: Plugin ("None, a skill on its own"), State, Comes from, Source and Clients;
// where it loads, and which clients have no switch; "Turn off for all projects…", "Turn off in
// this project…" where the project decides, and "Turn off in some projects…" (the project
// checklist, `someStep`); its file under Technical details.
export function skillCard(item, c, { someStep = () => {}, addStep = () => {} } = {}) {
  const source = el("span", "fact-mark");
  source.append(icon(item.source === ORIGIN_WORDS.project ? "folder" : "user-round", 13), el("span", null, item.source));
  const facts = [{ label: "Plugin", value: NO_PLUGIN, quiet: true }, stateFact(item), comesFrom(item, c), { label: "Source", value: source, text: item.source }, clientsFact(item, { count: true })];
  const own = SKILL_STATE_WORDS[item.skill_state];
  if (own) facts.splice(2, 0, { label: "Loads", value: own, text: own });
  const actions = [];
  // Add to a client: the same step as a plugin's, for a skill the skill catalog can copy (the List's
  // "+ Add" and a drag do the same).
  const adds = item.skill ? (item.can && item.can.add) || [] : [];
  if (adds.length) actions.push({ label: addLabel(adds), run: addStep, primary: true });
  // Its own switch for all projects, per client: the same one Context's Details draw.
  const switches = skillSwitches(item);
  for (const one of skillProjectSwitches(item, c)) actions.push({ label: one.label, node: rowsButton(one.label, one.bodies) });
  if (offersSome(item, c)) actions.push({ label: OFF_SOME, run: someStep });
  const notes = [];
  if (shared(item) && (item.by || {}).codex === "on") notes.push(NO_PROJECT_SWITCH);
  if ((item.by || {}).cursor === "on") notes.push(NO_CURSOR_SWITCH);
  const why = [loadsSay(item, { folder: c.project ? c.folder : "", noun: "this skill" }), ...notes].join(" ");
  const after = afterOf(projectLine(item, c), outsideLine(item, c));
  return { kind: KIND_WORDS.skill, title: item.name, id: item.source, tile: kindTile("skill"), facts, why, list: afterOf(copiesNode(item), switches), actions, more: removeActions(item), after, technical: techOf([{ title: "Skill file", path: (item.technical || {}).path }]) };
}

// A skill's switches for one project, the one answer the Library's and Context's Details read
// (`only`: one client's): "Turn off in this project…" and "Use the shared rule…" (Claude Code's
// rule there), and "Turn off this copy in Codex…". Each is `{ label, bodies }`.
export function skillProjectSwitches(item, c, only = null) {
  const out = [];
  if (!only || only === "claude_code") {
    const here = skillHereBody(item, c);
    if (here) out.push({ label: OFF_HERE, bodies: [here] });
    const back = sharedBody(item, c);
    if (back) out.push({ label: USE_SHARED, bodies: [back] });
  }
  const copy = copyBodies(item).filter((body) => !only || body.targets[0].client === only);
  if (copy.length) out.push({ label: OFF_COPY, bodies: copy });
  return out;
}

// Remove from one client (`only`), or from each: the rows under More.
export const removeRows = (item, only = null) => removeActions(item).filter((one) => !only || one.label === removeLabel(only));

// A skill's switch for all projects in each client that has one (`can.rule`, the states it takes;
// `can.now`, the state it has): skill-switch.js, the same control as Context's. Null with none.
export function skillSwitches(item, only = null) {
  const can = item.can || {};
  const clients = Object.keys(can.rule || {}).sort(byClientOrder).filter((client) => !only || client === only);
  if (!clients.length) return null;
  const box = el("div", "skill-switches");
  for (const client of clients) {
    const target = { item: item.items[client][0] };
    box.append(skillSwitch({ client, target, states: can.rule[client], now: (can.now || {})[client] || "on" }));
  }
  return box;
}

// What Claude Code keeps in the account (the List's "Claude account plugins and connectors"): its
// name, Unknown, and the reason Kitden gives for it. Kitden cannot change it.
export function accountCard(block) {
  return { kind: KIND_WORDS.plugin, title: block.name, tile: kindTile("plugin"), facts: [stateFact(block.item)], why: block.reason || null };
}

// A hook: its facts, why it has no action, and Technical details. Kitden has no switch for hooks.
// The twin of views/words.py HOOKS_ONLY_SHOWN.
export const HOOKS_ONLY_SHOWN = "Kitden only shows hooks; it does not add or turn them off.";
const EDIT_HOOK = "Edit it in the settings file under Technical details.";
export function hookCard(item, c) {
  const facts = [stateFact(item), comesFrom(item, c), { label: "Source", value: item.source }, clientsFact(item, { count: true })];
  return { kind: KIND_WORDS.hook, title: item.name, id: item.source, tile: kindTile("hook"), facts, why: `${HOOKS_ONLY_SHOWN} ${EDIT_HOOK}`, technical: techOf([{ title: "Settings file", path: (item.technical || {}).path }]) };
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
function readsCard({ from, to }) {
  const title = [from.name, el("span", "arrow", " → "), to.name];
  const facts = [{ label: "From", value: from.name }, { label: "To", value: to.name }];
  if (from.kind === "client") return { kind: "Connection", title, id: "Read by the client", facts, why: `${from.name} reads ${to.name}. ${READS_FILE}` };
  return { kind: "Connection", title, id: "An import", facts, why: `${from.name} brings in ${to.name}. ${READS_IT}` };
}

// Why a Cursor plugin's link has no ×: Cursor keeps its plugins in its own app. The words are
// the first two sentences of clients/cursor.py CURSOR_HINT (checked 2026-10-22,
// cursor.com/docs/plugins).
const CURSOR_REMOVES = "Cursor keeps its plugins in its own database. Remove it in Cursor: Customize → Plugins.";

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
  const why = item.kind === "plugin" && from.client === "cursor" && !owner ? `${loads} ${CURSOR_REMOVES}` : loads;
  return { kind: "Connection", title, id: owner ? `Through ${ownerName}` : "Loaded by the client", facts, why };
}

// A marketplace's caption: its plugins on the map, "Commands…" under More, and its source under
// Technical details.
export function marketplaceCard(group, { commandsStep = () => {} } = {}) {
  const items = group.items || [];
  const source = items.map((item) => (item.technical || {}).marketplace).find(Boolean);
  return { kind: "Marketplace", title: group.name, list: itemList("Plugins on the map", items.map((item) => ({ kind: "plugin", name: item.name, line: itemLine(item) }))), more: commandsAction(marketplaceEntries(group), commandsStep), technical: techOf([{ title: "Source", summary: source }]) };
}

// "Commands…" ---------------------------------------------------------------------------------

// The client entries whose commands "Commands…" reads (/api/commands takes an item id): a
// plugin's own entry in each client, a marketplace's in each client, in client order.
const pluginEntries = (item) => inOrder(Object.keys(item.items || {})).map((client) => ({ client, item: item.items[client][0] }));
const marketplaceEntries = (group) => inOrder(Object.keys(group.entries || {})).map((client) => ({ client, item: group.entries[client] }));
const commandsAction = (entries, run) => (entries.length ? [{ label: COMMANDS, run }] : []);

// One command: its label, the command in mono with a Copy button, or a note in its place.
function commandRow(command) {
  const row = el("li");
  row.append(el("strong", null, command.label));
  if (command.command) {
    const copy = button(COPY, () => copyText(command.command, copy), "btn ghost small");
    copy.setAttribute("aria-label", `${COPY} ${command.label}`);
    row.append(el("pre", null, command.command), copy);
  }
  if (command.note) row.append(el("p", "muted", command.note));
  return row;
}

// Copy a command to the clipboard; the button and live region say whether it worked.
function copyText(text, node) {
  const said = (words) => { node.textContent = words; say(words); };
  const clipboard = globalThis.navigator && navigator.clipboard;
  if (!clipboard) return Promise.resolve(said(NOT_COPIED));
  return clipboard.writeText(text).then(() => said(COPIED), () => said(NOT_COPIED));
}

// The step: one section per client entry, its commands read from /api/commands, and Done back.
function commandsNodes(crumb, entries, back) {
  const body = el("div", "body");
  body.append(el("p", "why", RUN_YOURSELF));
  for (const { client, item } of entries) {
    const section = el("section");
    const head = el("div", "who");
    head.append(mark(client), el("h2", null, CLIENT_NAMES[client] || client));
    const list = el("ul", "commands");
    list.append(el("li", "muted", "Loading…"));
    section.append(head, list);
    body.append(section);
    getJson(`/api/commands${query({ item })}`).then((answer) => {
      const rows = (answer.commands || []).map(commandRow);
      list.replaceChildren(...(rows.length ? rows : [el("li", "muted", NO_COMMANDS)]));
    }, () => list.replaceChildren(el("li", null, NOT_LOADED)));
  }
  const done = el("footer", "stack");
  const press = button("Done", back, "btn");
  press.dataset.focus = "commands:done";
  done.append(press);
  return [stepHead(crumb, COMMANDS.replace("…", ""), back), body, done];
}

// The card of what the map shows for `id` (library-map.js libraryThing).
const INSTRUCTION_CARDS = { file: fileCard, import: importCard };
function cardOf(thing, c, id) {
  if (thing.link) return INSTRUCTION_CARDS[thing.to.kind] ? readsCard(thing) : connectionCard(thing, c);
  const { block } = thing;
  if (INSTRUCTION_CARDS[block.kind]) return INSTRUCTION_CARDS[block.kind](block, c);
  if (block.kind === "client") return clientCard(block.client, c);
  if (block.kind === "account") return accountCard(block);
  if (block.kind === "group") return marketplaceCard(block.group, { commandsStep: () => commandsStep(id) });
  if (block.kind === "part") return partCard(block, c);
  if (block.kind === "plugin") return pluginCard(block.item, c, { addStep: () => addStep(id), commandsStep: () => commandsStep(id) });
  if (block.kind === "skill") return skillCard(block.item, c, { someStep: () => someStep(id), addStep: () => addStep(id) });
  return hookCard(block.item, c);
}

// Showing a card ----------------------------------------------------------------------------------

// Open the Details of what the map selected, beside the page, drawn from the map as it is now (also
// after Apply all). Gone from the map since: they close. `step` ("back") slides them in from a step.
function showLibrary(id, { step = null } = {}) {
  const thing = libraryThing(id);
  if (!thing) {
    closePanel({ focus: false });
    return Promise.resolve();
  }
  const card = cardOf(thing, context(thing.answer), id);
  const block = thing.block;
  if (block && (block.kind === "plugin" || block.kind === "skill")) card.after = afterOf(card.after, takesNode(block.item, id));
  // A skill inside a plugin: what it takes, found by its plugin and its own name.
  if (block && block.kind === "part" && block.label.words === "Skill") {
    const part = { kind: "part", plugin: block.plugin.plugin, skill: block.name, items: block.plugin.items };
    card.after = afterOf(card.after, takesNode(part, id));
  }
  const nodes = openCard(card, { type: "library", id }, () => showLibrary(id), () => showLibrary(id), step);
  return Promise.resolve(nodes);
}

// Back from a step to its card, focus on the button that stepped there (or More, which it waits
// under again).
function backFrom(id, label) {
  return () => showLibrary(id, { step: "back" }).then(() => focusAfterStep(`action:${label}`, "more"));
}

// "Add <name> to the clients you pick": one row per client that can take it or has it already
// ("Has it already", off); Cursor is never a choice (D26: it gets plugins through Claude Code). Each
// tick is one plugin.install row; a ticked row says "In preview".
export function addNodes(item, back) {
  const has = (client) => Boolean((item.items || {})[client]);
  // A skill can go to Cursor too (its own skills folder); a plugin cannot.
  const choices = item.kind === "skill" ? ["claude_code", "codex", "cursor"] : ["claude_code", "codex"];
  const clients = choices.filter((client) => item.can.add.includes(client) || has(client));
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
  return [stepHead(`${KIND_WORDS[item.kind] || "Plugin"} · ${item.name}`, `Add ${item.name} to the clients you pick`, back), body, done];
}

// A step in the panel: its nodes come in as the next step (`dir`), or drawn again in place (null);
// what it shows stays the selection's, with the step named. A new step shows from its top, even
// when the control that takes focus (Done) sits below the fold.
function openStep(id, name, nodes, dir, focus) {
  panelState.current = { type: "library", id, step: name };
  keepFrom(() => STEPS[name](id, null), nodes, () => showLibrary(id));
  if (!dir) return swapContent(nodes);
  return stepTo(nodes, dir).then(() => {
    focusAfterStep(focus);
    $("#drawer").scrollTop = 0;
  });
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
// or one with no Claude Code settings yet, cannot be ticked. Each tick is one skill.rule row for
// Claude Code.
export function someNodes(item, c, back) {
  const known = (data.projects || []).filter((p) => c.rules.projects[p.id]);
  const rows = menuItems(known, "").filter((p) => p.id).map((p) => {
    const can = c.rules.projects[p.id];
    const body = projectBody(item, p.id);
    const ticked = () => queued(body);
    const already = (item.off_in || []).includes(p.id);
    const away = can === "outside" ? outsideWords(c.rules.outside[p.id]) : null;
    const line = () => (already ? ALREADY_OFF : away || PROJECT_LINES[can] || "");
    return { id: p.id, name: p.name, line, off: () => already || can !== "ok", body, ticked };
  });
  return projectChecklist({ crumb: `Skill · ${item.name}`, title: `Turn off ${item.name} in the projects you pick`, why: SOME_WHY, rows, back });
}

function someStep(id, dir = "fwd") {
  const thing = libraryThing(id);
  if (!thing) return closePanel({ focus: false });
  const nodes = someNodes(thing.block.item, context(thing.answer), backFrom(id, OFF_SOME));
  return openStep(id, "some", nodes, dir, "find");
}

// "Commands…" of a plugin or a marketplace's caption, as a step; focus goes to its Done.
function commandsStep(id, dir = "fwd") {
  const thing = libraryThing(id);
  if (!thing) return closePanel({ focus: false });
  const { block } = thing;
  const group = block.kind === "group";
  const entries = group ? marketplaceEntries(block.group) : pluginEntries(block.item);
  const crumb = group ? `Marketplace · ${block.group.name}` : `${KIND_WORDS.plugin} · ${block.item.name}`;
  return openStep(id, "commands", commandsNodes(crumb, entries, backFrom(id, COMMANDS)), dir, "commands:done");
}

// The steps a Details card goes to, by name, to draw one again in place.
const STEPS = { add: addStep, some: someStep, commands: commandsStep };

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
