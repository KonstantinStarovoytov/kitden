// Side panel: item details, change review, the Apply motion, and the toast with Undo.
import { getJson, postJson, query } from "./api.js";
import { $, $$, button, el, joinWords, plural, reportError, shortPath, shortPaths } from "./dom.js";
import { loadLibrary, morphOnNextRender, onOpenItem, rowTitle, shownRow } from "./library.js";
import { finishTransition, fold, transition } from "./motion.js";
import { about, addButton, addOptions, whyNoAction } from "./offer.js";
import { CLIENT_NAMES, diffCounts, flag, GATEWAY_NOTE, gatewayName, kitdenMove, mark, movedNames, notesSection, ruleText, rulesText, skeleton, socket, stepText, strictText } from "./parts.js";
import { busy, current as currentModel, currentError, data, reload, render, setBusy, state } from "./store.js";

const KIND_WORDS = {
  mcp_server: "MCP server", plugin: "Plugin", skill: "Skill", hook: "Hook", marketplace: "Marketplace",
};
const CLIENT_ORDER = ["claude_code", "claude_desktop_code_tab", "codex", "cursor"];
const ACTION_BUTTONS = {
  "plugin.disable": (client) => `Turn off in ${client}…`,
  "plugin.enable": (client) => `Turn on in ${client}…`,
  "mcp.remove_direct": (client) => `Remove from ${client}…`,
};
// Node before 21 (the tests) has no navigator.
const APPLY_KEY = typeof navigator !== "undefined" && /Mac/.test(navigator.platform) ? "⌘ Enter to apply" : "Ctrl Enter to apply";
// While a change is written nothing in the review can stop it; the note says what happens.
const WRITING = "Writing the change. It can't stop halfway: if a step fails, Kitden puts everything back.";

// What is open now: "item" or "review", and for a review the change and the request behind it.
let current = null;
let opener = null;
let openerKey = null;

const clientName = (id) => CLIENT_NAMES[id] || id;

export function isPanelOpen() {
  return $("#drawer").classList.contains("open");
}

// New content for an open panel; focus stays inside it (the old buttons are gone).
function swapContent(content) {
  const drawer = $("#drawer");
  drawer.replaceChildren(...content);
  if (isPanelOpen() && !drawer.contains(document.activeElement)) drawer.focus();
}

// Put content in the panel and slide it in. Keyboard opens are instant.
export function openPanel(content, { instant = false } = {}) {
  finishTransition();
  const drawer = $("#drawer");
  if (isPanelOpen()) { swapContent(content); return; }
  drawer.replaceChildren(...content);
  opener = document.activeElement;
  const row = opener && opener.closest ? opener.closest("tr[data-key]") : null;
  openerKey = row ? row.dataset.key : state.selected;
  for (const node of [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  drawer.focus();
}

// While a change is being applied the panel stays open: closing it could not stop the change.
export function closePanel({ instant = false, keepSelection = false, focus = true, force = false } = {}) {
  if (!isPanelOpen() || (busy.change && !force)) return;
  cancelPreview();
  current = null;
  for (const node of [$("#drawer"), $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.remove("open");
  }
  if (!keepSelection) {
    state.selected = null;
    for (const row of $$('tr[aria-selected="true"]')) row.setAttribute("aria-selected", "false");
  }
  if (focus) restoreFocus();
}

// A review left without Apply: the server forgets its preview.
function cancelPreview() {
  if (current && current.type === "review" && current.change && current.change.state === "previewed") {
    postJson(`/api/changes/${encodeURIComponent(current.change.id)}/cancel`).catch(() => {});
  }
}

function restoreFocus() {
  if (opener && opener.isConnected) { opener.focus(); return; }
  const row = openerKey && $$("tr[data-key]").find((tr) => tr.dataset.key === openerKey);
  if (row) row.focus();
  else $("#main").focus();
}

// A review has no close button up here: its footer holds the one Cancel.
function header(kicker, title, lede, closeLabel = "Close", mono = false) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kicker));
  if (closeLabel) top.append(button(closeLabel, () => closePanel(), "btn ghost small"));
  const h1 = el("h1", mono ? "title-mono" : null, title);
  h1.id = "panel-title";
  head.append(top, h1);
  if (lede) head.append(el("p", "muted", lede));
  return head;
}

function callout(text, level = "warn") {
  const box = el("div", level === "error" ? "callout error" : "callout");
  box.setAttribute("role", level === "error" ? "alert" : "note");
  const icon = el("span", null, "⚠");
  icon.setAttribute("aria-hidden", "true");
  box.append(icon, el("span", null, text));
  return box;
}

// Item details ---------------------------------------------------------------------------

// `tools` goes to the tool list of a server in the Kitden gateway (see toolsSection).
export async function openItem(row, { instant = false, tools: toolsNext = {} } = {}) {
  current = { type: "item", row };
  const body = el("div", "body");
  body.append(el("div", "skeleton card"));
  openPanel([itemHeader(row), body, el("footer")], { instant });
  // The marketplace's entry says what the item is; read beside the definitions. Without it the
  // rest still shows.
  const entry = row.offer ? getJson(`/api/offer${query({ kind: row.kind, id: row.offer })}`).catch(() => null) : null;
  let definitions;
  try {
    const params = { name: row.lookup || row.name, kind: row.kind, project: state.project };
    definitions = (await getJson(`/api/explain${query(params)}`)).definitions;
  } catch {
    if (current && current.row === row) {
      body.replaceChildren(callout("Could not load the details.", "error"));
      const footer = el("footer");
      footer.append(button("Retry", () => openItem(row), "btn"));
      $("#drawer footer").replaceWith(footer);
      if (!$("#drawer").contains(document.activeElement)) $("#drawer").focus();
    }
    return;
  }
  const offer = await entry;
  if (!current || current.row !== row) return;
  current.definitions = definitions;
  current.offer = offer;
  showDetails(row, definitions, offer, toolsNext);
}

// The line under the Details title: the clients that load the item, then those where the page
// cannot tell whether it is on.
export function loadsLede(row, columns) {
  const names = (states) => columns
    .filter((c) => states.includes(row.cells[c.id] && row.cells[c.id].state))
    .map((c) => c.name);
  const loads = names(["on", "gw"]);
  const maybe = names(["unk"]);
  const lines = [];
  if (loads.length) lines.push(`Loads in ${joinWords(loads)}.`);
  if (maybe.length) lines.push(`May load in ${joinWords(maybe)}.`);
  return lines.join(" ") || "Does not load anywhere here.";
}

