// Side panel: item details, change review, the Apply motion, and the toast with Undo.
import { getJson, postJson, query } from "./api.js";
import { $, $$, button, el, shortPath, shortPaths } from "./dom.js";
import { morphOnNextRender, onOpenItem } from "./map.js";
import { CLIENT_NAMES, mark, socket } from "./parts.js";
import { busy, data, reload, render, state } from "./store.js";

const KIND_WORDS = {
  mcp_server: "MCP server", plugin: "Plugin", skill: "Skill", hook: "Hook", marketplace: "Marketplace",
};
const CLIENT_ORDER = ["claude_code", "claude_desktop_code_tab", "codex", "cursor"];
const ACTION_BUTTONS = {
  "plugin.disable": (client) => `Turn off in ${client}…`,
  "plugin.enable": (client) => `Turn on in ${client}…`,
  "mcp.remove_direct": (client) => `Remove from ${client}…`,
};
const APPLY_KEY = /Mac/.test(navigator.platform) ? "⌘ Enter to apply" : "Ctrl Enter to apply";

// What is open now: "item" or "review", and for a review the change and the request behind it.
let current = null;
let opener = null;
let openerKey = null;

const wait = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });
const clientName = (id) => CLIENT_NAMES[id] || id;

export function isPanelOpen() {
  return $("#drawer").classList.contains("open");
}

// Put content in the panel and slide it in. Keyboard opens are instant.
export function openPanel(content, { instant = false } = {}) {
  const drawer = $("#drawer");
  drawer.replaceChildren(...content);
  if (isPanelOpen()) return;
  opener = document.activeElement;
  const row = opener && opener.closest ? opener.closest("tr[data-key]") : null;
  openerKey = row ? row.dataset.key : null;
  for (const node of [drawer, $("#scrim")]) {
    node.classList.toggle("instant", instant);
    node.classList.add("open");
  }
  drawer.focus();
}

export function closePanel({ instant = false, keepSelection = false, focus = true } = {}) {
  if (!isPanelOpen()) return;
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

function header(kicker, title, lede, closeLabel = "Close", mono = false) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kicker), button(closeLabel, () => closePanel(), "btn ghost small"));
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
    }
    return;
  }
  if (!current || current.row !== row) return;
  current.definitions = definitions;
  showDetails(row, definitions);
}

function itemHeader(row) {
  const loads = (data.map ? data.map.columns : [])
    .filter((c) => ["on", "gw"].includes(row.cells[c.id] && row.cells[c.id].state))
    .map((c) => c.name);
  const lede = loads.length ? `Loads in ${joinWords(loads)}.` : "Does not load anywhere here.";
  return header(KIND_WORDS[row.kind] || row.kind, row.name, lede, "Close", true);
}

function warningText(text) {
  if (/loads it twice$/.test(text)) return `${text}. Two copies load; turn one off or remove it.`;
  if (text === "Around gateway") return "Around gateway: this server is set up directly, not through your gateway.";
  return text;
}

function scopeWords(def) {
  const project = def.project ? def.project.split("/").filter(Boolean).pop() : "";
  const words = {
    user: "Everywhere",
    project: `Project ${project}`,
    local: project ? `Only on this Mac · ${project}` : "Only on this Mac",
    plugin: "From a plugin",
    account: "Claude account",
    managed: "Managed by your organization",
  }[def.scope] || def.scope;
  const via = def.owner_client && def.owner_client !== def.client ? ` · via ${clientName(def.owner_client)}` : "";
  return `${words}${via}`;
}

function layer(def) {
  let look = "off";
  let badge = "Not loaded";
  if (def.loads) { look = def.via_gateway ? "gw" : "on"; badge = "Loads"; }
  else if (def.overridden) { look = "over"; badge = "Overridden"; }
  else if (def.enabled === "off") badge = "Off";
  else if (def.enabled === "unknown") { look = "unk"; badge = "Unknown"; }
  const row = el("div", def.loads ? "layer wins" : "layer");
  const dot = socket({ state: look });
  dot.replaceChildren(dot.querySelector(".dot"));
  dot.setAttribute("aria-hidden", "true");
  const middle = el("div");
  middle.append(el("div", "name", scopeWords(def)));
  const where = el("div", "why mono", shortPath(def.source));
  where.title = def.source || "";
  middle.append(where);
  if (def.why && def.why !== "Loads.") middle.append(el("div", "why", def.why));
  row.append(dot, middle, el("span", def.loads ? "badge win" : "badge", badge));
  return row;
}

