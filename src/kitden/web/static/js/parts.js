// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { $, button, el, plural } from "./dom.js";
import { reducedMotion } from "./motion.js";

export const STATE_WORDS = {
  on: "Loads", off: "Off", over: "Overridden", unk: "Unknown", gw: "Via gateway",
  missing: "Not installed", none: "—", via: "Via Claude Code", done: "Skills added",
};
export const CLIENT_MARKS = {
  claude_code: "CC", codex: "CX", cursor: "CU", claude_desktop_code_tab: "CD", gateway: "GW",
};
// Icon file names under /static/brand/clients. Codex and Cursor also ship a "-dark" version.
export const CLIENT_ICONS = {
  claude_code: "claude", claude_desktop_code_tab: "claude", codex: "codex", cursor: "cursor",
};
export const DARK_ICONS = new Set(["codex", "cursor"]);
export const CLIENT_ORDER = ["claude_code", "claude_desktop_code_tab", "codex", "cursor"];
export const CLIENT_NAMES = {
  claude_code: "Claude Code", codex: "Codex", cursor: "Cursor",
  claude_desktop_code_tab: "Claude Desktop (Code tab)", gateway: "Gateway",
};
// One client's checkbox in an Add form. Its name is the client's name (and the note after it),
// so a screen reader never says "on"; its value is the client id. `onChange` hears the new state.
export function clientCheck(client, checked, note, onChange) {
  const label = el("label");
  const box = el("input");
  box.type = "checkbox";
  box.value = client;
  box.checked = checked;
  box.setAttribute("aria-label", note ? `${CLIENT_NAMES[client]} · ${note}` : CLIENT_NAMES[client]);
  box.addEventListener("change", () => { if (onChange) onChange(box.checked); });
  label.append(box, el("span", null, CLIENT_NAMES[client]));
  if (note) label.append(el("span", "muted", ` · ${note}`));
  return label;
}

// A direct server, when no gateway here can take it: the Gateway page and Details say the same.
export const GATEWAY_NOTE = "Add the server in the gateway first, then remove its direct entry here.";

// `label` is what a screen reader hears for a dash: why nothing can be done, when known.
export function socket({ state, where, word, label }) {
  const node = el("span", `socket s-${state}`);
  if (state === "none") {
    node.append(el("span", "word faint", "—"));
    node.setAttribute("aria-label", label || "Not set up");
    return node;
  }
  const dot = el("span", "dot");
  dot.setAttribute("aria-hidden", "true");
  node.append(dot, el("span", "word", word || STATE_WORDS[state] || state));
  if (where) node.append(el("span", "where", where));
  return node;
}