// The title names the source too when two rows share the name ("superpowers · cursor-public").
function itemHeader(row) {
  const map = currentModel("map");
  return header(KIND_WORDS[row.kind] || row.kind, rowTitle(row), loadsLede(row, map ? map.columns : []), "Close", true);
}

// The warning names the fix; the server sends both (load_map.py).
function warningText(flag) {
  return flag.fix ? `${flag.text}. ${flag.fix}` : flag.text;
}

// Seen from the client with the warning, a change to the copy it loads from another client
// also changes that other client itself; say so next to the button.
const SIDE_EFFECTS = {
  "plugin.disable": "also turns it off for", "plugin.enable": "also turns it on for", "mcp.remove_direct": "also removes it from",
};
function sideEffect({ def, action }, warnings) {
  const reaches = warnings.some((f) => f.via === def.client && f.client !== def.client);
  if (!reaches || !SIDE_EFFECTS[action]) return [];
  return [el("span", "note side", `${SIDE_EFFECTS[action]} ${clientName(def.client)} itself`)];
}

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

// A server the Gateway page lists as one that can move, with the entries a move takes and the
// gateways that can take them (none when it must be added in the gateway by hand). Without a
// gateway there is nothing to move into, so Details stays as it was. When the gateway could
// not be read (`unread`), Move cannot be judged: it is marked `unread`.
export function moveFor(row, model, unread = false) {
  if (row.kind !== "mcp_server") return null;
  if (!model) return unread ? { items: [], gateways: [], unread: true } : null;
  if (!model.gateways.length) return null;
  for (const group of ["move", "local"]) {
    const direct = (model.groups[group] || []).find((r) => r.name === row.name);
    if (!direct || !direct.items.length) continue;
    const gateways = moveTargets(model, group);
    // A local server no gateway here can take stays as it was: nothing to say about it.
    if (group === "move" || gateways.length) return { items: direct.items, gateways };
  }
  return null;
}

// The footer's lead action and the rest, in order; "move" stands for Move into the gateway, and
// `adds` are the ways to add the item (offer.js addOptions). A problem comes before an option:
// the warning's fix leads, then Move, then a lone action, then the first add. With a warning no
// button fixes, or a server to add in the gateway by hand first, nothing leads.
export function footerActions(offers, warnings, move, adds = []) {
  const fix = offers.find((o) => warnings.some((f) => f.fix_action === o.action && f.client === o.def.client));
  const canMove = Boolean(move && move.gateways.length);
  const options = [...(canMove ? ["move"] : []), ...offers, ...adds];
  let lead = fix || null;
  if (!lead && !warnings.length && canMove) lead = "move";
  if (!lead && !warnings.length && !move && offers.length === 1) lead = offers[0];
  if (!lead && !warnings.length && adds.length) lead = adds[0];
  return { lead, rest: options.filter((o) => o !== lead) };
}

// Move entries into a gateway. With one gateway that can take them the review opens at once;
// with two the panel asks which, the Kitden gateway first. A move into the Kitden gateway may
// ask the server for its tools first, so the button that started it stays busy until then.
export function moveInto(gateways, items, title) {
  const targets = items.map((item) => ({ item }));
  const preview = (gateway) => review({ action: "gateway.move", targets, params: { gateway: gateway.id } });
  if (gateways.length === 1) return preview(gateways[0]);
  const body = el("div", "body");
  body.append(el("p", "muted", "More than one gateway can take it. The Kitden gateway runs on this Mac and turns tools on or off per project."));
  const into = (gateway) => (gateway.kind === "kitden" ? "the Kitden gateway" : gatewayName(gateway));
  // The primary button sits last, so the Kitden gateway is drawn last.
  const choices = gateways.map((gateway, i) => button(`Move into ${into(gateway)}…`, () => preview(gateway), i === 0 ? "btn primary" : "btn"));
  openInfo("Move into the gateway", title, body, choices.reverse());
  return null;
}

function moveButton({ items, gateways }, look, name) {
  return button("Move into the gateway…", () => moveInto(gateways, items, name), look);
}

// The other actions wait behind one button, so the primary one stands alone.
function moreButton(buttons) {
  const more = button("More", () => {
    more.replaceWith(...buttons);
    buttons[0].focus();
  }, "btn");
  return more;
}

// A Details footer from footerActions: the lead is the primary button and the rest, then
// `commands`, wait under More. Without a lead every action is plain, after the commands.
// `draw(option, look)` gives an option's nodes.
export function footerButtons({ lead, rest }, draw, commands = []) {
  if (lead) {
    const others = [...rest.flatMap((o) => draw(o, "btn")), ...commands];
    return [...(others.length ? [moreButton(others)] : []), ...draw(lead, "btn primary")];
  }
  const note = commands.length ? [el("span", "note", "Install, update or move to another client:"), ...commands] : [];
  return [...note, ...rest.flatMap((o) => draw(o, "btn"))];
}