function showDetails(row, definitions) {
  const body = el("div", "body");
  for (const f of row.flags.filter((x) => x.level === "warning")) body.append(callout(warningText(f.text)));
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
    const hints = new Set(byClient.get(client).filter((d) => d.change_hint && !d.actions.length).map((d) => d.change_hint));
    for (const hint of hints) section.append(el("p", "muted", hint));
    body.append(section);
  }
  if (!definitions.length) body.append(el("p", "muted", "No definitions found for this item here."));
  if (definitions.some((d) => d.secret_present)) {
    body.append(el("p", "muted", "This entry holds a secret. It is hidden here and never logged."));
  }

  const footer = el("footer");
  const withCommands = definitions.filter((d) => d.kind === "plugin" || d.kind === "marketplace");
  if (withCommands.length) {
    footer.append(el("span", "note", "Install, update or move to another client:"));
    footer.append(button("Commands…", () => showCommands(row, withCommands), "btn"));
  }
  // Name the scope too when one client has more than one definition that can change.
  const offers = definitions.flatMap((def) => def.actions.filter((a) => ACTION_BUTTONS[a]).map((action) => ({ def, action })));
  for (const { def, action } of offers) {
    const twins = offers.filter((o) => o.def.client === def.client).length > 1;
    const where = twins ? ` (${scopeWords(def).toLowerCase()})` : "";
    const label = ACTION_BUTTONS[action](`${clientName(def.client)}${where}`);
    footer.append(button(label, () => review({ action, targets: [{ item: def.id }], params: {} }), offers.length === 1 ? "btn primary" : "btn"));
  }
  const drawer = $("#drawer");
  drawer.replaceChildren(itemHeader(row), body, footer);
}

async function showCommands(row, definitions) {
  const body = el("div", "body");
  body.append(el("p", "muted", "You run these yourself. This page never runs them."));
  const footer = el("footer");
  footer.append(button("Back", () => showDetails(row, current.definitions), "btn"));
  $("#drawer").replaceChildren(header("Commands", row.name, null, "Close", true), body, footer);
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

// Change review --------------------------------------------------------------------------

const DONE_WORDS = {
  "plugin.disable": "Turned off", "plugin.enable": "Turned on", "mcp.remove_direct": "Removed",
  "gateway.connect": "Connected the gateway", "setup_server.register": "Added show my setup",
};

// The review title names the exact entry; the toast uses the short name ("superpowers").
function changeWords(change) {
  const names = joinWords([...new Set(change.steps.map((s) => s.name))]);
  const short = joinWords([...new Set(change.steps.map((s) => s.name.split("@")[0]))]);
  const clients = joinWords([...new Set(change.steps.map((s) => clientName(s.client)))]);
  const title = {
    "plugin.disable": `Turn off ${names} in ${clients}`,
    "plugin.enable": `Turn on ${names} in ${clients}`,
    "mcp.remove_direct": `Remove ${names} from ${clients}`,
    "gateway.connect": `Connect the gateway to ${clients}`,
    "setup_server.register": `Add “show my setup” to ${clients}`,
  }[change.action] || change.action;
  const verb = DONE_WORDS[change.action] || change.action;
  const what = ["gateway.connect", "setup_server.register"].includes(change.action)
    ? `${verb} to ${clients}`
    : `${verb} ${short} ${change.action === "mcp.remove_direct" ? "from" : "in"} ${clients}`;
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
    openPanel([header("Review change", "Could not prepare this change"), body, footer]);
    return;
  }
  showReview(result.data, previewBody);
}

function diffLines(text) {
  const pre = el("pre", "diff");
  for (const line of String(text || "").split("\n")) {
    let look = null;
    if (/^(\+\+\+|---|@@)/.test(line)) look = "faint";
    else if (line.startsWith("+")) look = "add";
    else if (line.startsWith("-")) look = "del";
    pre.append(el("span", look, `${line}\n`));
  }
  return pre;
}