// Morph a socket to a new state: the words fade out, the new socket fades in, one ping.
// The socket is rebuilt, so "not set up" (no dot) and the other states swap cleanly.
// `next` takes what socket() takes, so a word or a dash's reason stays. With reduced motion the
// new words show at once.
export function morphSocket(node, next) {
  const still = reducedMotion.matches;
  const swap = () => {
    const fresh = socket(next);
    node.className = still ? fresh.className : `${fresh.className} pulse`;
    if (fresh.hasAttribute("aria-label")) node.setAttribute("aria-label", fresh.getAttribute("aria-label"));
    else node.removeAttribute("aria-label");
    // Keep the old dot when both have one, so its fill drains or fills instead of jumping.
    const oldDot = node.querySelector(".dot");
    const newDot = fresh.querySelector(".dot");
    if (oldDot && newDot) newDot.replaceWith(oldDot);
    const parts = [...fresh.childNodes];
    if (!still) parts.filter((p) => p.matches(".word, .where")).forEach((p) => p.classList.add("swap"));
    node.replaceChildren(...parts);
    if (!still) requestAnimationFrame(() => node.querySelectorAll(".swap").forEach((t) => t.classList.remove("swap")));
  };
  if (still) { swap(); return; }
  node.querySelectorAll(".word, .where").forEach((t) => t.classList.add("swap"));
  setTimeout(swap, 160);
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

// "Applying 2 of 5" while a change with several steps runs; one step just says the verb.
export function stepText(verb, done, total) {
  return total > 1 ? `${verb} ${done} of ${total}` : `${verb}…`;
}

export function flag({ text, level }) {
  return el("span", level === "warning" ? "flag" : "flag info", text);
}

// The end of a row that opens Details: a chevron for the eye, words for a screen reader.
export function opens() {
  const node = el("span", "opens");
  const chevron = el("span", null, "›");
  chevron.setAttribute("aria-hidden", "true");
  node.append(chevron, el("span", "sr-only", "Open details"));
  return node;
}

export function skeleton(kind = "card", count = 3) {
  const box = el("div");
  box.setAttribute("aria-busy", "true");
  box.setAttribute("aria-label", "Loading");
  for (let i = 0; i < count; i += 1) box.append(el("div", `skeleton ${kind}`));
  return box;
}

const CONTROLS = "button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])";

// The page is drawn again after a Retry, so this button is gone. Focus goes to the new Retry
// when the read failed again, otherwise to the first control on the page.
export function banner(what, onRetry) {
  const node = el("div", "banner");
  node.setAttribute("role", "alert");
  node.append(el("span", null, `Could not load ${what}.`), button("Retry", async () => {
    await onRetry();
    const main = $("#main");
    if (!main || main.contains(document.activeElement)) return;
    (main.querySelector(".banner button") || main.querySelector(CONTROLS) || main).focus();
  }));
  return node;
}

// Above a page whose latest read failed: the page still shows the read from that time.
export function staleNote(time) {
  const clock = new Date(time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const node = el("div", "callout stale");
  node.setAttribute("role", "note");
  const icon = el("span", null, "⚠");
  icon.setAttribute("aria-hidden", "true");
  node.append(icon, el("span", null, `Could not refresh. Showing what Kitden read at ${clock}.`));
  return node;
}

const ACTION_WORDS = {
  "gateway.connect": "Added gateway",
  "gateway.move": "Moved into the gateway",
  "gateway.switch": "Switched the gateway",
  "plugin.install": "Added",
  "marketplace.add": "Added marketplace",
  "skill.install": "Added skill",
  "plugin.skills": "Added",
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
  const plugin = ["plugin.enable", "plugin.disable", "plugin.install"].includes(entry.action);
  // The gateway's own step is not a client: the line names the clients the entry left. An
  // install's marketplace steps only make the plugin reachable: the line names the plugin.
  const steps = entry.steps.filter((s) => s.client !== "gateway" && (entry.action !== "plugin.install" || s.name.includes("@")));
  const names = [...new Set(steps.map((s) => (plugin ? s.name.split("@")[0] : s.name)))];
  // A copied skill folder reaches every client that reads that folder.
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  reached.sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const clients = reached.map((c) => CLIENT_NAMES[c] || c);
  // A plugin's skills can be many; the line counts them, the change lists them.
  if (entry.action === "plugin.skills") return `${verb} ${plural(names.length, "skill", "skills")} · ${clients.join(", ")}`;
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

// The restart and log-in notes of a change's steps, each once, under a heading. Null when none.
export function notesSection(heading, steps) {
  const notes = [...new Set(steps.flatMap((s) => [s.restart_note, s.login_note && `Log in: ${s.login_note}`]).filter(Boolean))];
  if (!notes.length) return null;
  const section = el("section");
  const list = el("ul", "checklist");
  for (const note of notes) list.append(el("li", null, note));
  section.append(el("h2", null, heading), list);
  return section;
}

// The latest log line per change, newest first.
export function latestChanges(entries) {
  const seen = new Map();
  for (const entry of entries) if (!seen.has(entry.id)) seen.set(entry.id, entry);
  return [...seen.values()];
}

export { plural };