function scopeWords(def) {
  const project = def.project ? def.project.split("/").filter(Boolean).pop() : "";
  const words = {
    user: "Global settings",
    project: `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const via = def.owner_client && def.owner_client !== def.client ? ` · via ${clientName(def.owner_client)}` : "";
  return `${words}${via}`;
}

const UNKNOWN_WORDS = {
  stored_in_account: "Its on/off state is kept in your Claude account, not on this Mac.",
  no_access: "This page could not read where its state is kept.",
  unrecognized_format: "Its state is kept in a format this page does not know.",
  parse_error: "The file that holds its state could not be read.",
  may_be_stale: "The saved state may be out of date.",
  not_documented: "The client does not document where its state is kept.",
};

function layer(def) {
  let look = "off";
  let badge = "Not loaded";
  let why = def.why === "Loads." ? "" : def.why;
  const unknown = def.enabled === "unknown";
  if (unknown) {
    look = "unk";
    badge = "Unknown";
    why = UNKNOWN_WORDS[def.unknown_reason] || "This page cannot tell whether it is on.";
  } else if (def.loads) { look = def.via_gateway ? "gw" : "on"; badge = "Loads"; }
  else if (def.merged) badge = "Merged";
  else if (def.overridden) { look = "over"; badge = "Overridden"; }
  else if (def.enabled === "off") badge = "Off";
  const wins = def.loads && !unknown;
  const row = el("div", wins ? "layer wins" : "layer");
  const dot = socket({ state: look });
  dot.replaceChildren(dot.querySelector(".dot"));
  dot.setAttribute("aria-hidden", "true");
  const middle = el("div");
  middle.append(el("div", "name", scopeWords(def)));
  const where = el("div", "why mono", shortPath(def.source));
  where.title = def.source || "";
  middle.append(where);
  if (def.summary) middle.append(el("div", "why mono", def.summary));
  if (why) middle.append(el("div", "why", why));
  // Every plugin with a known state gets the same switch; one the page cannot change from
  // here (its on/off lives in the client's account) is shown locked, with the reason.
  const toggle = !unknown && def.kind === "plugin" && def.actions.find((a) => a === "plugin.disable" || a === "plugin.enable");
  const known = !unknown && def.kind === "plugin" && (def.enabled === "on" || def.enabled === "off");
  const control = toggle ? pluginSwitch(def, toggle) : known ? pluginSwitch(def, null) : el("span", wins ? "badge win" : "badge", badge);
  row.append(dot, middle, control);
  return row;
}

// A switch that shows a real state. Pressing it runs `press`, which opens the review; it flips
// only when the change is written and checked, never before. Without `press` it only shows.
function switchNode(on, press) {
  const node = el("button", "switch");
  node.type = "button";
  node.setAttribute("role", "switch");
  node.setAttribute("aria-checked", String(on));
  node.append(el("span", "thumb"));
  if (!press) return node;
  node.title = on ? "On. Press to review turning it off." : "Off. Press to review turning it on.";
  // While the preview is fetched the thumb rests half-way: pending, not flipped.
  node.addEventListener("click", async () => {
    if (node.classList.contains("pending")) return;
    node.classList.add("pending");
    node.setAttribute("aria-busy", "true");
    try {
      await press();
    } catch (error) {
      reportError(error);
    } finally {
      node.classList.remove("pending");
      node.removeAttribute("aria-busy");
    }
  });
  return node;
}

// The plugin's real state; the Library shows the new state after a change. Without an action
// the switch is locked: it shows the state and says where to change it.
function pluginSwitch(def, action) {
  const on = action ? action === "plugin.disable" : def.enabled === "on";
  const node = switchNode(on, action ? () => review({ action, targets: [{ item: def.id }], params: {} }) : null);
  if (!action) {
    node.disabled = true;
    node.setAttribute("aria-label", `${on ? "On" : "Off"} in ${clientName(def.client)}; not changed from here`);
    node.title = def.change_hint || "Not changed from here.";
    return node;
  }
  node.setAttribute("aria-label", `${on ? "Turn off" : "Turn on"} in ${clientName(def.client)}…`);
  return node;
}

// Tools of a server in the Kitden gateway --------------------------------------------------

// The project's folder name, as the picker at the top shows it.
function projectLabel(id) {
  const found = (data.projects || []).find((p) => p.id === id);
  return found ? found.path.split("/").filter(Boolean).pop() || found.path : id;
}

// The rows of a held server's Details, for the project picked at the top (`where`, its folder
// name) or for all projects (null): the whole server first, then each tool it lists. A row
// that differs names what it follows without its own setting: the project around it, or all
// projects. A tool's hint says whether it reads or writes, from the server or by its name.
export function toolRows(answer, where) {
  const place = where || "all projects";
  const row = (key, tool, name, description, entry) => {
    const on = entry.state !== "off";
    const what = tool === null ? answer.server : `${tool} of ${answer.server}`;
    const follows = entry.follows || "all projects";
    const hint = tool === null ? null : entry.hint || null;
    const hintFrom = tool === null ? null : entry.hint_from || null;
    return { key, tool, name, description, on, hint, hintFrom, calls: tool === null ? null : callsText(entry.calls), flag: entry.new ? "New" : null, differs: Boolean(entry.differs), follows, label: `Turn ${on ? "off" : "on"} ${what} in ${place}…` };
  };
  return [
    row("server", null, "Whole server", `Turns every tool of ${answer.server} on or off.`, answer),
    ...answer.tools.map((t) => row(`tool:${t.name}`, t.name, t.name, t.description, t)),
  ];
}

// What the tool row says when hovered: how often the gateway forwarded a call and when last. The
// file keeps UTC minutes; the time shown is the browser's.
export function callsText(calls, now = new Date()) {
  if (!calls || !calls.count) return null;
  const last = new Date(calls.last);
  const pad = (n) => String(n).padStart(2, "0");
  const time = `${pad(last.getHours())}:${pad(last.getMinutes())}`;
  const today = last.toDateString() === now.toDateString();
  const day = today ? "today" : `${last.getDate()} ${last.toLocaleString("en-GB", { month: "short" })}`;
  const times = calls.count === 1 ? "once" : `${calls.count} times`;
  return `Called ${times}, last ${day} ${time}`;
}

// The tools the batch switch turns off: those that are on and write, or may write by their name.
export function writingToolsOn(tools) {
  return tools.filter((t) => t.state === "on" && (t.hint === "writes" || t.hint === "may write")).map((t) => t.name);
}

const HINT_FROM = { server: "from the server", name: "by its name" };

// The tool list in the open panel: a refresh reads it again, an Undo draws its Details again.
let tools = null;

function reloadTools() {
  if (tools && tools.section.isConnected) tools.load();
}

// The control with this data-focus key inside `box`, if there is one.
function withFocusKey(box, key) {
  return key ? [...box.querySelectorAll("[data-focus]")].find((node) => node.dataset.focus === key) || null : null;
}

// Asks every held server for its tools again. The server says when it is done; without the
// event stream, stop waiting after a minute. The list reads the answer when the event comes.
async function refreshTools() {
  // True when the minute ran out: the list is read again here, since no event will do it.
  const ended = new Promise((resolve) => {
    document.addEventListener("kitden:tools", () => resolve(false), { once: true });
    setTimeout(() => resolve(true), 60000);
  });
  const result = await postJson("/api/gateway/tools/refresh");
  if (!result.ok) {
    if (tools) tools.load({ error: (result.data && result.data.detail) || `Could not refresh the tools (${result.status}).` });
    return;
  }
  if (await ended) reloadTools();
}

// A held server's tools, a switch each, for the project picked at the top. A switch opens the
// review; when the change is verified, `again(next)` draws this Details again with the switch
// flipped. `next` says which control gets focus (`focus`), why a review stopped (`error`) and
// which switch has just flipped (`flip`). An error stays as a callout until the next action.
export function toolsSection(server, again, next = {}) {
  const section = el("section", "tools");
  const where = state.project ? projectLabel(state.project) : null;
  const head = el("div", "tools-head");
  const refresh = button("Refresh tools", () => refreshTools(), "btn small ghost");
  refresh.dataset.focus = "tools:refresh";
  head.append(el("h2", null, `Tools · ${where || "All projects"}`), refresh);
  const list = el("div", "tool-list");
  list.append(skeleton("line", 3));
  section.append(head);
  if (!state.project) section.append(el("p", "muted", "These switches also apply in folders Kitden does not know."));
  section.append(list);

  const change = (row, value, pressed) => {
    const back = ({ error = null, verified = false } = {}) => again({ focus: verified ? row.key : pressed, error, flip: verified ? row.key : null });
    const params = { server, tool: row.tool, state: value, project: state.project || null };
    return review({ action: "gateway.rule", targets: [], params }, { back });
  };

  // Strict mode is set for all projects: with a project picked the switch only shows it.
  const strictRow = (answer, flip) => {
    const row = el("div", "layer tool whole");
    const middle = el("div");
    middle.append(el("div", "name", "Strict"), el("div", "why", "Only tools you turned on are offered; a new tool waits."));
    const back = ({ error = null, verified = false } = {}) => again({ focus: "strict", error, flip: verified ? "strict" : null });
    const params = { server, state: answer.strict ? "off" : "on" };
    const toggle = switchNode(Boolean(answer.strict), () => review({ action: "gateway.strict", targets: [], params }, { back }));
    toggle.setAttribute("aria-label", "Strict: only tools you turned on");
    toggle.dataset.focus = "strict";
    if (flip === "strict") toggle.classList.add("flipped");
    if (state.project) {
      toggle.disabled = true;
      toggle.title = "Set for all projects";
    }
    row.append(middle, toggle);
    const stack = el("div", "stack");
    stack.append(row);
    return stack;
  };

  const draw = (answer, { error = null, flip = null }) => {
    const nodes = [];
    if (error) nodes.push(callout(error, "error"));
    if (answer.problem) nodes.push(callout(answer.problem));
    if (answer.state === "off") nodes.push(el("p", "muted", `${server} is off in ${where || "all projects"}, so none of its tools are offered there.`));
    nodes.push(strictRow(answer, flip));
    const writing = writingToolsOn(answer.tools);
    if (writing.length) {
      // Verified, the button is gone (no writing tool is on), so focus goes to Refresh tools.
      const back = ({ error = null, verified = false } = {}) => again({ focus: verified ? "tools:refresh" : "writing", error });
      const params = { server, tools: writing, state: "off", project: state.project || null };
      const all = button("Turn off every writing tool…", () => review({ action: "gateway.rules", targets: [], params }, { back }), "btn small");
      all.dataset.focus = "writing";
      const line = el("div");
      line.append(all);
      nodes.push(line);
    }
    const stack = el("div", "stack");
    for (const row of toolRows(answer, where)) {
      const node = el("div", row.tool === null ? "layer tool whole" : "layer tool");
      if (row.calls) node.title = row.calls;
      const middle = el("div");
      const title = el("div", row.tool === null ? "name" : "name mono", row.name);
      if (row.hintFrom) {
        const hint = el("span", "muted hint", row.hint);
        hint.title = HINT_FROM[row.hintFrom];
        title.append(" ", hint);
      }
      if (row.flag) title.append(" ", flag({ text: row.flag, level: "info" }));
      middle.append(title);
      if (row.description) {
        const about = el("div", "why", row.description);
        about.title = row.description;
        middle.append(about);
      }
      if (row.differs) {
        const line = el("div", "differs");
        const follow = button(`Use ${row.follows}`, () => change(row, null, `follow:${row.key}`), "btn small");
        follow.dataset.focus = `follow:${row.key}`;
        line.append(flag({ text: `Differs from ${row.follows}`, level: "info" }), follow);
        middle.append(line);
      }
      const toggle = switchNode(row.on, () => change(row, row.on ? "off" : "on", row.key));
      toggle.setAttribute("aria-label", row.label);
      toggle.dataset.focus = row.key;
      // Drawn in its new state; the thumb slides there once (the resting style is the truth).
      if (flip === row.key) toggle.classList.add("flipped");
      node.append(middle, toggle);
      stack.append(node);
    }
    nodes.push(stack);
    if (!answer.tools.length) nodes.push(el("p", "muted", "Kitden does not know its tools yet. Refresh tools asks the server."));
    return nodes;
  };

  const load = async (options = {}) => {
    let answer = null;
    try {
      answer = await getJson(`/api/gateway/tools${query({ server, project: state.project })}`);
    } catch {
      answer = null;
    }
    if (!section.isConnected) return;
    // A redraw keeps keyboard focus on the same control.
    const kept = list.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    list.replaceChildren(...(answer ? draw(answer, options) : [callout("Could not load the tools.", "error")]));
    const target = withFocusKey(section, options.focus || kept);
    if (target) target.focus();
  };
  // `flipped`: the switch the last verified change flipped; an Undo puts focus back on it.
  tools = { section, load, again, flipped: next.flip || null };
  load(next);
  return section;
}

// Details of a row on this computer: why nothing can be done (when so), what it is (`offer`, the
// marketplace's entry, when read), warnings, what each client loads, then every action.
function showDetails(row, definitions, offer = null, toolsNext = {}) {
  const warnings = row.flags.filter((x) => x.level === "warning");
  const move = moveFor(row, currentModel("gateway"), Boolean(currentError("gateway")));
  const offers = definitions.flatMap((def) => def.actions.filter((a) => ACTION_BUTTONS[a]).map((action) => ({ def, action })));
  const actions = footerActions(offers, warnings, move, addOptions(row, offer));
  const why = actions.lead || actions.rest.length ? "" : whyNoAction(row, definitions);
  const body = el("div", "body");
  if (why) body.append(el("p", "muted", why));
  if (offer) body.append(...about(offer));
  for (const f of warnings) body.append(callout(warningText(f)));
  // A warning that already says where to change it (a copy loaded from another client)
  // replaces the hints under that client, so the fact appears once.
  const covered = new Set(warnings.filter((f) => f.via).map((f) => f.client));
  const byClient = new Map();
  for (const def of definitions) {
    if (!byClient.has(def.client)) byClient.set(def.client, []);
    byClient.get(def.client).push(def);
  }
  const clients = [...byClient.keys()].sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  for (const client of clients) {
    const section = el("section", "client-layers");
    const title = el("div", "chip");
    title.append(mark(client), el("h2", null, clientName(client)));
    const stack = el("div", "stack");
    for (const def of byClient.get(client)) stack.append(layer(def));
    section.append(title, stack);
    const hints = covered.has(client) ? [] : new Set(byClient.get(client).filter((d) => d.change_hint && !d.actions.length && d.change_hint !== why).map((d) => d.change_hint));
    for (const hint of hints) section.append(el("p", "muted", hint));
    body.append(section);
  }
  if (!definitions.length) body.append(el("p", "muted", "No definitions found for this item here."));
  // A server in the Kitden gateway: its tools, a switch each.
  if (definitions.some((d) => d.via_gateway === "kitden")) {
    // Drawn again after a change with the row as the Library reads it now, so the line under
    // the title stays true.
    body.append(toolsSection(row.name, (next) => openItem(shownRow(row.key) || row, { tools: next }), toolsNext));
  }
  if (definitions.some((d) => d.secret_present)) {
    body.append(el("p", "muted", "This entry holds a secret. It is hidden here and never logged."));
  }
  if (move && move.unread) body.append(el("p", "muted", "Could not read the gateway, so Move is not offered."));
  else if (move && !move.gateways.length) body.append(el("p", "muted", GATEWAY_NOTE));

  const withCommands = definitions.filter((d) => d.kind === "plugin" || d.kind === "marketplace");
  const commands = withCommands.length ? [button("Commands…", () => showCommands(row, withCommands), "btn")] : [];
  // Name the scope too when one client has more than one definition that can change.
  const buttonFor = ({ def, action }, look) => {
    const twins = offers.filter((o) => o.def.client === def.client).length > 1;
    const where = twins ? ` (${scopeWords(def).toLowerCase()})` : "";
    const label = ACTION_BUTTONS[action](`${clientName(def.client)}${where}`);
    return button(label, () => review({ action, targets: [{ item: def.id }], params: {} }), look);
  };
  // A plain action names what else it changes; the primary one stands alone.
  const draw = (o, look) => {
    if (o === "move") return [moveButton(move, look, row.name)];
    if (o.def) return [...(look === "btn" ? sideEffect(o, warnings) : []), buttonFor(o, look)];
    return [addButton(o, row, offer, look)];
  };
  const footer = el("footer");
  footer.append(...footerButtons(actions, draw, commands));
  swapContent([itemHeader(row), body, footer]);
}

async function showCommands(row, definitions) {
  const body = el("div", "body");
  body.append(el("p", "muted", "You run these yourself. This page never runs them."));
  const footer = el("footer");
  footer.append(button("Back", () => showDetails(row, current.definitions, current.offer), "btn"));
  swapContent([header("Commands", row.name, null, "Close", true), body, footer]);
  const seen = new Set();
  for (const def of definitions) {
    if (seen.has(def.id)) continue;
    seen.add(def.id);
    const twins = definitions.filter((d) => d.client === def.client).length > 1;
    const section = el("section");
    const title = el("div", "chip");
    title.append(mark(def.client), el("h2", null, twins ? `${clientName(def.client)} · ${scopeWords(def)}` : clientName(def.client)));
    const list = el("ul", "commands");
    list.append(el("li", "muted", "Loading…"));
    section.append(title, list);
    body.append(section);
    try {
      const result = await getJson(`/api/commands${query({ item: def.id })}`);
      list.replaceChildren();
      for (const command of result.commands) {
        const li = el("li");
        li.append(el("strong", null, command.label));
        if (command.command) li.append(el("pre", null, command.command));
        if (command.note) li.append(el("p", "muted", command.note));
        list.append(li);
      }
      if (!result.commands.length) list.append(el("li", "muted", "No commands for this item."));
    } catch {
      list.replaceChildren(el("li", null, "Could not load the commands."));
    }
  }
}

// A note in the panel, for example a server the gateway holds; `actions` go in its footer.
export function openInfo(kicker, title, body, actions = []) {
  current = { type: "info" };
  const footer = el("footer");
  footer.append(...actions);
  openPanel([header(kicker, title, null, "Close", true), body, footer]);
}

// A change from the Changes page: the Changes page builds the body (steps with their files,
// history, error); the panel frames it. Undo stays with the row that opened it.
export function openChange(title, body, onUndo) {
  current = { type: "change" };
  const footer = el("footer");
  if (onUndo) footer.append(button("Undo", onUndo, "btn primary"));
  openPanel([header("Change", title, null), body, footer]);
}

// Change review --------------------------------------------------------------------------

const DONE_WORDS = {
  "plugin.disable": "Turned off", "plugin.enable": "Turned on", "mcp.remove_direct": "Removed",
  "gateway.connect": "Connected the gateway", "setup_server.register": "Added show my setup",
  "setup_server.update": "Updated show my setup to Kitden", "gateway.move": "Moved",
  "gateway.switch": "Switched the gateway", "plugin.install": "Added", "marketplace.add": "Added the marketplace",
  "skill.install": "Added", "plugin.skills": "Added",
};

// The review title names the exact entry; the toast uses the short name ("superpowers").
// `previewBody` is what the review asked for; Add skills names its plugin and a tool rule its
// tool and project from it.
export function changeWords(change, previewBody) {
  if (change.action === "gateway.rule") {
    const params = (previewBody && previewBody.params) || {};
    return ruleText(params, params.project ? projectLabel(params.project) : null);
  }
  if (change.action === "gateway.strict") {
    const params = (previewBody && previewBody.params) || {};
    return strictText(params);
  }
  if (change.action === "gateway.rules") {
    const params = (previewBody && previewBody.params) || {};
    return rulesText({ ...params, tools: params.tools || [] }, params.project ? projectLabel(params.project) : null);
  }
  // A move names the servers it takes; the Kitden gateway's own steps are not a client.
  const kitden = kitdenMove(change);
  const steps = change.steps.filter((s) => s.client !== "gateway" && s.client !== "kitden");
  const listed = change.action === "gateway.move" ? movedNames(change.steps) : [...new Set(steps.map((s) => s.name))];
  const names = joinWords(listed);
  const short = joinWords([...new Set(listed.map((name) => name.split("@")[0]))]);
  // A copied skill folder reaches every client that reads that folder, not only its owner.
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  reached.sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const clients = joinWords(reached.map(clientName));
  const plugin = ((previewBody && previewBody.params && previewBody.params.plugin) || "the plugin").split("@")[0];
  const title = {
    "gateway.move": kitden ? `Move ${names} into the Kitden gateway` : `Move ${names} into the gateway`,
    "plugin.disable": `Turn off ${names} in ${clients}`,
    "plugin.enable": `Turn on ${names} in ${clients}`,
    "mcp.remove_direct": `Remove ${names} from ${clients}`,
    "gateway.connect": `Connect the gateway to ${clients}`,
    "plugin.install": `Add ${joinWords([...new Set(steps.filter((s) => s.name.includes("@")).map((s) => s.name))])} to ${clients}`,
    "marketplace.add": `Add the ${names} marketplace to ${clients}`,
    "skill.install": `Add ${names} to ${clients}`,
    "plugin.skills": `Add ${plugin}'s skills to ${clients}`,
    // Each client's last step adds the new entry; it is named after the gateway.
    "gateway.switch": `Use ${steps.length ? steps[steps.length - 1].name : "the new gateway"} in ${clients}`,
    "setup_server.register": `Add “show my setup” to ${clients}`,
    "setup_server.update": `Update “show my setup” to Kitden in ${clients}`,
  }[change.action] || change.action;
  const verb = DONE_WORDS[change.action] || change.action;
  let what = `${verb} ${short} ${change.action === "mcp.remove_direct" ? "from" : "in"} ${clients}`;
  if (change.action === "plugin.install") {
    what = `${verb} ${joinWords([...new Set(steps.filter((s) => s.name.includes("@")).map((s) => s.name.split("@")[0]))])} to ${clients}`;
  } else if (change.action === "marketplace.add" || change.action === "skill.install") {
    what = `${verb} ${short} to ${clients}`;
  } else if (["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update"].includes(change.action)) {
    what = `${verb} ${["setup_server.update", "gateway.switch"].includes(change.action) ? "in" : "to"} ${clients}`;
  } else if (change.action === "gateway.move") {
    what = `${verb} ${short} into ${kitden ? "the Kitden gateway" : "the gateway"}`;
  } else if (change.action === "plugin.skills") {
    what = `${verb} ${plural(steps.length, "skill", "skills")} to ${clients}`;
  }
  const notes = [...new Set(change.steps.map((s) => s.restart_note).filter(Boolean))]
    .map((note) => note.replace(/,? for this to take effect\.?$/, ""));
  const after = notes.length > 1 ? [`Restart or reload ${clients}`] : notes;
  return { title, done: [what, ...after].join(" · ") };
}

