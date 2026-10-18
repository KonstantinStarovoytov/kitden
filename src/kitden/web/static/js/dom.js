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
  if (onClick) node.addEventListener("click", (event) => Promise.resolve(onClick(event)).catch(reportError));
  return node;
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
