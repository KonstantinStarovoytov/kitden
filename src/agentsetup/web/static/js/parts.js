// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { button, el, plural } from "./dom.js";

export const STATE_WORDS = {
  on: "Loads", off: "Off", over: "Overridden", unk: "Unknown", gw: "Via gateway",
  missing: "Not installed", none: "—",
};
export const CLIENT_MARKS = {
  claude_code: "CC", codex: "CX", cursor: "CU", claude_desktop_code_tab: "CD",
};
export const CLIENT_NAMES = {
  claude_code: "Claude Code", codex: "Codex", cursor: "Cursor",
  claude_desktop_code_tab: "Claude Desktop (Code tab)",
};

export function socket({ state, where, word }) {
  const node = el("span", `socket s-${state}`);
  if (state === "none") {
    node.append(el("span", "word faint", "—"));
    node.setAttribute("aria-label", "Not set up");
    return node;
  }
  const dot = el("span", "dot");
  dot.setAttribute("aria-hidden", "true");
  node.append(dot, el("span", "word", word || STATE_WORDS[state] || state));
  if (where) node.append(el("span", "where", where));
  return node;
}

// Morph a socket to a new state: the fill drains or fills, the words blur across, one ping.
export function morphSocket(node, { state, where }) {
  const texts = [...node.querySelectorAll(".word, .where")];
  texts.forEach((t) => t.classList.add("swap"));
  setTimeout(() => {
    node.className = `socket s-${state} pulse`;
    const word = node.querySelector(".word");
    if (word) word.textContent = STATE_WORDS[state] || state;
    let place = node.querySelector(".where");
    if (where && !place) { place = el("span", "where swap"); node.append(place); }
    if (place) place.textContent = where || "";
    requestAnimationFrame(() => node.querySelectorAll(".swap").forEach((t) => t.classList.remove("swap")));
  }, 160);
}

export function mark(clientId) {
  const node = el("span", "mono-mark", CLIENT_MARKS[clientId] || "?");
  node.title = CLIENT_NAMES[clientId] || clientId;
  node.setAttribute("aria-hidden", "true");
  return node;
}

export function flag({ text, level }) {
  return el("span", level === "warning" ? "flag" : "flag info", text);
}

export function heading(text, aside) {
  const h = el("h2");
  h.append(el("span", null, text));
  if (aside) h.append(el("span", "count", aside));
  return h;
}

export function skeleton(kind = "card", count = 3) {
  const box = el("div");
  box.setAttribute("aria-busy", "true");
  box.setAttribute("aria-label", "Loading");
  for (let i = 0; i < count; i += 1) box.append(el("div", `skeleton ${kind}`));
  return box;
}

export function banner(what, onRetry) {
  const node = el("div", "banner");
  node.setAttribute("role", "alert");
  node.append(el("span", null, `Could not load ${what}.`), button("Retry", onRetry));
  return node;
}

const ACTION_WORDS = {
  "gateway.connect": "Added gateway",
  "mcp.remove_direct": "Removed",
  "plugin.enable": "Turned on",
  "plugin.disable": "Turned off",
  "setup_server.register": "Added show my setup",
};

// One line for a change log entry: what, which entries, which clients.
export function changeTitle(entry) {
  const verb = ACTION_WORDS[entry.action] || entry.action;
  const names = [...new Set(entry.steps.map((s) => s.name))];
  const clients = [...new Set(entry.steps.map((s) => CLIENT_NAMES[s.client] || s.client))];
  const what = entry.action === "gateway.connect" || entry.action === "setup_server.register" ? "" : ` ${names.join(", ")}`;
  return `${verb}${what} · ${clients.join(", ")}`;
}

// The latest log line per change, newest first.
export function latestChanges(entries) {
  const seen = new Map();
  for (const entry of entries) if (!seen.has(entry.id)) seen.set(entry.id, entry);
  return [...seen.values()];
}

export function timeOf(entry) {
  const when = new Date(entry.time);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export { plural };