// What Add skills does not copy, as one plain line; empty when it copies every skill.
export function leftOutText(leftOut) {
  if (!leftOut || !leftOut.length) return "";
  return `Left out: ${leftOut.map((s) => `${s.name} (${s.why})`).join(", ")}.`;
}

// Ask the server for a preview and show it. Used by the Library, Gateway and Agents places.
// `note` shows as a callout above the result, for example that an add is for every project.
// `back({ error, verified })` returns to the Details the review came from (a tool switch):
// after Cancel, after Apply is verified, or with the reason the preview was refused.
export async function review(previewBody, { note = null, back = null } = {}) {
  const result = await postJson("/api/changes/preview", previewBody);
  if (!result.ok || !result.data || !result.data.id) {
    const reason = (result.data && result.data.detail) || `Could not prepare this change (${result.status}).`;
    if (back) {
      await back({ error: reason });
      return;
    }
    current = { type: "error" };
    const footer = el("footer");
    footer.append(button("Close", () => closePanel(), "btn"));
    const body = el("div", "body");
    body.append(callout(reason, "error"));
    openPanel([header("Review change", "Could not prepare this change", null, null), body, footer]);
    return;
  }
  showReview(result.data, previewBody, note, back);
}

// The after line's client chips, and its notes, each once. An entry may have only a note (a
// tool rule when no client uses the Kitden gateway yet).
export function afterParts(entries) {
  return { chips: entries.filter((e) => e.client), notes: [...new Set(entries.map((e) => e.note).filter(Boolean))] };
}