function showReview(change, previewBody) {
  current = { type: "review", change, previewBody };
  const words = changeWords(change);
  const body = el("div", "body");
  if (change.shared_file_warning) body.append(callout("This edits a project file that is usually shared through git."));
  for (const step of change.steps) {
    const box = el("div", "step");
    const head = el("div", "step-head");
    const file = el("span", "file mono", shortPath(step.path));
    file.title = step.path || "";
    head.append(mark(step.client), el("strong", null, clientName(step.client)), file);
    box.append(head, diffLines(step.diff));
    body.append(box);
    if (step.command) body.append(el("p", "muted", `Runs ${clientName(step.client)}'s own command: ${step.command}`));
  }
  const notes = [...new Set(change.steps.flatMap((s) => [s.restart_note, s.login_note && `Log in: ${s.login_note}`]).filter(Boolean))];
  if (notes.length) {
    const after = el("section");
    const list = el("ul", "checklist");
    for (const note of notes) list.append(el("li", null, note));
    after.append(el("h2", null, "After you apply"), list);
    body.append(after);
  }

  const footer = el("footer");
  footer.append(el("span", "note", APPLY_KEY));
  const cancel = button("Cancel", () => closePanel(), "btn");
  const apply = el("button", "btn primary apply");
  apply.type = "button";
  const label = el("span", "label", "Apply");
  apply.append(label);
  apply.addEventListener("click", () => applyChange(change, { apply, cancel, label, body }).catch(failed(apply, cancel, label, body)));
  footer.append(cancel, apply);
  openPanel([header("Review change", words.title, "Nothing is written until you press Apply. A backup is kept, so you can undo.", "Cancel"), body, footer]);
}

function failed(apply, cancel, label, body) {
  return (error) => {
    console.error(error);
    busy.change = false;
    resetApply(apply, cancel, label);
    body.prepend(callout("Could not reach the page server. Nothing was changed by this page.", "error"));
  };
}

function swapLabel(label, text) {
  label.classList.add("swap");
  setTimeout(() => { label.textContent = text; label.classList.remove("swap"); }, 120);
}

function resetApply(apply, cancel, label) {
  for (const extra of apply.querySelectorAll(".spinner, .check")) extra.remove();
  label.textContent = "Apply";
  label.classList.remove("swap");
  apply.disabled = false;
  cancel.disabled = false;
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

// Apply → Applying… (spinner) → Applied (the check draws); then the panel leaves and the
// page shows the effect where it happened.
async function applyChange(change, { apply, cancel, label, body }) {
  if (busy.change || apply.disabled) return;
  busy.change = true;
  apply.disabled = true;
  cancel.disabled = true;
  swapLabel(label, "Applying…");
  apply.prepend(el("span", "spinner"));
  const started = performance.now();
  const result = await postJson(`/api/changes/${encodeURIComponent(change.id)}/apply`);
  const after = result.data && result.data.id ? result.data : null;
  if (after) current.change = after;

  if (!after || after.state !== "verified") {
    busy.change = false;
    resetApply(apply, cancel, label);
    const reason = after ? STOPPED[after.state] || `The change stopped: ${after.state}.` : (result.data && result.data.detail) || `Apply failed (${result.status}).`;
    const detail = after && after.error ? ` (${shortPaths(after.error)})` : "";
    for (const old of body.querySelectorAll(".callout.error")) old.remove();
    body.prepend(callout(`${reason}${detail}`, "error"));
    if (after && after.state !== "previewed") {
      const again = current.previewBody;
      apply.replaceWith(button("Preview again", () => review(again), "btn primary"));
    }
    reload().then(render).catch(() => {});
    return;
  }

  await wait(Math.max(0, 520 - (performance.now() - started)));
  for (const spin of apply.querySelectorAll(".spinner")) spin.remove();
  apply.prepend(checkMark());
  label.textContent = "Applied";
  await Promise.all([wait(450), reload().catch(() => {})]);
  current = null;
  closePanel({ keepSelection: true, focus: false });
  morphOnNextRender();
  render();
  restoreFocus();
  busy.change = false;
  toast(changeWords(after).done, () => undoChange(after));
}

export async function undoChange(change) {
  hideToast();
  busy.change = true;
  try {
    const result = await postJson(`/api/changes/${encodeURIComponent(change.id)}/undo`);
    await reload().catch(() => {});
    morphOnNextRender();
    render();
    const after = result.data;
    if (after && after.state === "undone") toast("Undone. The previous settings are back.");
    else if (after && after.state === "undo_blocked") toast("Undo stopped: the file changed after the change was applied.");
    else toast((after && after.detail) || `Undo failed (${result.status}).`);
  } finally {
    busy.change = false;
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
export function toast(text, onUndo) {
  const node = $("#toast");
  node.classList.remove("show");
  node.replaceChildren(el("span", null, text));
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
  const stops = $$("button:not([disabled]), a[href], select, input, [tabindex]:not([tabindex='-1'])", drawer);
  if (!stops.length) { event.preventDefault(); drawer.focus(); return; }
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
  drawer.addEventListener("keydown", trapFocus);
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
