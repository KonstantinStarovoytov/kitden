// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { button, el, plural } from "./dom.js";

export const STATE_WORDS = {
  on: "Loads", off: "Off", over: "Overridden", unk: "Unknown", gw: "Via gateway",
  missing: "Not installed", none: "—",
};
export const CLIENT_MARKS = {
  claude_code: "CC", codex: "CX", cursor: "CU", claude_desktop_code_tab: "CD", gateway: "GW",
};
// Icon file names under /static/brand/clients. Codex and Cursor also ship a "-dark" version.
export const CLIENT_ICONS = {
  claude_code: "claude", claude_desktop_code_tab: "claude", codex: "codex", cursor: "cursor",
};
export const DARK_ICONS = new Set(["codex", "cursor"]);
export const CLIENT_NAMES = {
  claude_code: "Claude Code", codex: "Codex", cursor: "Cursor",
  claude_desktop_code_tab: "Claude Desktop (Code tab)", gateway: "Gateway",
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
    // Where the vendor offers a dark version, both are in the tile and CSS shows one.
    node.className = "client-mark";
    node.dataset.icon = icon;
    const image = (suffix, kind) => {
      const img = el("img", kind);
      img.src = `/static/brand/clients/${icon}${suffix}.png`;
      img.alt = "";
      img.width = 24;
      img.height = 24;
      img.addEventListener("error", () => {
        node.className = "mono-mark";
        node.textContent = CLIENT_MARKS[clientId] || "?";
      }, { once: true });
      return img;
    };
    node.replaceChildren(image("", "icon-light"));
    if (DARK_ICONS.has(icon)) {
      node.classList.add("has-dark");
      node.append(image("-dark", "icon-dark"));
    }
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
  "gateway.move": "Moved into the gateway",
  "gateway.switch": "Switched the gateway",
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
  // The gateway's own step is not a client: the line names the clients the entry left.
  const steps = entry.steps.filter((s) => s.client !== "gateway");
  const names = [...new Set(steps.map((s) => (plugin ? s.name.split("@")[0] : s.name)))];
  const clients = [...new Set(steps.map((s) => CLIENT_NAMES[s.client] || s.client))];
  const whole = ["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update"].includes(entry.action);
  const what = whole ? "" : ` ${names.join(", ")}`;
  return `${verb}${what} · ${clients.join(", ")}`;
}

// How many lines a diff adds and removes: the summary says so before the diff is opened.
export function diffCounts(text) {
  let added = 0;
  let removed = 0;
  for (const line of String(text || "").split("\n")) {
    if (line.startsWith("+++") || line.startsWith("---")) continue;
    if (line.startsWith("+")) added += 1;
    else if (line.startsWith("-")) removed += 1;
  }
  return { added, removed };
}

// The latest log line per change, newest first.
export function latestChanges(entries) {
  const seen = new Map();
  for (const entry of entries) if (!seen.has(entry.id)) seen.set(entry.id, entry);
  return [...seen.values()];
}

export { plural };
