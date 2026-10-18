// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { button, el, plural } from "./dom.js";

export const STATE_WORDS = {
  on: "Loads", off: "Off", over: "Overridden", unk: "Unknown", gw: "Via gateway",
  missing: "Not installed", none: "—",
};
export const CLIENT_MARKS = {
  claude_code: "CC", codex: "CX", cursor: "CU", claude_desktop_code_tab: "CD",
};
export const CLIENT_ICONS = {
  claude_code: "claude.png", claude_desktop_code_tab: "claude.png",
  codex: "codex.png", cursor: "cursor.png",
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

// Morph a socket to a new state: the words blur out, the new socket blurs in, one ping.
// The socket is rebuilt, so "not set up" (no dot) and the other states swap cleanly.
export function morphSocket(node, { state, where }) {
  const texts = [...node.querySelectorAll(".word, .where")];
  texts.forEach((t) => t.classList.add("swap"));
  setTimeout(() => {
    const fresh = socket({ state, where });
    node.className = `${fresh.className} pulse`;
    if (fresh.hasAttribute("aria-label")) node.setAttribute("aria-label", fresh.getAttribute("aria-label"));
    else node.removeAttribute("aria-label");
    // Keep the old dot when both have one, so its fill drains or fills instead of jumping.
    const oldDot = node.querySelector(".dot");
    const newDot = fresh.querySelector(".dot");
    if (oldDot && newDot) newDot.replaceWith(oldDot);
    const parts = [...fresh.childNodes];
    parts.filter((p) => p.matches(".word, .where")).forEach((p) => p.classList.add("swap"));
    node.replaceChildren(...parts);
    requestAnimationFrame(() => node.querySelectorAll(".swap").forEach((t) => t.classList.remove("swap")));
  }, 160);
}

export function mark(clientId) {
  const node = el("span", "mono-mark", CLIENT_MARKS[clientId] || "?");
  node.title = CLIENT_NAMES[clientId] || clientId;
  const icon = CLIENT_ICONS[clientId];
  if (icon) {
    // One rounded tile for every client; the vendor icon keeps its own colors.
    node.className = "client-mark";
    node.dataset.icon = icon.replace(".png", "");
    const image = el("img");
    image.src = `/static/brand/clients/${icon}`;
    image.alt = "";
    image.width = 24;
    image.height = 24;
    image.addEventListener("error", () => {
      node.className = "mono-mark";
      node.textContent = CLIENT_MARKS[clientId] || "?";
    }, { once: true });
    node.replaceChildren(image);
  }
  node.setAttribute("aria-hidden", "true");
  return node;
}

export function flag({ text, level }) {
  return el("span", level === "warning" ? "flag" : "flag info", text);
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
  "setup_server.update": "Updated show my setup to Kitden",
};

// One line for a change log entry: what, which entries, which clients. Plugins go by their
// short name ("superpowers"); the review named the exact entry before Apply.
export function changeTitle(entry) {
  const verb = ACTION_WORDS[entry.action] || entry.action;
  const plugin = ["plugin.enable", "plugin.disable"].includes(entry.action);
  const names = [...new Set(entry.steps.map((s) => (plugin ? s.name.split("@")[0] : s.name)))];
  const clients = [...new Set(entry.steps.map((s) => CLIENT_NAMES[s.client] || s.client))];
  const whole = ["gateway.connect", "setup_server.register", "setup_server.update"].includes(entry.action);
  const what = whole ? "" : ` ${names.join(", ")}`;
  return `${verb}${what} · ${clients.join(", ")}`;
}

// The latest log line per change, newest first.
export function latestChanges(entries) {
  const seen = new Map();
  for (const entry of entries) if (!seen.has(entry.id)) seen.set(entry.id, entry);
  return [...seen.values()];
}

export { plural };
