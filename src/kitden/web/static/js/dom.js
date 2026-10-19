// DOM helpers. All text from client files is untrusted (FR-041): it only ever goes in through
// textContent or attributes, never as HTML.

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
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

// A redraw replaces every node. What names a control across it: its data-focus key (a tab, a
// filter button, a menu), or for a table row its own key. Null when it has neither.
export function focusKey(node) {
  if (node.dataset.focus) return node.dataset.focus;
  return node.dataset.key ? `row:${node.dataset.key}` : null;
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

// Only http and https links are ever made clickable.
export function webLink(url, text) {
  if (!/^https?:\/\//i.test(String(url || ""))) return el("span", null, text);
  const link = el("a", "btn", text);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

export function shortPath(path) {
  return path ? String(path).replace(/^\/Users\/[^/]+/, "~") : "";
}

export function shortPaths(text) {
  return String(text || "").replace(/\/Users\/[^/\s]+/g, "~");
}

export function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

export function reportError(error) {
  console.error(error);
  const status = document.getElementById("scanned");
  if (status) status.textContent = "error";
}
