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

// The tab an arrow, Home or End moves to from tab `at` of `count`, or null for any other key.
// The arrows wrap around.
export function tabAfter(key, at, count) {
  if (key === "ArrowRight") return (at + 1) % count;
  if (key === "ArrowLeft") return (at - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

// Keys on a row of tabs: focus moves to the tab, then it is selected. A key with a modifier is
// the browser's (Alt+Left is Back), so it is left alone.
export function tabKeys(box) {
  box.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const tabs = $$('[role="tab"]', box);
    const at = tabs.indexOf(document.activeElement);
    const to = at < 0 ? null : tabAfter(event.key, at, tabs.length);
    if (to === null) return;
    event.preventDefault();
    if (to === at) return;
    tabs[to].focus();
    tabs[to].click();
  });
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

export function shortPath(path) {
  return path ? String(path).replace(/^\/Users\/[^/]+/, "~") : "";
}

export function shortPaths(text) {
  return String(text || "").replace(/\/Users\/[^/\s]+/g, "~");
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
