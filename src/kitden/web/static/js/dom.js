// DOM helpers. All text from client files is untrusted (FR-041): it only ever goes in through
// textContent or attributes, never as HTML.

import { ICONS } from "./icons.js";

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

// A lucide icon as an SVG node. Its shapes are built from the fixed ICONS table with DOM calls,
// never from markup or client text. An unknown name gives an empty icon; only the table's own
// names count.
const SVG_NS = "http://www.w3.org/2000/svg";

export function icon(name, size = 16, className = "ic") {
  const node = document.createElementNS(SVG_NS, "svg");
  const attrs = {
    viewBox: "0 0 24 24",
    width: size,
    height: size,
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "1.75",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
    class: className,
  };
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.dataset.icon = name;
  for (const [tag, shape] of Object.hasOwn(ICONS, name) ? ICONS[name] : []) {
    const part = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(shape)) part.setAttribute(key, value);
    node.append(part);
  }
  return node;
}

export function button(label, onClick, className = "btn small") {
  const node = el("button", className, label);
  node.type = "button";
  if (onClick) {
    node.addEventListener("click", (event) => {
      if (node.dataset.working) return; // a second press while the first one works
      busyWhile(node, Promise.resolve().then(() => onClick(event))).catch(reportError);
    });
  }
  return node;
}

// A button whose work takes a moment shows a small spinner in place of its words. It waits a
// little first, so quick work never flickers; the words stay in the layout, so the button
// keeps its size. The button is off while it works and comes back as it was.
export function busyWhile(node, work, delay = 150) {
  const promise = Promise.resolve(work);
  const wasDisabled = node.disabled;
  let shown = false;
  node.dataset.working = "1";
  const timer = setTimeout(() => {
    shown = true;
    node.classList.add("busy");
    node.setAttribute("aria-busy", "true");
    node.disabled = true;
  }, delay);
  const done = () => {
    clearTimeout(timer);
    delete node.dataset.working;
    if (!shown) return;
    node.classList.remove("busy");
    node.removeAttribute("aria-busy");
    node.disabled = wasDisabled;
  };
  promise.then(done, done);
  return promise;
}

// A control that waits while another change is written (an Apply or an Undo): it keeps focus and
// its words (aria-disabled, not disabled; style.css gives it the busy cursor) and its title says why:
// `waits` true says WAITS, and words of its own say those. `title` is its own title when it does
// not wait.
export const WAITS = "Another change is being written.";
export function showWaits(node, waits, title = "") {
  if (waits) node.setAttribute("aria-disabled", "true");
  else node.removeAttribute("aria-disabled");
  node.title = waits ? (typeof waits === "string" ? waits : WAITS) : title;
}

// While the page reads another project (app.js sets `#main.pending`), nothing on it may act on the
// project it was drawn for.
export const pageWaits = () => Boolean($("#main")?.classList.contains("pending"));

// Whether the last input was a key (true) or a pointer press (false). Focus that comes after a key
// is keyboard focus, also where `:focus-visible` fails (Safari on an SVG path); focus that the page
// gives back after a mouse press is not.
let keyed = false;
globalThis.window?.addEventListener?.("keydown", () => (keyed = true), true);
globalThis.window?.addEventListener?.("pointerdown", () => (keyed = false), true);
export const byKeys = () => keyed;

// A redraw replaces every node. What names a control across it: its data-focus key (a tab, a
// filter button, a menu), or for a table row its own key. Null when it has neither.
export function focusKey(node) {
  if (node.dataset.focus) return node.dataset.focus;
  return node.dataset.key ? `row:${node.dataset.key}` : null;
}

// The control with this data-focus key inside `box`, if there is one.
export function withFocusKey(box, key) {
  return key ? [...box.querySelectorAll("[data-focus]")].find((node) => node.dataset.focus === key) || null : null;
}

