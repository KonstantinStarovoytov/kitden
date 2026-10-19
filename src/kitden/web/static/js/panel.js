// Side panel: item details, change review, the Apply motion, and the toast with Undo.
import { getJson, postJson, query } from "./api.js";
import { $, $$, button, el, plural, reportError, shortPath, shortPaths } from "./dom.js";
import { morphOnNextRender, onOpenItem } from "./map.js";
import { finishTransition, fold, transition } from "./motion.js";
import { CLIENT_NAMES, diffCounts, GATEWAY_NOTE, mark, notesSection, socket, stepText } from "./parts.js";
import { busy, current as currentModel, currentError, reload, render, setBusy, state } from "./store.js";

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
  if (current && current.type === "review" && current.change && current.change.state === "previewed") {
    postJson(`/api/changes/${encodeURIComponent(current.change.id)}/cancel`).catch(() => {});
  }
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

function joinWords(words) {
  if (words.length < 2) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

// Item details ---------------------------------------------------------------------------

export async function openItem(row, { instant = false } = {}) {
  current = { type: "item", row };
  const body = el("div", "body");
  body.append(el("div", "skeleton card"));
  openPanel([itemHeader(row), body, el("footer")], { instant });
  let definitions;
  try {
    const params = { name: row.name, kind: row.kind, project: state.project };
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
  if (!current || current.row !== row) return;
  current.definitions = definitions;
  showDetails(row, definitions);
}

function itemHeader(row) {
  const map = currentModel("map");
  const loads = (map ? map.columns : [])
    .filter((c) => ["on", "gw"].includes(row.cells[c.id] && row.cells[c.id].state))
    .map((c) => c.name);
  const lede = loads.length ? `Loads in ${joinWords(loads)}.` : "Does not load anywhere here.";
  return header(KIND_WORDS[row.kind] || row.kind, row.name, lede, "Close", true);
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

// A server the Gateway page lists under "Can move", with the entries a move takes and the
// gateway that can take them (none when it must be added in the gateway by hand). Without a
// registered gateway there is nothing to move into, so Details stays as it was. When the
// gateway could not be read (`unread`), Move cannot be judged: it is marked `unread`.
export function moveFor(row, model, unread = false) {
  if (row.kind !== "mcp_server") return null;
  if (!model) return unread ? { items: [], gateway: null, unread: true } : null;
  if (!model.gateways.length) return null;
  const direct = model.groups.move.find((r) => r.name === row.name);
  if (!direct || !direct.items.length) return null;
  return { items: direct.items, gateway: model.gateways.find((g) => g.movable) || null };
}

// The footer's lead action and the rest, in order; "move" stands for Move into the gateway.
// A problem comes before an option: the warning's fix leads, then Move, then a lone action. With
// a warning no button fixes, or a server to add in the gateway by hand first, nothing leads.
export function footerActions(offers, warnings, move) {
  const fix = offers.find((o) => warnings.some((f) => f.fix_action === o.action && f.client === o.def.client));
  const options = move && move.gateway ? ["move", ...offers] : offers;
  let lead = fix || null;
  if (!lead && !warnings.length && move && move.gateway) lead = "move";
  if (!lead && !warnings.length && !move && offers.length === 1) lead = offers[0];
  return { lead, rest: options.filter((o) => o !== lead) };
}

function moveButton({ items, gateway }, look) {
  const targets = items.map((item) => ({ item }));
  return button("Move into the gateway…", () => review({ action: "gateway.move", targets, params: { gateway: gateway.id } }), look);
}

// The other actions wait behind one button, so the primary one stands alone.
function moreButton(buttons) {
  const more = button("More", () => {
    more.replaceWith(...buttons);
    buttons[0].focus();
  }, "btn");
  return more;
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

// A switch that shows the plugin's real state. Pressing it opens the review; it flips only
// when the change is written and checked, never before (the Load map then shows the new state).
// Without an action the switch is locked: it shows the state and says where to change it.
function pluginSwitch(def, action) {
  const on = action ? action === "plugin.disable" : def.enabled === "on";
  const node = el("button", "switch");
  node.type = "button";
  node.setAttribute("role", "switch");
  node.setAttribute("aria-checked", String(on));
  node.append(el("span", "thumb"));
  if (!action) {
    node.disabled = true;
    node.setAttribute("aria-label", `${on ? "On" : "Off"} in ${clientName(def.client)}; not changed from here`);
    node.title = def.change_hint || "Not changed from here.";
    return node;
  }
  node.setAttribute("aria-label", `${on ? "Turn off" : "Turn on"} in ${clientName(def.client)}…`);
  node.title = on ? "On. Press to review turning it off." : "Off. Press to review turning it on.";
  // While the preview is fetched the thumb rests half-way: pending, not flipped.
  node.addEventListener("click", async () => {
    if (node.classList.contains("pending")) return;
    node.classList.add("pending");
    node.setAttribute("aria-busy", "true");
    try {
      await review({ action, targets: [{ item: def.id }], params: {} });
    } catch (error) {
      reportError(error);
    } finally {
      node.classList.remove("pending");
      node.removeAttribute("aria-busy");
    }
  });
  return node;
}

function showDetails(row, definitions) {
  const body = el("div", "body");
  const warnings = row.flags.filter((x) => x.level === "warning");
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
    const hints = covered.has(client) ? [] : new Set(byClient.get(client).filter((d) => d.change_hint && !d.actions.length).map((d) => d.change_hint));
    for (const hint of hints) section.append(el("p", "muted", hint));
    body.append(section);
  }
  if (!definitions.length) body.append(el("p", "muted", "No definitions found for this item here."));
  if (definitions.some((d) => d.secret_present)) {
    body.append(el("p", "muted", "This entry holds a secret. It is hidden here and never logged."));
  }
  const move = moveFor(row, currentModel("gateway"), Boolean(currentError("gateway")));
  if (move && move.unread) body.append(el("p", "muted", "Could not read the gateway, so Move is not offered."));
  else if (move && !move.gateway) body.append(el("p", "muted", GATEWAY_NOTE));

  const footer = el("footer");
  const withCommands = definitions.filter((d) => d.kind === "plugin" || d.kind === "marketplace");
  const commands = withCommands.length ? [button("Commands…", () => showCommands(row, withCommands), "btn")] : [];
  // Name the scope too when one client has more than one definition that can change.
  const offers = definitions.flatMap((def) => def.actions.filter((a) => ACTION_BUTTONS[a]).map((action) => ({ def, action })));
  const buttonFor = ({ def, action }, look) => {
    const twins = offers.filter((o) => o.def.client === def.client).length > 1;
    const where = twins ? ` (${scopeWords(def).toLowerCase()})` : "";
    const label = ACTION_BUTTONS[action](`${clientName(def.client)}${where}`);
    return button(label, () => review({ action, targets: [{ item: def.id }], params: {} }), look);
  };
  // The lead action is the primary button; the rest wait under More. Without a lead, all stay plain.
  const { lead, rest: others } = footerActions(offers, warnings, move);
  const rest = others.flatMap((o) => (o === "move" ? [moveButton(move, "btn")] : [...sideEffect(o, warnings), buttonFor(o, "btn")]));
  if (lead) {
    if (rest.length || commands.length) footer.append(moreButton([...rest, ...commands]));
    footer.append(lead === "move" ? moveButton(move, "btn primary") : buttonFor(lead, "btn primary"));
  } else {
    if (commands.length) footer.append(el("span", "note", "Install, update or move to another client:"), ...commands);
    footer.append(...rest);
  }
  swapContent([itemHeader(row), body, footer]);
}

async function showCommands(row, definitions) {
  const body = el("div", "body");
  body.append(el("p", "muted", "You run these yourself. This page never runs them."));
  const footer = el("footer");
  footer.append(button("Back", () => showDetails(row, current.definitions), "btn"));
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
  "skill.install": "Added",
};

// The review title names the exact entry; the toast uses the short name ("superpowers").
function changeWords(change) {
  const steps = change.steps.filter((s) => s.client !== "gateway");
  const names = joinWords([...new Set(steps.map((s) => s.name))]);
  const short = joinWords([...new Set(steps.map((s) => s.name.split("@")[0]))]);
  // A copied skill folder reaches every client that reads that folder, not only its owner.
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  reached.sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const clients = joinWords(reached.map(clientName));
  const title = {
    "gateway.move": `Move ${names} into the gateway`,
    "plugin.disable": `Turn off ${names} in ${clients}`,
    "plugin.enable": `Turn on ${names} in ${clients}`,
    "mcp.remove_direct": `Remove ${names} from ${clients}`,
    "gateway.connect": `Connect the gateway to ${clients}`,
    "plugin.install": `Add ${joinWords([...new Set(steps.filter((s) => s.name.includes("@")).map((s) => s.name))])} to ${clients}`,
    "marketplace.add": `Add the ${names} marketplace to ${clients}`,
    "skill.install": `Add ${names} to ${clients}`,
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
    what = `${verb} ${short} into the gateway`;
  }
  const notes = [...new Set(change.steps.map((s) => s.restart_note).filter(Boolean))]
    .map((note) => note.replace(/,? for this to take effect\.?$/, ""));
  const after = notes.length > 1 ? [`Restart or reload ${clients}`] : notes;
  return { title, done: [what, ...after].join(" · ") };
}

// Ask the server for a preview and show it. Used by the Load map, Gateway and Agents places.
export async function review(previewBody) {
  const result = await postJson("/api/changes/preview", previewBody);
  if (!result.ok || !result.data || !result.data.id) {
    current = { type: "error" };
    const footer = el("footer");
    footer.append(button("Close", () => closePanel(), "btn"));
    const body = el("div", "body");
    body.append(callout((result.data && result.data.detail) || `Could not prepare this change (${result.status}).`, "error"));
    openPanel([header("Review change", "Could not prepare this change", null, null), body, footer]);
    return;
  }
  showReview(result.data, previewBody);
}

// "After: [CC] Claude Code ● Off · [CU] Cursor ● Loads once", in the Load map's sockets.
// An entry with a note (a client that would load a skill twice) gets its one line below.
function afterLine(entries) {
  const box = el("div");
  const line = el("div", "after");
  line.append(el("span", "note", "After:"));
  for (const entry of entries) {
    const chip = el("span", "chip");
    chip.append(mark(entry.client), el("span", null, clientName(entry.client)), socket({ state: entry.state, word: entry.word }));
    line.append(chip);
  }
  box.append(line);
  for (const note of new Set(entries.map((e) => e.note).filter(Boolean))) box.append(callout(note));
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

function showReview(change, previewBody) {
  current = { type: "review", change, previewBody };
  const words = changeWords(change);
  const body = el("div", "body");
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
  const after = notesSection("After you apply", change.steps);
  if (after) body.append(after);

  const footer = el("footer");
  footer.append(el("span", "note", APPLY_KEY));
  const cancel = button("Cancel", () => closePanel(), "btn");
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

// The header's Cancel and the footer buttons are off while a change runs.
function lockReview(locked, apply, cancel) {
  apply.disabled = locked;
  cancel.disabled = locked;
  const close = $("#drawer header .top button");
  if (close) close.disabled = locked;
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
      next = button("Preview again", () => review(previewBody), "btn primary");
      apply.replaceWith(next);
    }
    next.focus();
    reload().then(render).catch(() => {});
    return;
  }
  await showApplied(after, apply, label);
}

// The server said `verified`: the button turns green while the page reloads, then the panel
// leaves at once and the toast offers Undo.
async function showApplied(after, apply, label) {
  for (const spin of apply.querySelectorAll(".spinner")) spin.remove();
  apply.prepend(checkMark());
  apply.classList.add("done");
  label.textContent = "Applied";
  await reload().catch(() => {});
  current = null;
  closePanel({ keepSelection: true, focus: false, force: true });
  showEffect();
  restoreFocus();
  setBusy(false);
  toast(changeWords(after).done, () => undoChange(after), { ok: true });
}

// The page shows the effect where it happened: the Load map morphs its cells, every other
// place cross-fades to its new state.
function showEffect() {
  if (state.view === "map") {
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
    await reload().catch(() => {});
    showEffect();
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
  // Only what is drawn: a closed Details hides everything but its summary.
  const stops = $$("button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])", drawer)
    .filter((node) => node.getClientRects().length > 0);
  if (!stops.length || !drawer.contains(document.activeElement)) {
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