// "After: [CC] Claude Code ● Off · [CU] Cursor ● Loads once", in the Library's sockets.
// An entry with a note (a client that would load a skill twice) gets its one line below.
function afterLine(entries) {
  const { chips, notes } = afterParts(entries);
  const box = el("div");
  if (chips.length) {
    const line = el("div", "after");
    line.append(el("span", "note", "After:"));
    for (const entry of chips) {
      const chip = el("span", "chip");
      chip.append(mark(entry.client), el("span", null, clientName(entry.client)), socket({ state: entry.state, word: entry.word }));
      line.append(chip);
    }
    box.append(line);
  }
  for (const note of notes) box.append(callout(note));
  return box;
}

// Only the lines that change show; the diff's own header lines say nothing a person needs.
// Each line is a block, so removed and added lines carry their own tint.
function diffLines(text) {
  const pre = el("pre", "diff");
  for (const line of String(text || "").split("\n")) {
    if (line === "--- before" || line === "+++ after" || /^@@ /.test(line)) continue;
    let look = "line";
    if (line.startsWith("+")) look = "line add";
    else if (line.startsWith("-")) look = "line del";
    pre.append(el("span", look, line || " "));
  }
  return pre;
}

function showReview(change, previewBody, note, back = null) {
  current = { type: "review", change, previewBody, note, back };
  const words = changeWords(change, previewBody);
  const body = el("div", "body");
  if (note) body.append(callout(note));
  if (change.after && change.after.length) body.append(afterLine(change.after));
  if (change.shared_file_warning) body.append(callout("This edits a project file that is usually shared through git."));
  // The result comes first; the file change and the command wait behind one summary.
  const files = el("details", "file-change");
  const summary = el("summary", null, change.steps.length > 1 ? "Show file changes" : "Show file change");
  const counts = change.steps.map((s) => diffCounts(s.diff)).reduce((a, b) => ({ added: a.added + b.added, removed: a.removed + b.removed }), { added: 0, removed: 0 });
  if (counts.added || counts.removed) {
    const count = el("span", "diff-count");
    count.setAttribute("aria-label", `${plural(counts.added, "line", "lines")} added, ${counts.removed} removed`);
    if (counts.added) count.append(el("span", "plus", `+${counts.added}`));
    if (counts.removed) count.append(el("span", "minus", `−${counts.removed}`));
    summary.append(count);
  }
  files.append(summary);
  for (const step of change.steps) {
    const box = el("div", "step");
    const head = el("div", "step-head");
    const file = el("span", "file mono", shortPath(step.path));
    file.title = step.path || "";
    head.append(mark(step.client), el("strong", null, clientName(step.client)), file);
    box.append(head, diffLines(step.diff));
    files.append(box);
    if (step.command) files.append(el("p", "muted", `Runs ${clientName(step.client)}'s own command: ${step.command}`));
  }
  body.append(fold(files));
  const leftOut = leftOutText(change.left_out);
  if (leftOut) body.append(el("p", "muted", leftOut));
  const after = notesSection("After you apply", change.steps);
  if (after) body.append(after);

  const footer = el("footer");
  footer.append(el("span", "note", APPLY_KEY));
  // From a tool switch, Cancel goes back to its Details; otherwise it closes the panel.
  const cancel = button("Cancel", () => {
    if (!back) return closePanel();
    cancelPreview();
    return back();
  }, "btn");
  const apply = el("button", "btn primary apply");
  apply.type = "button";
  const label = el("span", "label", "Apply");
  apply.append(label);
  apply.addEventListener("click", () => applyChange(change, { apply, cancel, label, body }).catch(brokeAfterAnswer));
  footer.append(cancel, apply);
  openPanel([header("Review change", words.title, "Nothing is written until you press Apply. A backup is kept, so you can undo.", null), body, footer]);
}