// Keys on a tree grid: `rows` as shown ({ id, parent, group, expanded }), the row at `at` focused.
// Down, Up, Home and End move. Right unfolds a closed row and goes into an open one; Left folds an
// open row and goes from any other to its parent. Enter opens a row's Details (`details`), or
// folds a group, which has none. Null for any other key: the browser keeps it.
export function gridKey(rows, at, key) {
  const row = rows[at];
  if (!row) return null;
  const last = rows.length - 1;
  if (key === "ArrowDown") return { at: Math.min(at + 1, last) };
  if (key === "ArrowUp") return { at: Math.max(at - 1, 0) };
  if (key === "Home") return { at: 0 };
  if (key === "End") return { at: last };
  if (key === "ArrowRight") {
    if (row.expanded === false) return { at, toggle: row.id };
    const child = rows[at + 1];
    return { at: row.expanded && child && child.parent === row.id ? at + 1 : at };
  }
  if (key === "ArrowLeft") {
    if (row.expanded === true) return { at, toggle: row.id };
    const parent = rows.findIndex((r) => r.id === row.parent);
    return { at: parent < 0 ? at : parent };
  }
  if (key === "Enter") return row.group ? { at, toggle: row.id } : { at, details: row.id };
  return null;
}

// A tree grid's keys on `grid` (gridKey, for its `rows` as shown): `toggle(row)` folds, `details(row)`
// opens and `focus(id)` moves. A key with a modifier, or on a row's own button, is left alone.
export function gridKeys(grid, rows, { toggle, details, focus }) {
  grid.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || !event.target.dataset.row) return;
    const next = gridKey(rows, rows.findIndex((r) => r.id === event.target.dataset.row), event.key);
    if (!next) return;
    event.preventDefault();
    const row = rows[next.at];
    if (next.toggle) toggle(row);
    else if (next.details) details(row);
    else focus(row.id);
  });
}

// A cell of a tree grid: "gridcell" or "columnheader".
export function gridCell(role, className, text) {
  const node = el("div", className, text);
  node.setAttribute("role", role);
  return node;
}

// A tree grid's row and its name cell, which starts with the fold mark (and the row's icon). The
// row says its level, whether it is open and selected, and takes the Tab key when `current`.
export function treeRow(className, row, { current, selected }) {
  const node = el("div", className);
  node.setAttribute("role", "row");
  node.setAttribute("aria-level", String(row.depth + 1));
  if (row.expanded !== undefined) node.setAttribute("aria-expanded", String(row.expanded));
  node.setAttribute("aria-selected", String(selected));
  node.tabIndex = current ? 0 : -1;
  node.dataset.row = row.id;
  node.dataset.focus = `row:${row.id}`;
  const name = gridCell("gridcell", "tg-name");
  name.style.setProperty("--depth", String(row.depth));
  const caret = el("span", row.expanded === undefined ? "caret none" : "caret", "▸");
  caret.setAttribute("aria-hidden", "true");
  name.append(caret);
  if (row.icon) name.append(icon(row.icon, 13));
  return { node, name };
}

// The Tab key, and focus, go to the row `id` of a tree grid's row `nodes`, and to the controls of
// that row that `controls(node)` gives; every other row's leave the Tab order.
export function focusTreeRow(nodes, id, controls) {
  for (const node of nodes) {
    const on = node.dataset.row === id;
    node.tabIndex = on ? 0 : -1;
    for (const control of controls(node)) control.tabIndex = on ? 0 : -1;
    if (on) node.focus();
  }
}

export function shortPath(path) {
  return path ? String(path).replace(/^\/(?:Users|home)\/[^/]+/, "~") : "";
}

export function shortPaths(text) {
  return String(text || "").replace(/\/(?:Users|home)\/[^/\s]+/g, "~");
}

// Where secrets live, as the server names it in /api/about: "Keychain" on macOS, "keyring" on
// Linux. Until it answers, the macOS word.
let secretsName = "Keychain";

export function secretsWord() {
  return secretsName;
}

export function setSecretsWord(word) {
  if (word) secretsName = word;
}

// A name cut to `max` characters with "…"; the whole name goes in the hover text and the label.
export function cutName(name, max = 24) {
  const text = String(name || "");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// "Claude Code, Codex and Cursor".
export function joinWords(words) {
  if (words.length < 2) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

export function reportError(error) {
  console.error(error);
  const status = document.getElementById("scanned");
  if (status) status.textContent = "error";
}