// Something broke after the server answered (a render, the toast). The answer stands, so
// the page says nothing new about the change; it only frees itself and logs the error.
function brokeAfterAnswer(error) {
  setBusy(false);
  reportError(error);
}

// While a change is written, Cancel and the close button are gone (nothing could stop it)
// and the note under the buttons says what is happening; they come back if it stops.
function lockReview(locked, apply, cancel) {
  apply.disabled = locked;
  cancel.disabled = locked;
  cancel.hidden = locked;
  const close = $("#drawer header .top button");
  if (close) {
    close.disabled = locked;
    close.hidden = locked;
  }
  const note = $("#drawer footer .note");
  if (note) note.textContent = locked ? WRITING : APPLY_KEY;
}

function resetApply(apply, cancel, label) {
  for (const extra of apply.querySelectorAll(".spinner, .check")) extra.remove();
  apply.classList.remove("done");
  label.textContent = "Apply";
  lockReview(false, apply, cancel);
}

function checkMark() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [key, value] of Object.entries({ viewBox: "0 0 14 14", width: "12", height: "12", class: "check", "aria-hidden": "true" })) svg.setAttribute(key, value);
  const path = document.createElementNS(ns, "path");
  for (const [key, value] of Object.entries({ d: "M2.5 7.5 L5.8 10.5 L11.5 3.5", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round" })) path.setAttribute(key, value);
  svg.append(path);
  return svg;
}

const STOPPED = {
  stale: "A file changed after the preview, so nothing was written. Preview again to see the current state.",
  restored: "The change did not check out, so the original settings were put back.",
};
// The states a change can end in after each verb. Read back in any other state it has not
// ended, so the page cannot say how it went.
const ENDED = {
  apply: ["verified", "stale", "restored", "cancelled", "undone", "undo_blocked"],
  undo: ["undone", "undo_blocked"],
};
const LOST = "Could not confirm the result. Check Changes before trying again.";

// The change as the server holds it now, or null when it cannot be read.
async function readChange(id) {
  try {
    return await getJson(`/api/changes/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

// How the change ended, read back from the server, when the answer cannot say.
async function readOutcome(id, verb) {
  const read = await readChange(id);
  return { after: read && ENDED[verb].includes(read.state) ? read : null, failure: LOST };
}

// How an Apply or an Undo ("apply", "undo") ended: the change as the server holds it, or why
// it failed.
export async function changeOutcome(id, verb) {
  const name = verb === "undo" ? "Undo" : "Apply";
  let result;
  try {
    result = await postJson(`/api/changes/${encodeURIComponent(id)}/${verb}`);
    if (!result.data) throw new Error(`The ${name} answer had no body (${result.status}).`);
  } catch (error) {
    // No answer, or one with no body, yet the change may have run: ask the server how it ended.
    console.error(error);
    return readOutcome(id, verb);
  }
  if (result.data.id) return { after: result.data, failure: null };
  // 409 with no change: it had moved on already, for example by an Apply whose answer was lost.
  if (result.status === 409) return readOutcome(id, verb);
  return { after: null, failure: result.data.detail || `${name} failed (${result.status}).` };
}

// Apply → Applying… (spinner) → Applied (the check draws); then the panel leaves and the
// page shows the effect where it happened. Each step waits for work, never for a timer.
async function applyChange(change, { apply, cancel, label, body }) {
  if (busy.change) return;
  const previewBody = current && current.previewBody;
  const note = current && current.note;
  const back = current && current.back;
  setBusy(true);
  lockReview(true, apply, cancel);
  label.textContent = "Applying…";
  apply.prepend(el("span", "spinner"));
  // A change with several steps counts them as the server finishes each one, and a thin bar
  // along the button's bottom edge fills to match. Both show only what the server reported.
  const meter = el("span", "meter");
  meter.setAttribute("aria-hidden", "true");
  apply.append(meter);
  const onProgress = (event) => {
    const { id, done, total } = event.detail || {};
    if (id !== change.id || !(total > 1)) return;
    label.textContent = stepText("Applying", done, total);
    meter.style.transform = `scaleX(${done / total})`;
  };
  document.addEventListener("kitden:progress", onProgress);
  // The last try's error stays until now, the next action.
  for (const old of body.querySelectorAll(".callout.error")) old.remove();
  let outcome;
  try {
    outcome = await changeOutcome(change.id, "apply");
  } finally {
    document.removeEventListener("kitden:progress", onProgress);
    meter.remove();
  }
  const { after, failure } = outcome;
  if (after && current) current.change = after;

  if (!after || after.state !== "verified") {
    setBusy(false);
    resetApply(apply, cancel, label);
    const reason = after ? STOPPED[after.state] || `The change stopped: ${after.state}.` : failure;
    const detail = after && after.error ? ` (${shortPaths(after.error)})` : "";
    body.prepend(callout(`${reason}${detail}`, "error"));
    // Focus goes to the button in Apply's place; the callout says what went wrong.
    let next = apply;
    if (after && after.state !== "previewed") {
      next = button("Preview again", () => review(previewBody, { note, back }), "btn primary");
      apply.replaceWith(next);
    }
    next.focus();
    reload().then(render).catch(() => {});
    return;
  }
  await showApplied(after, apply, label, previewBody, back);
}

// The server said `verified`: the button turns green while the page reloads, then the panel
// leaves at once and the toast offers Undo. From a tool switch, its Details comes back instead,
// with the switch flipped, and the page behind shows the new state.
async function showApplied(after, apply, label, previewBody, back) {
  for (const spin of apply.querySelectorAll(".spinner")) spin.remove();
  apply.prepend(checkMark());
  apply.classList.add("done");
  label.textContent = "Applied";
  await reloadAll();
  if (back) {
    render();
    await back({ verified: true });
  } else {
    current = null;
    closePanel({ keepSelection: true, focus: false, force: true });
    showEffect();
    restoreFocus();
  }
  setBusy(false);
  toast(changeWords(after, previewBody).done, () => undoChange(after), { ok: true });
}

// Everything the page shows, the Library's rows too, read again after a change.
async function reloadAll() {
  await Promise.all([reload().catch(() => {}), loadLibrary()]);
}

// The page shows the effect where it happened: the Library morphs its cells, every other
// place cross-fades to its new state.
function showEffect() {
  if (state.view === "library") {
    morphOnNextRender();
    render();
  } else {
    transition(render);
  }
}

// Undo, from the toast or the Changes page. Whatever the answer, the page reloads first: the
// server may have put the files back even when its answer was lost.
export async function undoChange(change) {
  if (busy.change) return;
  hideToast();
  setBusy(true);
  try {
    const { after, failure } = await changeOutcome(change.id, "undo");
    await reloadAll();
    // With a tool list's Details still open, the page behind just redraws and Details is drawn
    // again from the files as they are now, focus on the switch the Undo changed back.
    if (isPanelOpen() && tools && tools.section.isConnected) {
      render();
      const undone = after && after.state === "undone";
      await tools.again({ focus: tools.flipped, flip: undone ? tools.flipped : null });
    } else {
      showEffect();
    }
    if (after && after.state === "undone") toast("Undone. The previous settings are back.", null, { ok: true });
    else if (after && after.state === "undo_blocked") toast("Undo stopped: " + (after.error ? shortPaths(after.error) : "the file changed after the change was applied."));
    else toast(failure);
  } finally {
    setBusy(false);
  }
}

// Toast ----------------------------------------------------------------------------------

const TOAST_MS = 6000;
let hideTimer = null;
let remaining = TOAST_MS;
let shownAt = 0;

function scheduleHide(ms) {
  clearTimeout(hideTimer);
  remaining = ms;
  shownAt = performance.now();
  hideTimer = setTimeout(hideToast, ms);
}

function pauseHide() {
  clearTimeout(hideTimer);
  remaining = Math.max(800, remaining - (performance.now() - shownAt));
}

export function hideToast() {
  clearTimeout(hideTimer);
  $("#toast").classList.remove("show");
}

// A short note after a change, with Undo when it can be undone. Hides after 6 s; the
// countdown pauses while the pointer or focus is on it.
// A check mark only for a state the server verified (applied, undone); never for an error.
export function toast(text, onUndo, { ok = false } = {}) {
  const node = $("#toast");
  node.classList.remove("show");
  node.replaceChildren(el("span", null, text));
  if (ok) node.prepend(checkMark());
  if (onUndo) node.append(button("Undo", () => onUndo()));
  node.append(el("span", "timer"));
  void node.offsetWidth;
  node.classList.add("show");
  node.onmouseenter = pauseHide;
  node.onmouseleave = () => scheduleHide(remaining);
  node.onfocusin = pauseHide;
  node.onfocusout = () => scheduleHide(remaining);
  scheduleHide(TOAST_MS);
}

// Wiring ---------------------------------------------------------------------------------

function trapFocus(event) {
  if (event.key !== "Tab" || !isPanelOpen()) return;
  const drawer = $("#drawer");
  // Only what is drawn: a closed Details hides everything but its summary. A toast shown while
  // the panel stays open (after a tool switch) is in the loop too, so its Undo can be reached.
  const shown = $("#toast").classList.contains("show") ? $$("button", $("#toast")) : [];
  const stops = [...$$("button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])", drawer), ...shown]
    .filter((node) => node.getClientRects().length > 0);
  const inside = drawer.contains(document.activeElement) || $("#toast").contains(document.activeElement);
  if (!stops.length || !inside) {
    event.preventDefault();
    (stops[0] || drawer).focus();
    return;
  }
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === drawer)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function initPanel() {
  const drawer = $("#drawer");
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  drawer.setAttribute("aria-labelledby", "panel-title");
  onOpenItem((row, tr, how) => openItem(row, { instant: how === "keyboard" }));
  // A refresh of the gateway's tool lists ended: an open tool list reads them again.
  document.addEventListener("kitden:tools", reloadTools);
  $("#scrim").addEventListener("click", () => { if (!busy.change) closePanel(); });
  document.addEventListener("keydown", trapFocus);
  document.addEventListener("keydown", (event) => {
    if (!isPanelOpen()) return;
    // Keyboard closes are instant: an action done many times a day must not wait.
    if (event.key === "Escape" && !busy.change) {
      event.preventDefault();
      closePanel({ instant: true });
    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && current && current.type === "review") {
      const apply = $("#drawer .apply");
      if (apply && !apply.disabled) { event.preventDefault(); apply.click(); }
    }
  });
}
